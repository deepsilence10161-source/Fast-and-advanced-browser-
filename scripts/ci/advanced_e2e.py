#!/usr/bin/env python3
"""patches/0010: Swiftra's advanced defaults, checked by behaviour on the device (no settings screen-scraping).

1. HTTPS-First (balanced) on by default
   http://httponly.example.com/ is mapped (--host-resolver-rules) to a plain-HTTP server on the runner, for every
   port. Chromium first upgrades the navigation to https:// (port 443 -> the same plain-HTTP server -> TLS error).
     * HTTPS-Upgrades only (Chromium default)  -> silent fallback, the HTTP page loads   (marker visible)
     * HTTPS-First balanced (patches/0010)     -> "connection is not secure" interstitial (marker NOT visible)
   example.com is a unique public name, so the balanced mode applies (private IPs / single-label hosts are exempt).

2. Third-party cookies blocked by default
   https://top.example.com/top.html (first party) embeds https://cookie3p.example.org/frame (third party). Both are
   mapped to a local HTTPS server (self-signed; --ignore-certificate-errors for this run only, see
   components/network_session_configurator). The frame response sets `s3p=1; SameSite=None; Secure` and reports
   document.cookie to the top page.
     * allowed (Chromium default) -> frame sees s3p=1
     * blocked (patches/0010)     -> frame sees nothing
   Control: the top page's own first-party cookie must still work (fp=1), so cookies in general are not broken.

The command-line file is honoured because the package is the debug app (see startup_netlog.py); it is removed after.
Usage: advanced_e2e.py --package <pkg> --out <dir> [--devtools http://127.0.0.1:9222]
Prints ADVANCED_E2E PASS / FAIL / NOT_RUN.
"""
import argparse
import http.server
import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shield_e2e import adb, open_internal, page_text, targets, internal_text  # noqa: E402
from startup_netlog import CMDLINE_FILE, CMDLINE_JS, resolve_launcher  # noqa: E402

HTTP_PORT, HTTPS_PORT = 8770, 8771
HTTP_HOST, TOP_HOST, THIRD_HOST = "httponly.example.com", "top.example.com", "cookie3p.example.org"
HTTP_MARKER = "SWIFTRA_HTTPONLY_PAGE_LOADED"
RULES = (f"MAP {HTTP_HOST} 127.0.0.1:{HTTP_PORT},MAP {TOP_HOST} 127.0.0.1:{HTTPS_PORT},"
         f"MAP {THIRD_HOST} 127.0.0.1:{HTTPS_PORT}")

TOP_HTML = f"""<!doctype html><meta name="viewport" content="width=device-width"><title>3PC:pending</title>
<h1>Swiftra 3PC test</h1><div id="r"></div>
<script>
let n = 0; const seen = [];
window.addEventListener('message', e => {{
  if (e.origin !== 'https://{THIRD_HOST}') return;
  seen.push(String(e.data)); n++;
  if (n === 1) {{ const f = document.createElement('iframe'); f.src = 'https://{THIRD_HOST}/frame?2'; document.body.appendChild(f); }}
  else {{ document.title = '3PC:done'; document.getElementById('r').textContent = JSON.stringify({{fp: document.cookie, frame: seen}}); }}
}});
const f = document.createElement('iframe'); f.src = 'https://{THIRD_HOST}/frame?1'; document.body.appendChild(f);
</script>"""
FRAME_HTML = "<!doctype html><script>parent.postMessage(document.cookie, '*');</script>"
RESULT_JS = ("(() => ({title: document.title, r: (document.getElementById('r') || {}).textContent || '', "
             "fp: document.cookie}))()")
HFM_JS = ("(() => ({title: document.title, href: location.href, text: (document.body ? document.body.innerText : '')"
          ".slice(0, 600), ids: ['primary-button', 'proceed-link', 'main-message', 'details-button']"
          ".filter(i => document.getElementById(i))}))()")


HITS = []   # (port, host, path) of every plain request the runner-side servers answered


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        HITS.append((self.server.server_port, host, self.path))
        if host == HTTP_HOST:
            body, extra = f"<!doctype html><title>{HTTP_MARKER}</title><h1>{HTTP_MARKER}</h1>", []
        elif host == TOP_HOST and self.path.startswith("/top.html"):
            body, extra = TOP_HTML, [("Set-Cookie", "fp=1; SameSite=Lax; Secure; Path=/")]
        elif host == THIRD_HOST and self.path.startswith("/frame"):
            body, extra = FRAME_HTML, [("Set-Cookie", "s3p=1; SameSite=None; Secure; Path=/")]
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)


