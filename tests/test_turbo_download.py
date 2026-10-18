"""Patch 0017 (Swiftra Turbo Download) + the HTTP/2 download server used by the device test."""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
PATCH = open(os.path.join(ROOT, "patches", "0017-swiftra-turbo-download.patch"), encoding="utf-8").read()


def added(path):
    """Added lines of one file in the patch."""
    out, cur = [], None
    for ln in PATCH.splitlines():
        if ln.startswith("+++ "):
            cur = ln[4:].split("\t")[0]
        elif cur and cur.endswith(path) and ln.startswith("+") and not ln.startswith("+++"):
            out.append(ln[1:])
    return "\n".join(out)


def test_ascii_and_in_series():
    assert all(ord(c) < 128 for c in PATCH)
    series = [l.strip() for l in open(os.path.join(ROOT, "patches", "series")) if l.strip() and not l.startswith("#")]
    assert "0017-swiftra-turbo-download.patch" in series


def test_feature_default_enabled():
    assert "BASE_DECLARE_FEATURE(kSwiftraSliceConnections)" in added("download_features.h")
    assert "BASE_FEATURE(kSwiftraSliceConnections, base::FEATURE_ENABLED_BY_DEFAULT)" in added("download_features.cc")


def test_tag_reaches_resource_request():
    assert "request->socket_tag = params->socket_tag();" in added("download_utils.cc")
    p = added("download_url_parameters.h")
    assert "net::SocketTag socket_tag_;" in p and "socket_tag() const" in p and "set_socket_tag" in p
    assert '#include "net/socket/socket_tag.h"' in p


def test_slice_tag_android_only_and_own_uid():
    j = added("parallel_download_job.cc")
    assert "#if BUILDFLAG(IS_ANDROID)" in j and "#endif" in j
    assert "net::SocketTag::UNSET_UID" in j                      # never changes the uid (no permission needed)
    assert "features::kSwiftraSliceConnections" in j
    assert j.index("#if BUILDFLAG(IS_ANDROID)") < j.index("set_socket_tag") < j.index("#endif")


def test_defaults_mode_turns_feature_off():
    import speed_e2e
    assert "SwiftraSliceConnections" in speed_e2e.MODES["chromium_defaults"]
    assert speed_e2e.MODES["swiftra"] == ""
    assert f"MAP {speed_e2e.H2DL} 127.0.0.1:{speed_e2e.H2PORT}" in speed_e2e.RULES


@pytest.mark.skipif(not shutil.which("curl") or not shutil.which("openssl"), reason="curl/openssl missing")
def test_h2_server_paces_per_connection():
    pytest.importorskip("h2")
    if "HTTP2" not in subprocess.run(["curl", "-V"], capture_output=True, text=True).stdout:
        pytest.skip("curl without HTTP/2")
    from h2_dl_server import H2DownloadServer
    d = tempfile.mkdtemp()
    key, crt = os.path.join(d, "k.pem"), os.path.join(d, "c.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-keyout", key, "-out",
                    crt, "-subj", "/CN=h2dl.example.com", "-addext", "subjectAltName=DNS:h2dl.example.com"],
                   check=True, capture_output=True)
    data = hashlib.sha256(b"t").digest() * (2 * 1024 * 1024 // 32)
    port = 8791
    srv = H2DownloadServer(port, crt, key, data, 1024 * 1024).start()
    q = len(data) // 4
    url = f"https://h2dl.example.com:{port}/f/{{}}.zip"
    res = ["--resolve", f"h2dl.example.com:{port}:127.0.0.1"]
    args = ["curl", "--parallel", "--parallel-max", "4"]
    for i in range(4):
        args += (["--next"] if i else []) + ["-sk", "--http2", *res, "-r", f"{i*q}-{(i+1)*q-1}", url.format("one"),
                                             "-o", os.path.join(d, f"one{i}")]
    t = time.time()
    subprocess.run(args, check=True, timeout=30)
    one_wall = time.time() - t
    t = time.time()
    ps = [subprocess.Popen(["curl", "-sk", "--http2", *res, "-r", f"{i*q}-{(i+1)*q-1}", url.format("four"), "-o",
                            os.path.join(d, f"four{i}")]) for i in range(4)]
    [p.wait(timeout=30) for p in ps]
    four_wall = time.time() - t
    one, four = srv.stats("one"), srv.stats("four")
    assert one["connections"] == 1 and one["requests"] == 4 and one["complete"] and one["alpn"] == ["h2"]
    assert four["connections"] == 4 and four["complete"]
    assert one_wall > 1.6 and four_wall < 1.2          # 2 MiB at 1 MiB/s: ~2 s on one connection, ~0.5 s on four
    for name in ("one", "four"):
        assert b"".join(open(os.path.join(d, f"{name}{i}"), "rb").read() for i in range(4)) == data
