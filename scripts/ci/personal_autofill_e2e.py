#!/usr/bin/env python3
"""PERSONAL_AF: does the personal browser expose web forms to the Android AUTOFILL service? (real Android runtime)

The CI-only helper app (tools/clip_helper) is registered as the system autofill service and logs every package that
asks it to fill. Synthetic login form on loopback, no account, no real site, nothing is ever filled.
Every line: `PERSONAL_AF <id> PASS|FAIL|NOT_RUN <detail>`; NOT_RUN = could not be measured (never a pass).

  A00 control : a foreground helper field really triggers a request to the selected autofill service
  A01 browser : focusing username/password fields of a web login form in the personal browser sends NO request
"""
import argparse
import http.server
import json
import os
import re
import sys
import threading
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import personal_e2e as P  # noqa: E402

PORT = P.PORT
HELPER = "com.swiftra.cliphelper"
SERVICE = HELPER + "/.FillSvc"
REPORTS = []

PAGE = """<!doctype html><meta name=viewport content="width=device-width"><title>login</title>
<body style="margin:8px"><form method=post action=/none autocomplete=on>
<input id=u name=username autocomplete=username autofocus style="width:94vw;font-size:30px"><br>
<input id=p name=password type=password autocomplete=current-password style="width:94vw;font-size:30px"></form>
<script>
const r=(s)=>fetch('/report?step='+s);
document.getElementById('u').addEventListener('focus',()=>r('focus_u'));
document.getElementById('p').addEventListener('focus',()=>r('focus_p'));
addEventListener('load',()=>r('ready'));
</script>"""


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/report":
            REPORTS.append({k: v[0] for k, v in q.items()})
            body, ct = b"ok", "text/plain"
        else:
            body, ct = PAGE.encode(), "text/html"
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


# ---------------------------------------------------------------- pure helpers (host-tested)
def autofill_requests(logcat):
    """Packages that asked the helper's autofill service to fill, in order."""
    return re.findall(r"CLIPHELPER[^\n]*AUTOFILL_REQUEST pkg=([\w.:\-]+)", logcat)


def classify_browser(requests, pkg, control_ok, focus_seen):
    if not control_ok:
        return "NOT_RUN", "control failed: the autofill service did not receive the helper's own request"
    if pkg in requests:
        return "FAIL", f"the browser asked the system autofill service to fill ({requests})"
    if not focus_seen:
        return "NOT_RUN", f"form focus not observed in the page; requests={requests}"
    return "PASS", f"form fields focused, no autofill request from {pkg}; requests={requests}"


def summarize(results):
    c = {"PASS": 0, "FAIL": 0, "NOT_RUN": 0}
    for r in results:
        c[r["status"]] += 1
    return c


def wait_for(step, since, secs=20):
    t0 = time.time()
    while time.time() - t0 < secs:
        got = [r for r in REPORTS[since:] if r.get("step") == step]
        if got:
            return got[-1]
        time.sleep(1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pkg = a.package
    os.makedirs(a.out, exist_ok=True)
    results = []

    def res(cid, status, detail=""):
        results.append({"id": cid, "status": status, "detail": detail})
        print(f"PERSONAL_AF {cid} {status} {detail}", flush=True)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    P.go_root()
    P.reverse()
    url = f"http://127.0.0.1:{PORT}/login"
    print(f"PERSONAL_AF env package={pkg} abi={P.sh('getprop ro.product.cpu.abi')} sdk={P.sh('getprop ro.build.version.sdk')}", flush=True)
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from ui_capture import Device, launch, wait_ready  # noqa: E402
        dev = Device(pkg, a.out, lambda line: print("PERSONAL_AF_UI", line, flush=True))
        P.sh(f"settings put secure autofill_service {SERVICE}")
        time.sleep(2)
        sel = P.sh("settings get secure autofill_service")
        print(f"PERSONAL_AF autofill_service={sel}", flush=True)
        P.adb("shell", "am", "force-stop", pkg)
        launch(dev)
        wait_ready(dev, seconds=180)

        # A00 control
        P.adb("logcat", "-c")
        P.adb("shell", "am", "start", "-W", "-n", f"{HELPER}/.Main", "--es", "mode", "autofill", timeout=60)
        control_ok, log = False, ""
        for _ in range(12):
            time.sleep(1)
            log = P.adb("logcat", "-d", "-s", "CLIPHELPER:I")
            if HELPER in autofill_requests(log):
                control_ok = True
                break
        res("A00_control", "PASS" if control_ok else "NOT_RUN",
            f"requests={autofill_requests(log)} lines={[l for l in log.splitlines() if 'AUTOFILL' in l][:4]}")

        # A01 browser form
        w, h = 1080, 2400
        m = re.search(r"(\d+)x(\d+)", P.sh("wm size"))
        if m:
            w, h = int(m.group(1)), int(m.group(2))
        P.adb("logcat", "-c")
        since = len(REPORTS)
        P.open_url(pkg, url)
        wait_for("ready", since, 40)
        time.sleep(3)
        P.sh(f"input tap {w // 2} {int(h * 0.17)}")
        time.sleep(2)
        P.sh(f"input tap {w // 2} {int(h * 0.26)}")
        time.sleep(2)
        P.sh("input text probe")
        time.sleep(6)
        focus = bool(wait_for("focus_u", since, 1) or wait_for("focus_p", since, 1))
        log = P.adb("logcat", "-d", "-s", "CLIPHELPER:I")
        s, d = classify_browser(autofill_requests(log), pkg, control_ok, focus)
        res("A01_browser_form", s, d + f" focus_seen={focus}")
    except Exception as e:  # noqa: BLE001
        print("PERSONAL_AF harness_error", repr(e)[:300], flush=True)
        return 2
    finally:
        P.sh("settings delete secure autofill_service")
        try:
            open(os.path.join(a.out, "logcat_tail.txt"), "w").write(P.adb("logcat", "-d", "-t", "3000", timeout=60))
        except Exception:  # noqa: BLE001
            pass
    c = summarize(results)
    json.dump({"package": pkg, "results": results, "summary": c}, open(os.path.join(a.out, "personal_af.json"), "w"), indent=1)
    print(f"PERSONAL_AF_SUMMARY pass={c['PASS']} fail={c['FAIL']} not_run={c['NOT_RUN']}", flush=True)
    return 1 if c["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
