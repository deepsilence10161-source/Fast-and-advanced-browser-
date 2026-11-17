#!/usr/bin/env python3
"""PERSONAL_CRED: does a WebAuthn/passkey request from the personal browser reach the SYSTEM credential provider?

The CI-only helper app (tools/clip_helper) is registered as the system Credential Manager provider and logs every
package that asks it. Loopback page, no account, no real site, nothing is ever returned.
Every line: `PERSONAL_CRED <id> PASS|FAIL|NOT_RUN <detail>`; NOT_RUN = could not be measured (never a pass).
Needs Android 14+ (API 34).

  C00 control : a foreground helper request through CredentialManager reaches the selected provider
  C01 browser : a page calling navigator.credentials.get({publicKey}) after a real tap sends NO request to it
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
PROVIDER = HELPER + "/.CredSvc"
REPORTS = []

PAGE = """<!doctype html><meta name=viewport content="width=device-width"><title>passkey</title>
<body style="margin:0"><button id=b style="display:block;width:100vw;height:100vh;font-size:48px;background:#fc0">tap for passkey</button>
<script>
const r=(s,v)=>fetch('/report?step='+s+'&v='+encodeURIComponent(v||''));
addEventListener('load',()=>r('ready',String(!!(window.PublicKeyCredential))));
document.getElementById('b').addEventListener('click',async()=>{
  r('clicked');
  try{
    await navigator.credentials.get({publicKey:{challenge:new Uint8Array(32),rpId:location.hostname,timeout:15000,userVerification:'discouraged'}});
    r('result','ok');
  }catch(e){r('result',String(e&&e.name)+':'+String(e&&e.message).slice(0,80));}
});
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
def cred_requests(logcat):
    return re.findall(r"CLIPHELPER[^\n]*CRED_(?:GET|CREATE) pkg=([\w.:\-]+)", logcat)


def classify_browser(requests, pkg, control_ok, clicked):
    if not control_ok:
        return "NOT_RUN", "control failed: the provider did not receive the helper's own request"
    if pkg in requests:
        return "FAIL", f"the browser's passkey request reached the system credential provider ({requests})"
    if not clicked:
        return "NOT_RUN", f"the page click was not observed; requests={requests}"
    return "PASS", f"real tap + navigator.credentials.get sent no request from {pkg}; requests={requests}"


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
        print(f"PERSONAL_CRED {cid} {status} {detail}", flush=True)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    P.go_root()
    P.reverse()
    sdk = P.sh("getprop ro.build.version.sdk")
    print(f"PERSONAL_CRED env package={pkg} abi={P.sh('getprop ro.product.cpu.abi')} sdk={sdk}", flush=True)
    try:
        if not sdk.isdigit() or int(sdk) < 34:
            res("C00_control", "NOT_RUN", f"Credential Manager providers need API 34+, this is {sdk}")
            res("C01_browser", "NOT_RUN", "no control")
        else:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from ui_capture import Device, launch, wait_ready  # noqa: E402
            dev = Device(pkg, a.out, lambda line: print("PERSONAL_CRED_UI", line, flush=True))
            P.sh(f"settings put secure credential_service {PROVIDER}")
            P.sh(f"settings put secure credential_service_primary {PROVIDER}")
            time.sleep(2)
            print("PERSONAL_CRED credential_service=" + P.sh("settings get secure credential_service") +
                  " primary=" + P.sh("settings get secure credential_service_primary"), flush=True)
            P.adb("shell", "am", "force-stop", pkg)
            launch(dev)
            wait_ready(dev, seconds=180)

            P.adb("logcat", "-c")
            P.adb("shell", "am", "start", "-W", "-n", f"{HELPER}/.Main", "--es", "mode", "cred", timeout=60)
            control_ok, log = False, ""
            for _ in range(15):
                time.sleep(1)
                log = P.adb("logcat", "-d", "-s", "CLIPHELPER:I")
                if HELPER in cred_requests(log):
                    control_ok = True
                    break
            res("C00_control", "PASS" if control_ok else "NOT_RUN",
                f"requests={cred_requests(log)} lines={[l[-90:] for l in log.splitlines() if 'CRED' in l][:5]}")

            w, h = 1080, 2400
            m = re.search(r"(\d+)x(\d+)", P.sh("wm size"))
            if m:
                w, h = int(m.group(1)), int(m.group(2))
            P.adb("shell", "am", "force-stop", HELPER)
            P.adb("logcat", "-c")
            since = len(REPORTS)
            P.adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", f"http://localhost:{PORT}/pk", "-p", pkg, timeout=60)
            ready = wait_for("ready", since, 40)
            time.sleep(3)
            P.sh(f"input tap {w // 2} {h // 2}")
            clicked = wait_for("clicked", since, 10)
            result = wait_for("result", since, 20)
            time.sleep(3)
            log = P.adb("logcat", "-d", "-s", "CLIPHELPER:I")
            s, d = classify_browser(cred_requests(log), pkg, control_ok, bool(clicked))
            res("C01_browser", s, d + f" page_ready={ready} webauthn_result={(result or {}).get('v')}")
    except Exception as e:  # noqa: BLE001
        print("PERSONAL_CRED harness_error", repr(e)[:300], flush=True)
        return 2
    finally:
        P.sh("settings delete secure credential_service")
        P.sh("settings delete secure credential_service_primary")
        try:
            open(os.path.join(a.out, "logcat_tail.txt"), "w").write(P.adb("logcat", "-d", "-t", "3000", timeout=60))
        except Exception:  # noqa: BLE001
            pass
    c = summarize(results)
    json.dump({"package": pkg, "results": results, "summary": c}, open(os.path.join(a.out, "personal_cred.json"), "w"), indent=1)
    print(f"PERSONAL_CRED_SUMMARY pass={c['PASS']} fail={c['FAIL']} not_run={c['NOT_RUN']}", flush=True)
    return 1 if c["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