def start_servers(tmp):
    http_srv = http.server.ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    threading.Thread(target=http_srv.serve_forever, daemon=True).start()
    key, crt = os.path.join(tmp, "k.pem"), os.path.join(tmp, "c.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-keyout", key,
                    "-out", crt, "-subj", f"/CN={TOP_HOST}",
                    "-addext", f"subjectAltName=DNS:{TOP_HOST},DNS:{THIRD_HOST}"],
                   check=True, capture_output=True, timeout=60)
    https_srv = http.server.ThreadingHTTPServer(("127.0.0.1", HTTPS_PORT), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    https_srv.socket = ctx.wrap_socket(https_srv.socket, server_side=True)
    threading.Thread(target=https_srv.serve_forever, daemon=True).start()
    return http_srv, https_srv


def find_target(substr):
    for t in targets(DEVTOOLS):
        if t.get("type") == "page" and substr in t.get("url", ""):
            return t
    return None


def eval_on(substr, js, wait=20, until=None):
    t0, last = time.time(), None
    while time.time() - t0 < wait:
        t = find_target(substr)
        if t:
            v = page_text(DEVTOOLS, t["url"], js)
            if isinstance(v, dict):
                last = dict(v, target_url=t["url"])
                if until is None or until(last):
                    return last
        time.sleep(1)
    return last


def hfm_verdict(r, http_hits=None):
    """interstitial = warning page rendered; blocked_no_http = error page and the plain-HTTP page was never fetched
    (same security outcome; desktop headless renders the HFM interstitial as an empty chrome-error page)."""
    if not r:
        return "no_page"
    text = (r.get("title", "") + " " + r.get("text", ""))
    if HTTP_MARKER in text or http_hits:
        return "http_loaded_silently"
    if r.get("ids") or "not secure" in text.lower() or "secure connection" in text.lower():
        return "interstitial"
    if str(r.get("href", "")).startswith("chrome-error://") and http_hits == 0:
        return "blocked_no_http"
    return "unknown"


def http_hits():
    return sum(1 for port, host, _ in HITS if port == HTTP_PORT and host == HTTP_HOST)


def tpc_verdict(r):
    if not r or r.get("title") != "3PC:done":
        return "no_result"
    try:
        d = json.loads(r.get("r") or "{}")
    except ValueError:
        return "no_result"
    frame = " ".join(d.get("frame", []))
    fp_ok = "fp=1" in (d.get("fp") or "")
    if not fp_ok:
        return "first_party_cookie_broken"
    return "third_party_allowed" if "s3p=1" in frame else "third_party_blocked"


DEVTOOLS = "http://127.0.0.1:9222"


def main():
    global DEVTOOLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--devtools", default=DEVTOOLS)
    ap.add_argument("--socket", default=os.environ.get("SOCK", "chrome_devtools_remote"))
    a = ap.parse_args()
    DEVTOOLS = a.devtools
    os.makedirs(a.out, exist_ok=True)
    pkg, res = a.package, {"package": a.package, "rules": RULES}
    tmp = tempfile.mkdtemp()
    start_servers(tmp)
    flags = f'_ --host-resolver-rules="{RULES}" --ignore-certificate-errors'
    comp = resolve_launcher(pkg)
    try:
        adb("shell", "am", "force-stop", pkg)
        if adb("shell", "settings", "get", "global", "adb_enabled").strip() != "1":
            adb("shell", "settings", "put", "global", "adb_enabled", "1")
        adb("shell", "am", "set-debug-app", "--persistent", pkg)
        adb("shell", f"echo '{flags}' > {CMDLINE_FILE} && chmod 644 {CMDLINE_FILE}")
        for p in (HTTP_PORT, HTTPS_PORT):
            adb("reverse", f"tcp:{p}", f"tcp:{p}")
        adb("shell", "am", "start", "-W", "-n", comp, timeout=60) if comp else adb(
            "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(8)
        adb("forward", "tcp:9222", f"localabstract:{a.socket}")
        time.sleep(2)
        res["version_open"] = open_internal(DEVTOOLS, "chrome://version/")
        time.sleep(3)
        cl = internal_text(DEVTOOLS, "chrome://version", CMDLINE_JS) or ""
        res["flags_applied"] = "--host-resolver-rules" in cl
        res["command_line"] = cl[:500]
        if not res["flags_applied"]:
            res["verdict"] = "not_run"
        else:
            # 1. HTTPS-First
            res["hfm_open"] = open_internal(DEVTOOLS, f"http://{HTTP_HOST}/")
            r = eval_on(HTTP_HOST, HFM_JS, wait=25,
                        until=lambda x: hfm_verdict(x, http_hits()) in ("interstitial", "http_loaded_silently"))
            time.sleep(4)   # a late silent fallback must not be missed
            r = eval_on(HTTP_HOST, HFM_JS, wait=5) or r
            res["hfm_page"], res["hfm_http_hits"] = r, http_hits()
            res["hfm"] = hfm_verdict(r, res["hfm_http_hits"])
            subprocess.run(f"adb exec-out screencap -p > '{os.path.join(a.out, 'hfm.png')}'", shell=True, timeout=30)
            # 2. third-party cookies
            res["tpc_open"] = open_internal(DEVTOOLS, f"https://{TOP_HOST}/top.html")
            r = eval_on(TOP_HOST, RESULT_JS, wait=25, until=lambda x: x.get("title") == "3PC:done")
            res["tpc_page"] = r
            res["tpc"] = tpc_verdict(r)
            subprocess.run(f"adb exec-out screencap -p > '{os.path.join(a.out, 'tpc.png')}'", shell=True, timeout=30)
            res["server_hits"] = HITS[:40]
            ok = res["hfm"] in ("interstitial", "blocked_no_http") and res["tpc"] == "third_party_blocked"
            res["verdict"] = "pass" if ok else "fail"
    finally:
        adb("shell", "rm", "-f", CMDLINE_FILE)
        adb("shell", "am", "clear-debug-app")
        adb("shell", "am", "force-stop", pkg)
    json.dump(res, open(os.path.join(a.out, "advanced_e2e.json"), "w"), indent=1, ensure_ascii=False)
    print("advanced e2e:", json.dumps({k: v for k, v in res.items() if k != "command_line"}, ensure_ascii=False)[:3000])
    print("ADVANCED_E2E", {"pass": "PASS", "fail": "FAIL"}.get(res["verdict"], "NOT_RUN"),
          f"hfm={res.get('hfm')} tpc={res.get('tpc')}")
    return 1 if res["verdict"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
