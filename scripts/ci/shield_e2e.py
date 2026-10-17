#!/usr/bin/env python3
"""Swiftra Shield end-to-end check on an Android emulator / Redroid (patches/0006).

Flow (all inside CI; no real malicious site is contacted):
  1. Local canary server (127.0.0.1:8001 via `adb reverse`) serves phishing/malware/safe pages whose
     body is a unique marker. The phishing/malware paths are canaries baked into the signed list.
  2. The handler is installed at browser startup (ProcessInitializationHandler -> initSafeBrowsingApi)
     and downloads + verifies the signed list in the background. Readiness is measured by behaviour
     (phishing canary blocked); logcat "SwiftraShield ... list updated|loaded" is recorded if present.
  3. Open each case in the browser; read the page through DevTools (title + innerText), fall back to a
     uiautomator dump. Classify: loaded (marker visible) / blocked_phishing / blocked_malware.
  4. Google's harmless test pages (testsafebrowsing.appspot.com, user permission 2026-10-17) and
     example.com are checked the same way.
  5. Honesty (patches/0002 + 0007): on every blocked page the text must not say "Chrome" or
     "Google Safe Browsing", must not carry the Google diagnostic / report-error links, and the
     details section must still hold the risk warning + proceed link.
  6. Enhanced protection (switched on through the real Settings UI): the Shield-only public canary
     (Google rates it SAFE) must still be blocked (patches/0007), Google's unwanted-software test page
     must now be blocked (= Google real-time protection is really active), example.com must load.
     chrome://safe-browsing (RT lookup pings) and chrome://components are recorded (informational).
Exit 0 only if every expectation holds. Writes <out>/shield_e2e.json + one screenshot per case.
"""
import argparse
import http.server
import xml.etree.ElementTree as ET
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
HARMFUL_TXT = "affects the way you browse"   # checked first: also contains PHISH_TXT
TSB = "https://testsafebrowsing.appspot.com/s"

CASES = [
    # (id, url, expected)
    ("local_safe_control", f"http://127.0.0.1:{PORT}/{CANARY_DIR}/safe.html", "loaded"),
    ("local_phishing_canary", f"http://127.0.0.1:{PORT}/{CANARY_DIR}/phishing.html", "blocked_phishing"),
    ("local_malware_canary", f"http://127.0.0.1:{PORT}/{CANARY_DIR}/malware.html", "blocked_malware"),
    ("google_test_phishing", "https://testsafebrowsing.appspot.com/s/phishing.html", "blocked_phishing"),
    ("google_test_malware", "https://testsafebrowsing.appspot.com/s/malware.html", "blocked_malware"),
    ("example_com", "https://example.com/", "loaded"),
    # c2b: Shield canary on a public host (Google RT says SAFE; see scripts/shield/build_shield_db.py)
    ("public_shield_canary", f"{TSB}/swiftra_shield_canary.html", "blocked_phishing"),
    # Standard protection = Shield only, which has no unwanted-software list (honest baseline)
    ("google_test_unwanted", f"{TSB}/unwanted.html", "loaded"),
]
MARKERS = {
    "local_safe_control": "SWIFTRA_CANARY_SAFE_LOADED",
    "local_phishing_canary": "SWIFTRA_CANARY_PHISHING_LOADED",
    "local_malware_canary": "SWIFTRA_CANARY_MALWARE_LOADED",
    "example_com": ("Example Domain", "documentation examples"),
    # Google's test pages render a short body; if they load, the heading is absent.
    "google_test_phishing": "",
    "google_test_malware": "",
    "public_shield_canary": "",   # if not blocked: the host's 404 page
    "google_test_unwanted": "",
}

# Enhanced protection run (same pages, ids prefixed "esb_"; marker = MARKERS of the base id)
ESB_CASES = [
    ("esb_local_phishing_canary", CASES[1][1], "blocked_phishing"),   # private IP -> no RT, Shield DB
    ("esb_public_shield_canary", f"{TSB}/swiftra_shield_canary.html", "blocked_phishing"),  # RT SAFE + Shield
    ("esb_google_test_phishing", f"{TSB}/phishing.html", "blocked_phishing"),
    ("esb_google_test_unwanted", f"{TSB}/unwanted.html", "blocked_harmful"),  # Google RT only
    ("esb_example_com", "https://example.com/", "loaded"),
]

