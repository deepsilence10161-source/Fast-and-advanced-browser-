"""scripts/ci/repeat_e2e.py: repeat-visit A/B harness (offline parts)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))

import repeat_e2e as rp  # noqa: E402


def test_modes_and_candidate_features():
    assert set(rp.MODES) == {"chromium_defaults", "swiftra", "swiftra_lcpp"}
    assert rp.MODES["swiftra"] == ""
    feats = rp.MODES["swiftra_lcpp"].split("=", 1)[1].split(",")
    # feature names = BASE_FEATURE variable minus the leading 'k' (base/feature_internal.h @155)
    assert feats == ["LCPCriticalPathPredictor", "LCPPFontURLPredictor", "LCPPAutoPreconnectLcpOrigin",
                     "LCPPPrefetchSubresource", "HttpDiskCachePrewarming"]


def test_page_and_assets():
    rp.build_assets()
    html = rp.page_html().decode()
    assert "SPEED:done" in html and rp.CSS in html and rp.APP in html and rp.HERO in rp.APP_TAIL
    # the LCP image is discovered only by the script (late): no static <img>/preload for it in the HTML
    assert "<img" not in html and 'rel="preload"' not in html and f'src="{rp.HERO}' not in html
    assert len(rp.ASSETS[rp.APP][0]) > 190000 and rp.ASSETS[rp.HERO][1] == "image/png"
    assert "immutable" in rp.IMMUTABLE and "31536000" in rp.IMMUTABLE


def test_visit_attribution():
    recs = [{"path": "/spa.html", "rid": "a", "t0": 10.0}, {"path": "/" + rp.APP, "rid": None, "t0": 10.2},
            {"path": "/" + rp.HERO, "rid": None, "t0": 11.0}, {"path": "/spa.html", "rid": "b", "t0": 20.0},
            {"path": "/" + rp.CSS, "rid": None, "t0": 19.8}, {"path": "/news.html", "rid": "x", "t0": 10.5}]
    a = [r["path"] for r in rp.visit_requests("a", recs)]
    assert a == ["/" + rp.APP, "/" + rp.HERO]
    assert [r["path"] for r in rp.visit_requests("b", recs)] == ["/" + rp.CSS]   # browser prefetch just before
    assert rp.visit_requests("zz", recs) == []


def test_summary_counts_only_finished_visits():
    v = {"page": {"load": 100, "lcp": 90, "fcp": 80, "app_ran": 70, "hero_end": 85}, "network": []}
    bad = {"page": None, "network": []}
    cyc = {m: {"cold": [v, bad], "warm": [v]} for m in rp.MODES}
    s = rp.summarize({"cycles": [cyc]})
    assert s["swiftra"]["cold"]["n"] == 1 and s["swiftra"]["cold"]["of"] == 2 and s["swiftra"]["cold"]["lcp_ms"] == 90


def test_spki_hash(tmp_path):
    key, crt = tmp_path / "k.pem", tmp_path / "c.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-keyout", str(key),
                    "-out", str(crt), "-subj", "/CN=t"], check=True, capture_output=True)
    h = rp.spki_hash(str(crt))
    assert len(h) == 44 and h.endswith("=")
    assert rp.spki_hash(str(crt)) == h
