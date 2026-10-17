#!/usr/bin/env python3
"""Swiftra Shield end-to-end check on an Android emulator / Redroid (patches/0006).

Flow (all inside CI; no real malicious site is contacted):
  1. Local canary server (127.0.0.1:8001 via `adb reverse`) serves phishing/malware/safe pages whose
     body is a unique marker. The phishing/malware paths are canaries baked into the signed list.
  2. Open the SAFE page -> first Safe Browsing check installs SwiftraShieldApiHandler, which downloads
     and verifies the signed list. Wait for logcat "SwiftraShield ... list updated|loaded".
  3. Open each case in the browser; read the page through DevTools (title + innerText), fall back to a
     uiautomator dump. Classify: loaded (marker visible) / blocked_phishing / blocked_malware.
  4. Google's harmless test pages (testsafebrowsing.appspot.com, user permission 2026-10-17) and
     example.com are checked the same way.
Exit 0 only if every expectation holds. Writes <out>/shield_e2e.json + one screenshot per case.
"""
import argparse
import http.server
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.request

PORT = 8001
CANARY_DIR = "__swiftra_shield_canary__"
# components/security_interstitials_strings.grdp @155.0.8059.80
HEADING = "Dangerous site"
PHISH_TXT = "trick you into installing"
MALWARE_TXT = "install harmful software"

CASES = [
    # (id, url, expected)
    ("local_safe_control", f"http://127.0.0.1:{PORT}/{CANARY_DIR}/safe.html", "loaded"),
    ("local_phishing_canary", f"http://127.0.0.1:{PORT}/{CANARY_DIR}/phishing.html", "blocked_phishing"),
    ("local_malware_canary", f"http://127.0.0.1:{PORT}/{CANARY_DIR}/malware.html", "blocked_malware"),
    ("google_test_phishing", "https://testsafebrowsing.appspot.com/s/phishing.html", "blocked_phishing"),
    ("google_test_malware", "https://testsafebrowsing.appspot.com/s/malware.html", "blocked_malware"),
    ("example_com", "https://example.com/", "loaded"),
]
MARKERS = {
    "local_safe_control": "SWIFTRA_CANARY_SAFE_LOADED",
    "local_phishing_canary": "SWIFTRA_CANARY_PHISHING_LOADED",
    "local_malware_canary": "SWIFTRA_CANARY_MALWARE_LOADED",
    "example_com": "Example Domain",
    # Google's test pages render a short body; if they load, the heading is absent.
    "google_test_phishing": "",
    "google_test_malware": "",
}


def adb(*args, timeout=30):
    try:
        return subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        return ""


def serve(root):
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=root, **k)  # noqa: E731
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    srv.RequestHandlerClass.log_message = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def make_site():
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, CANARY_DIR))
    for name in ("safe", "phishing", "malware"):
        marker = f"SWIFTRA_CANARY_{name.upper()}_LOADED"
        with open(os.path.join(root, CANARY_DIR, name + ".html"), "w", encoding="utf-8") as f:
            f.write(f"<!doctype html><title>{marker}</title><h1>{marker}</h1>")
    return root


def targets(devtools):
    try:
        with urllib.request.urlopen(devtools + "/json/list", timeout=10) as r:
            return json.load(r)
    except Exception:
        return []


def page_text(devtools, url):
    """title + innerText of the newest page target whose URL is |url| (DevTools)."""
    import websocket  # websocket-client (installed by the workflow)
    for t in targets(devtools):
        if t.get("type") == "page" and t.get("url", "").rstrip("/") == url.rstrip("/") and t.get("webSocketDebuggerUrl"):
            try:
                ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=10)
                ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
                    "expression": "document.title + '\\n' + (document.body ? document.body.innerText : '')", "returnByValue": True}}))
                for _ in range(20):
                    m = json.loads(ws.recv())
                    if m.get("id") == 1:
                        ws.close()
                        return m.get("result", {}).get("result", {}).get("value", "") or ""
                ws.close()
            except Exception as e:  # noqa: BLE001
                return f"<devtools error {e}>"
    return None


def ui_text():
    adb("shell", "uiautomator", "dump", "/sdcard/shield.xml", timeout=40)
    xml = adb("shell", "cat", "/sdcard/shield.xml", timeout=20)
    return " ".join(re.findall(r'(?:text|content-desc)="([^"]+)"', xml))


def classify(text, marker):
    if HEADING in text and PHISH_TXT in text:
        return "blocked_phishing"
    if HEADING in text and MALWARE_TXT in text:
        return "blocked_malware"
    if HEADING in text:
        return "blocked_other"
    if marker and marker in text:
        return "loaded"
    return "loaded" if not marker and text.strip() else "unknown"


def wait_list(timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        log = adb("logcat", "-d", "-s", "cr_SwiftraShield:*", "SwiftraShield:*", timeout=30)
        m = re.search(r"list (updated|loaded): (\d+) entries", log)
        if m:
            return {"ready": True, "how": m.group(1), "entries": int(m.group(2)), "seconds": round(time.time() - t0, 1), "log": log[-1500:]}
        time.sleep(3)
    return {"ready": False, "seconds": timeout, "log": adb("logcat", "-d", "-s", "cr_SwiftraShield:*", "SwiftraShield:*")[-3000:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--devtools", default="http://127.0.0.1:9222")
    ap.add_argument("--list-timeout", type=int, default=180)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    srv = serve(make_site())
    adb("reverse", f"tcp:{PORT}", f"tcp:{PORT}")
    res = {"package": a.package, "cases": []}

    # 1) first check -> handler install + list download
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", CASES[0][1], a.package, timeout=40)
    res["list"] = wait_list(60)  # informational; pass/fail is decided by behaviour below
    print("list:", {k: v for k, v in res["list"].items() if k != "log"})

    # 2) readiness by behaviour (the log line may have rolled out of the buffer if the list was
    #    downloaded earlier in the journey): re-open the phishing canary until it is blocked.
    t0, ready = time.time(), None
    while time.time() - t0 < a.list_timeout:
        adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", CASES[1][1], a.package, timeout=40)
        time.sleep(6)
        text = page_text(a.devtools, CASES[1][1]) or ui_text()
        if classify(text, MARKERS["local_phishing_canary"]) == "blocked_phishing":
            ready = round(time.time() - t0, 1)
            break
    res["blocking_ready_after_s"] = ready
    print("blocking ready after s:", ready)

    ok = ready is not None
    for cid, url, expected in CASES:
        adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url, a.package, timeout=40)
        got, text, src = "unknown", "", ""
        for _ in range(8):  # up to ~24 s for network pages
            time.sleep(3)
            text = page_text(a.devtools, url)
            src = "devtools"
            if not text:
                text, src = ui_text(), "uiautomator"
            got = classify(text or "", MARKERS[cid])
            if got != "unknown" and (got == expected or got.startswith("blocked")):
                break
        with open(os.path.join(a.out, f"{cid}.png"), "wb") as f:
            f.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=20).stdout)
        passed = got == expected
        ok = ok and passed
        res["cases"].append({"id": cid, "url": url, "expected": expected, "got": got, "pass": passed, "source": src,
                             "text_head": (text or "")[:300]})
        print(f"{cid}: expected={expected} got={got} ({src}) {'PASS' if passed else 'FAIL'}")

    res["pass"] = ok
    with open(os.path.join(a.out, "shield_e2e.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    srv.shutdown()
    print("SHIELD_E2E", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