# Honesty probe on a blocked page (main + details text incl. the hidden details section)
HONESTY_JS = r"""(() => {
  const q = s => document.querySelector(s);
  const txt = ['#main-content', '#details'].map(s => (q(s) || {}).textContent || '').join(' ');
  const html = document.documentElement.outerHTML;
  return JSON.stringify({
    chrome_word: /\bChrome\b/.test(txt), swiftra_word: /Swiftra/.test(txt),
    google_safe_browsing: /Google Safe Browsing/.test(txt) || /Google Safe Browsing/.test(html),
    diagnostic_link: !!q('#diagnostic-link'), report_error_link: !!q('#report-error-link'),
    google_sb_urls: /transparencyreport\.google|safebrowsing\.google\.com/.test(html),
    final_paragraph: ((q('#final-paragraph') || {}).textContent || '').trim(),
    esb_message: ((q('#enhanced-protection-message') || {}).textContent || '').trim()});
})()"""


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


def page_text(devtools, url, expression=None):
    """title + innerText of the newest page target whose URL is |url| (DevTools)."""
    import websocket  # websocket-client (installed by the workflow)
    for t in targets(devtools):
        if t.get("type") == "page" and t.get("url", "").rstrip("/") == url.rstrip("/") and t.get("webSocketDebuggerUrl"):
            try:
                ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
                ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
                    "expression": expression or "document.title + '\\n' + (document.body ? document.body.innerText : '')",
                    "returnByValue": True}}))
                for _ in range(20):
                    m = json.loads(ws.recv())
                    if m.get("id") == 1:
                        ws.close()
                        return m.get("result", {}).get("result", {}).get("value", "") or ""
                ws.close()
            except Exception as e:  # noqa: BLE001
                print(f"devtools error ({url}): {str(e)[:160]}")
                return None
    return None


def ui_text():
    adb("shell", "uiautomator", "dump", "/sdcard/shield.xml", timeout=40)
    xml = adb("shell", "cat", "/sdcard/shield.xml", timeout=20)
    return " ".join(re.findall(r'(?:text|content-desc)="([^"]+)"', xml))


def classify(text, marker):
    if HEADING in text and HARMFUL_TXT in text:
        return "blocked_harmful"
    if HEADING in text and PHISH_TXT in text:
        return "blocked_phishing"
    if HEADING in text and MALWARE_TXT in text:
        return "blocked_malware"
    if HEADING in text:
        return "blocked_other"
    markers = marker if isinstance(marker, tuple) else ((marker,) if marker else ())
    if any(m in text for m in markers):
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


# ---------- honesty ----------
def honesty(devtools, url):
    """Checks on a blocked page; None if DevTools could not read it."""
    raw = page_text(devtools, url, HONESTY_JS)
    try:
        h = json.loads(raw) if raw else None
    except ValueError:
        h = None
    if not isinstance(h, dict):
        return None
    problems = [k for k in ("chrome_word", "google_safe_browsing", "diagnostic_link", "report_error_link",
                            "google_sb_urls") if h.get(k)]
    if not h.get("swiftra_word"):
        problems.append("no_swiftra_word")
    if "understand the risks" not in h.get("final_paragraph", ""):
        problems.append("final_paragraph_missing")
    h["problems"] = problems
    h["pass"] = not problems
    return h


# ---------- Settings UI (uiautomator) ----------
def ui_nodes():
    adb("shell", "rm", "-f", "/sdcard/sb.xml")
    adb("shell", "uiautomator", "dump", "/sdcard/sb.xml", timeout=40)
    xml = adb("exec-out", "cat", "/sdcard/sb.xml", timeout=20)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return [], xml
    out = []
    for n in root.iter("node"):
        b = list(map(int, re.findall(r"\d+", n.get("bounds", "[0,0][0,0]")))) or [0, 0, 0, 0]
        out.append({"text": n.get("text", ""), "desc": n.get("content-desc", ""), "id": n.get("resource-id", ""),
                    "checkable": n.get("checkable") == "true", "checked": n.get("checked") == "true",
                    "cx": (b[0] + b[2]) // 2, "cy": (b[1] + b[3]) // 2, "h": b[3] - b[1]})
    return out, xml


def tap(n):
    adb("shell", "input", "tap", str(n["cx"]), str(n["cy"]))


def find_text(text, scrolls=5, pause=1.2):
    for k in range(scrolls + 1):
        ns, _ = ui_nodes()
        hit = [n for n in ns if n["text"] == text and n["h"] > 20]
        if hit:
            return hit[-1], ns
        if k < scrolls:
            adb("shell", "input", "swipe", "540", "1600", "540", "900", "400")
            time.sleep(pause)
    return None, []


def focused_window():
    m = re.search(r"mCurrentFocus=Window\{[^ ]+ [^ ]+ ([^}]+)\}", adb("shell", "dumpsys", "window", timeout=30))
    return m.group(1) if m else ""


def to_browser(package, tries=6):
    """BACK until the tabbed browser (toolbar menu button, no menu/settings on top) is in front."""
    for _ in range(tries):
        win = focused_window()
        ns, _ = ui_nodes()
        in_app = win.startswith(package + "/")
        overlay = "Settings" in win or any(n["id"].endswith(":id/menu_list") for n in ns)
        if in_app and not overlay and any(n["id"].endswith(":id/menu_button") for n in ns):
            return True
        adb("shell", "input", "keyevent", "4")
        time.sleep(1.5)
    return False


def set_safe_browsing(package, mode, out):
    """Real UI path: menu -> Settings -> Privacy and security -> Safe Browsing -> <mode>."""
    log = []
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "https://example.com/", package, timeout=40)
    time.sleep(5)
    to_browser(package)
    ns, _ = ui_nodes()
    menu = [n for n in ns if n["id"].endswith(":id/menu_button")]
    if not menu:
        return {"set": False, "log": ["menu_button not found"]}
    tap(menu[0]); time.sleep(1.5)
    for step in ("Settings", "Privacy and security", "Safe Browsing", mode):
        n, _ = find_text(step, scrolls=0 if step == "Settings" else 5)
        if not n and step == "Settings":   # app menu list may need a scroll
            n, _ = find_text(step, scrolls=3)
        if not n:
            log.append(f"not found: {step}")
            return {"set": False, "log": log}
        tap(n); log.append(f"tap: {step}"); time.sleep(2.5)
    ns, xml = ui_nodes()
    title = [n for n in ns if n["text"] == mode]
    radios = sorted((n for n in ns if title and n["checkable"]), key=lambda n: abs(n["cy"] - title[-1]["cy"]))
    checked = bool(radios) and abs(radios[0]["cy"] - title[-1]["cy"]) < 150 and radios[0]["checked"]
    with open(os.path.join(out, f"safe_browsing_{mode.split()[0].lower()}.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    with open(os.path.join(out, f"safe_browsing_{mode.split()[0].lower()}.png"), "wb") as f:
        f.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=20).stdout)
    page_text_ = [n["text"] for n in ns if n["text"]]
    back = to_browser(package)
    return {"set": checked, "log": log, "page_text": page_text_[:60], "back_to_browser": back}


# ---------- chrome:// pages via DevTools (informational) ----------
def browser_ws(devtools):
    try:
        with urllib.request.urlopen(devtools + "/json/version", timeout=10) as r:
            return json.load(r).get("webSocketDebuggerUrl")
    except Exception:  # noqa: BLE001
        return None


def open_internal(devtools, url):
    """Target.createTarget on the browser endpoint (chrome:// cannot be opened by an intent)."""
    import websocket
    ws_url = browser_ws(devtools)
    if not ws_url:
        return "no browser websocket"
    try:
        ws = websocket.create_connection(ws_url, timeout=10, suppress_origin=True)
        ws.send(json.dumps({"id": 1, "method": "Target.createTarget", "params": {"url": url}}))
        for _ in range(20):
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                ws.close()
                return "error: " + json.dumps(m["error"])[:200] if "error" in m else "ok"
        ws.close()
    except Exception as e:  # noqa: BLE001
        return f"error: {str(e)[:160]}"
    return "no reply"


def internal_text(devtools, url_prefix):
    for t in targets(devtools):
        if t.get("type") == "page" and t.get("url", "").startswith(url_prefix):
            return page_text(devtools, t["url"])
    return None


def run_case(a, cid, url, expected, marker):
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url, a.package, timeout=40)
    got, text, src = "unknown", "", ""
    for _ in range(8):  # up to ~24 s for network pages
        time.sleep(3)
        text = page_text(a.devtools, url)
        src = "devtools"
        if not text:
            text, src = ui_text(), "uiautomator"
        got = classify(text or "", marker)
        if got != "unknown" and (got == expected or got.startswith("blocked")):
            break
    time.sleep(2)  # let the compositor present the final frame (Redroid can show a stale one)
    with open(os.path.join(a.out, f"{cid}.png"), "wb") as f:
        f.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=20).stdout)
    passed = got == expected
    rec = {"id": cid, "url": url, "expected": expected, "got": got, "pass": passed, "source": src,
           "text_head": (text or "")[:300]}
    if got.startswith("blocked"):
        h = honesty(a.devtools, url)
        rec["honesty"] = h
        if h is None or not h["pass"]:
            rec["pass"] = passed = False
    hp = rec.get("honesty") or {}
    print(f"{cid}: expected={expected} got={got} ({src}) honesty={hp.get('problems', '-')} "
          f"{'PASS' if passed else 'FAIL'}")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--devtools", default="http://127.0.0.1:9222")
    ap.add_argument("--list-timeout", type=int, default=180)
    ap.add_argument("--skip-esb", action="store_true", help="skip the Enhanced protection part")
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
        rec = run_case(a, cid, url, expected, MARKERS[cid])
        ok = ok and rec["pass"]
        res["cases"].append(rec)

    # 3) Enhanced protection through the Settings UI, then the same kind of checks
    if not a.skip_esb:
        esb = set_safe_browsing(a.package, "Enhanced protection", a.out)
        print("enhanced protection:", {k: v for k, v in esb.items() if k != "page_text"})
        res["esb"] = esb
        ok = ok and esb["set"]
        if esb["set"]:
            esb["rt_page_open"] = open_internal(a.devtools, "chrome://safe-browsing/#tab-rt-lookup")
            time.sleep(3)
            for cid, url, expected in ESB_CASES:
                rec = run_case(a, cid, url, expected, MARKERS.get(cid[4:], ""))
                ok = ok and rec["pass"]
                res["cases"].append(rec)
            rt = internal_text(a.devtools, "chrome://safe-browsing") or ""
            esb["rt_lookup_page"] = {"chars": len(rt),
                                     "mentions_public_canary": "swiftra_shield_canary" in rt,
                                     "mentions_unwanted": "unwanted.html" in rt, "head": rt[:1500]}
            esb["components_open"] = open_internal(a.devtools, "chrome://components/")
            time.sleep(3)
            comp = internal_text(a.devtools, "chrome://components") or ""
            esb["components"] = [l.strip() for l in comp.splitlines() if re.search(r"(?i)safe|allowlist|real.?time", l)][:20]
            print("rt lookup page:", {k: v for k, v in esb["rt_lookup_page"].items() if k != "head"})
            print("components:", esb["components"])
        back = set_safe_browsing(a.package, "Standard protection", a.out)   # leave the device as found
        res["esb_restore_standard"] = {k: v for k, v in back.items() if k != "page_text"}

    res["pass"] = ok
    with open(os.path.join(a.out, "shield_e2e.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    srv.shutdown()
    print("SHIELD_E2E", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
