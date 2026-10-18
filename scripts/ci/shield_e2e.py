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


DL_DIR = f"{CANARY_DIR}/download"
DL_REDIRECT = f"/{DL_DIR}/redirect.zip"          # not listed; 302 -> the listed canary (redirect chain check)
DL_HITS = []                                      # paths of download requests the runner served


class SiteHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith(f"/{DL_DIR}/"):
            DL_HITS.append(self.path)
        if self.path.split("?")[0] == DL_REDIRECT:
            self.send_response(302)
            self.send_header("Location", f"/{DL_DIR}/swiftra-canary.zip")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        return super().do_GET()


def serve(root):
    handler = lambda *a, **k: SiteHandler(*a, directory=root, **k)  # noqa: E731
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    SiteHandler.log_message = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def make_site():
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, CANARY_DIR))
    for name in ("safe", "phishing", "malware"):
        marker = f"SWIFTRA_CANARY_{name.upper()}_LOADED"
        with open(os.path.join(root, CANARY_DIR, name + ".html"), "w", encoding="utf-8") as f:
            f.write(f"<!doctype html><title>{marker}</title><h1>{marker}</h1>")
    # patches/0015 Download Shield: harmless zip bytes + a page that starts an <a download> (no navigation, so the
    # Shield navigation check does not see it; only the download URL check does)
    os.makedirs(os.path.join(root, DL_DIR))
    for name in ("swiftra-canary.zip", "clean.zip"):
        with open(os.path.join(root, DL_DIR, name), "wb") as f:
            f.write(b"PK\x05\x06" + b"\x00" * 18)   # empty zip archive (end-of-central-directory record only)
    with open(os.path.join(root, CANARY_DIR, "dl.html"), "w", encoding="utf-8") as f:
        f.write(DL_PAGE)
    # c2d: an ordinary address form - Chromium's Autofill asks content-autofill.googleapis.com about such forms
    with open(os.path.join(root, CANARY_DIR, "form.html"), "w", encoding="utf-8") as f:
        f.write(FORM_HTML)
    return root


FORM_HTML = """<!doctype html><meta name="viewport" content="width=device-width"><title>SWIFTRA_FORM</title>
<form action="/submit" method="post">
<input name="name" autocomplete="name" placeholder="Full name"><input name="email" type="email" autocomplete="email">
<input name="tel" type="tel" autocomplete="tel"><input name="address" autocomplete="street-address">
<input name="city" autocomplete="address-level2"><input name="zip" autocomplete="postal-code">
<input name="country" autocomplete="country-name"><button>Send</button></form>"""
FORM_URL = f"http://127.0.0.1:{PORT}/{CANARY_DIR}/form.html"
DL_PAGE = """<!doctype html><meta name="viewport" content="width=device-width"><title>SWIFTRA_DL_PAGE</title>
<h1>Swiftra download test</h1><a id="a" download>download</a><script>
const f = new URLSearchParams(location.search).get('f');
const a = document.getElementById('a');
a.href = f === 'redirect' ? '/__swiftra_shield_canary__/download/redirect.zip'
       : '/__swiftra_shield_canary__/download/' + (f === 'canary' ? 'swiftra-canary.zip' : 'clean.zip');
a.download = (f === 'clean' ? 'swiftra-clean' : 'swiftra-' + f) + '-' + Date.now() + '.zip';
setTimeout(() => a.click(), 800);
</script>"""
# Android DangerousDownloadDialog (android_chrome_strings.grd @155): IDS_DANGEROUS_DOWNLOAD_DIALOG_TITLE
DL_DIALOG_TITLE = "File might be harmful"
DL_CASES = [("canary", "blocked_dialog"), ("redirect", "blocked_dialog"), ("clean", "downloaded")]
# c2d (patches/0009): requests that cannot work without a Google API key, or are logging only, must be gone
NO_KEY_HOSTS = ("content-autofill.googleapis.com", "discover-pa.googleapis.com")
QUIET_PATHS = ("/async/ddllog",)
# accounts.google.com/ListAccounts is allowed only together with AI Mode's eligibility check (/async/folae):
# AimEligibilityService drops that request while the cookie jar is stale (drop_request_if_cookies_stale=true @155),
# so this one fetch belongs to a working feature. Unpaired ListAccounts is checked in startup_netlog.py.


def quiet_violations(requests):
    """Request keys ("METHOD url") that patches/0009 should have removed."""
    return sorted(k for k in (requests or {})
                  if any(f"://{h}/" in k for h in NO_KEY_HOSTS) or any(q in k for q in QUIET_PATHS))


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


def screenshot(path):
    """Never let a hung `adb exec-out screencap` abort a test (speed A/A run 39132154988 lost its result to one)."""
    try:
        r = subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=20)
        if r.stdout:
            with open(path, "wb") as f:
                f.write(r.stdout)
            return True
    except (subprocess.TimeoutExpired, OSError):
        pass
    return False


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


def dl_nodes():
    adb("shell", "uiautomator", "dump", "/sdcard/dl.xml", timeout=40)
    xml = adb("shell", "cat", "/sdcard/dl.xml", timeout=20)
    return [(m.group(1), (int(m.group(2)) + int(m.group(4))) // 2, (int(m.group(3)) + int(m.group(5))) // 2)
            for m in re.finditer(r'<node [^>]*?text="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)]


def dl_tap(nodes, label):
    for t, x, y in nodes:
        if t == label:
            adb("shell", "input", "tap", str(x), str(y))
            return True
    return False


def downloads_listing():
    return adb("shell", "ls", "/sdcard/Download/", timeout=20)


def download_case(package, case, expected, out):
    """<a download> from a local page; dangerous URL -> DangerousDownloadDialog, Cancel -> no file."""
    since = len(DL_HITS)
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d",
        f"http://127.0.0.1:{PORT}/{CANARY_DIR}/dl.html?f={case}", package, timeout=40)
    t0, dialog, texts, taps = time.time(), False, [], []
    while time.time() - t0 < 25:
        nodes = dl_nodes()
        texts = [t for t, _, _ in nodes if t]
        if DL_DIALOG_TITLE in texts:
            dialog = True
            break
        # first-download prompts (download location / notification permission): never the danger dialog's buttons
        for label in ("Download", "Don't allow", "Don\u2019t allow"):
            if dl_tap(nodes, label):
                taps.append(label)
                break
        if case == "clean" and f"swiftra-{case}" in downloads_listing() and time.time() - t0 > 6:
            break
        time.sleep(1.5)
    screenshot(os.path.join(out, f"download_{case}.png"))
    if dialog:
        taps.append("Cancel" if dl_tap(dl_nodes(), "Cancel") else "Cancel(not found)")
        time.sleep(3)
    listing = downloads_listing()
    files = [ln for ln in listing.split() if ln.startswith(f"swiftra-{case}")]
    complete = [x for x in files if not x.endswith(".crdownload") and not x.startswith(".")]
    served = DL_HITS[since:]
    if not served:
        verdict = "no_request"
    elif dialog and not complete:
        verdict = "blocked_dialog"
    elif dialog:
        verdict = "dialog_but_file_kept"
    elif complete:
        verdict = "downloaded"
    else:
        verdict = "no_result"
    return {"case": case, "expected": expected, "verdict": verdict, "pass": verdict == expected, "dialog": dialog,
            "files": files, "served": served, "taps": taps, "texts": texts[:25]}


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
    screenshot(os.path.join(out, f"safe_browsing_{mode.split()[0].lower()}.png"))
    page_text_ = [n["text"] for n in ns if n["text"]]
    back = to_browser(package)
    return {"set": checked, "log": log, "page_text": page_text_[:150], "back_to_browser": back}


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


def internal_text(devtools, url_prefix, expression=None):
    for t in targets(devtools):
        if t.get("type") == "page" and t.get("url", "").startswith(url_prefix):
            return page_text(devtools, t["url"], expression)
    return None


# components/webui/chrome_urls/resources/app.ts @155: <chrome-urls-app>, cr-button "Enable internal debugging pages"
ENABLE_DEBUG_PAGES_JS = r"""(() => {
  const app = document.querySelector('chrome-urls-app');
  const b = app && app.shadowRoot && app.shadowRoot.querySelector('cr-button');
  if (!b) return 'no button';
  const label = b.textContent.trim();
  if (/^Enable/.test(label)) { b.click(); return 'clicked: ' + label; }
  return 'already: ' + label;
})()"""
ALL_TEXT_JS = "document.body ? document.body.textContent : ''"


def enable_debug_pages(devtools):
    """chrome://safe-browsing etc. are gated by the 'internal debugging pages' pref (CI emulator only)."""
    r = open_internal(devtools, "chrome://chrome-urls/")
    time.sleep(3)
    return f"{r}; " + str(internal_text(devtools, "chrome://chrome-urls", ENABLE_DEBUG_PAGES_JS))


CHROME_WORD = re.compile(r"\bChrome\b(?!\s*(?:Web Store|OS\b))")


# ---------- c2c: Settings truthfulness (patches/0002 FACT_FIXES + 0008) ----------
# Safe Browsing page: radio summaries (android_chrome_strings.grd, replaced by Chrome's desktop subtitles)
SB_PAGE_EXPECT = ("Protects you from sites, downloads, and extensions that are known to be dangerous",
                  "Real-time, proactive protection by sending more information to Google Safe Browsing")
SB_PAGE_FALSE = ("bits of page content are sent to Google Safe Browsing", "AI-powered")
# Enhanced protection details page (enhanced_protection_preferences.xml): undeliverable benefit claims hidden,
# data disclosures (bullet_six, bullet_seven) kept
ESB_DETAILS_FALSE = ("In-depth scans for suspicious downloads", "protects you across Google services",
                     "keeps your data private")
ESB_DETAILS_EXPECT = ("Sends the URLs of sites you visit", "this data is linked to your Google Account")


def sb_page_truth(page_text):
    t = " ".join(page_text or [])
    found_false = [x for x in SB_PAGE_FALSE if x in t]
    missing = [x for x in SB_PAGE_EXPECT if x not in t]
    return {"false_claims": found_false, "missing_expected": missing, "pass": not found_false and not missing}


def esb_details(package, out):
    """menu -> Settings -> Privacy and security -> Safe Browsing -> (Enhanced) expand arrow -> details page."""
    adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "https://example.com/", package, timeout=40)
    time.sleep(4)
    to_browser(package)
    ns, _ = ui_nodes()
    menu = [n for n in ns if n["id"].endswith(":id/menu_button")]
    if not menu:
        return {"pass": False, "log": ["menu_button not found"]}
    tap(menu[0]); time.sleep(1.5)
    log = []
    for step in ("Settings", "Privacy and security", "Safe Browsing"):
        n, _ = find_text(step, scrolls=3 if step == "Settings" else 5)
        if not n:
            return {"pass": False, "log": log + [f"not found: {step}"]}
        tap(n); log.append(f"tap: {step}"); time.sleep(2.5)
    ns, _ = ui_nodes()
    title = [n for n in ns if n["text"] == "Enhanced protection"]
    arrows = [n for n in ns if n["id"].endswith(":id/expand_arrow")]
    if not title or not arrows:
        return {"pass": False, "log": log + ["expand arrow not found"]}
    arrow = min(arrows, key=lambda n: abs(n["cy"] - title[-1]["cy"]))
    tap(arrow); log.append("tap: expand_arrow (Enhanced)"); time.sleep(3)
    texts = []
    for k in range(4):   # the page is longer than one screen
        ns, xml = ui_nodes()
        with open(os.path.join(out, f"esb_details_{k}.xml"), "w", encoding="utf-8") as f:
            f.write(xml)
        screenshot(os.path.join(out, f"esb_details_{k}.png"))
        texts += [n["text"] for n in ns if n["text"] and n["text"] not in texts]
        adb("shell", "input", "swipe", "540", "1700", "540", "700", "400"); time.sleep(1.2)
    t = " ".join(texts)
    false_ = [x for x in ESB_DETAILS_FALSE if x in t]
    missing = [x for x in ESB_DETAILS_EXPECT if x not in t]
    back = to_browser(package)
    return {"pass": not false_ and not missing, "false_claims": false_, "missing_expected": missing,
            "texts": texts[:40], "log": log, "back_to_browser": back}


# ---------- c2c: variations source (args.gn disable_fieldtrial_testing_config) ----------
VERSION_JS = r"""(() => {
  const q = s => document.querySelector(s);
  const sec = q('#variations-source-section');
  return JSON.stringify({
    source: ((q('#variations-source') || {}).textContent || '').trim(),
    source_hidden: sec ? sec.hidden : null,
    variations_chars: ((q('#variations-list') || {}).textContent || '').trim().length,
    cmd_chars: ((q('#variations-cmd') || {}).textContent || '').trim().length,
    cmd: ((q('#variations-cmd') || {}).textContent || '').trim().slice(0, 60000),
    version: ((q('#version') || {}).textContent || '').trim().slice(0, 80)});
})()"""


def variations_state(devtools):
    # ?show-variations-cmd fills #variations-cmd with --force-fieldtrials=Study/Group/... (plain text)
    r = open_internal(devtools, "chrome://version/?show-variations-cmd")
    time.sleep(3)
    raw = internal_text(devtools, "chrome://version", VERSION_JS)
    try:
        v = json.loads(raw) if raw else None
    except ValueError:
        v = None
    if not isinstance(v, dict):
        return {"open": r, "pass": False, "error": "chrome://version not readable", "raw": str(raw)[:200]}
    v["open"] = r
    # 0016 Speed Pack: the testing config may be active, but only with the audited studies (speedpack_check.py)
    from speedpack_check import verdict as speedpack_verdict
    sp = speedpack_verdict(v.get("source", ""), v.get("cmd", ""))
    v["speedpack"] = sp
    v["cmd"] = v.get("cmd", "")[:3000]
    v["pass"] = sp["verdict"] in ("no_testing_config", "speedpack_only")
    return v


# ---------- c2c: browser-process network audit (CDP Tracing, NetLog category) ----------
# NetworkService installs net::TraceNetLogObserver; with the "disabled-by-default-netlog" category on, every
# URL request / host resolution of the browser process (Safe Browsing pings included) becomes a trace event.
GOOGLE_SUFFIXES = ("google.com", "googleapis.com", "gstatic.com", "gvt1.com", "gvt2.com", "googleusercontent.com",
                   "google-analytics.com", "doubleclick.net", "googlesyndication.com", "ggpht.com", "youtube.com",
                   "1e100.net", "googleadservices.com", "app-measurement.com", "android.com", "googlevideo.com")
SB_HOSTS = ("safebrowsing.google.com", "sb-ssl.google.com", "safebrowsing.googleapis.com",
            "androidchromeprotect.pa.googleapis.com", "sb.google.com")
USER_PAGE_HOSTS = ("example.com", "testsafebrowsing.appspot.com", "127.0.0.1", "localhost")
HOST_RX = re.compile(r'(?:https?|wss?)://([A-Za-z0-9.-]+)(?::\d+)?[/"?]|"host":\s*"([A-Za-z0-9.-]+)')


def is_google(h):
    return any(h == s or h.endswith("." + s) for s in GOOGLE_SUFFIXES)


def netlog_trace(devtools, actions, settle=8):
    """Run actions() while the browser records NetLog trace events; return {host: count, ...} + URL samples."""
    import websocket
    ws_url = browser_ws(devtools)
    if not ws_url:
        return {"ok": False, "error": "no browser websocket"}
    try:
        ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True, enable_multithread=True)
        ws.send(json.dumps({"id": 1, "method": "Tracing.start", "params": {
            "transferMode": "ReportEvents",
            "traceConfig": {"recordMode": "recordContinuously",
                            "includedCategories": ["disabled-by-default-netlog", "netlog"]}}}))
        start_reply = None
        for _ in range(50):
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                start_reply = m
                break
        if not start_reply or "error" in start_reply:
            ws.close()
            return {"ok": False, "error": "Tracing.start: " + json.dumps(start_reply)[:200]}
        t0 = time.time()
        actions()
        time.sleep(settle)
        ws.send(json.dumps({"id": 2, "method": "Tracing.end"}))
        events, done = 0, False
        hosts, urls = {}, set()
        requests, resolves, google_events = {}, {}, {}
        ws.settimeout(60)
        while not done:
            m = json.loads(ws.recv())
            meth = m.get("method")
            if meth == "Tracing.dataCollected":
                for ev in m["params"].get("value", []):
                    events += 1
                    args = ev.get("args", {}) or {}
                    blob = json.dumps(args)
                    name = str(ev.get("name", ""))
                    params = args.get("params") if isinstance(args.get("params"), dict) else {}
                    evh = set()
                    for a1, a2 in HOST_RX.findall(blob):
                        h = (a1 or a2).lower().rstrip(".")
                        if h:
                            hosts[h] = hosts.get(h, 0) + 1
                            evh.add(h)
                    for u in re.findall(r'https?://[^"\s\\]+', blob):
                        if len(urls) < 400:
                            urls.add(u.split("?")[0][:160])
                    # real network requests (URLRequest jobs) vs. mere mentions (socket pools, server properties...)
                    if name == "URL_REQUEST_START_JOB" and isinstance(params.get("url"), str):
                        k = f"{params.get('method', '?')} {params['url'].split('?')[0][:160]}"
                        requests[k] = requests.get(k, 0) + 1
                    if name.startswith("HOST_RESOLVER") and isinstance(params.get("host"), str):
                        resolves[params["host"]] = resolves.get(params["host"], 0) + 1
                    if any(is_google(h) for h in evh):
                        google_events[name] = google_events.get(name, 0) + 1
            elif meth == "Tracing.tracingComplete":
                done = True
        ws.close()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    google = {h: c for h, c in hosts.items() if is_google(h) and h not in USER_PAGE_HOSTS
              and not h.endswith("appspot.com")}
    req_google = {k: c for k, c in requests.items()
                  if is_google(re.sub(r"^\S+ \w+://([^/:]+).*$", r"\1", k)) and "testsafebrowsing.appspot.com" not in k}
    return {"ok": events > 0, "events": events, "seconds": round(time.time() - t0, 1), "hosts": hosts,
            "requests": dict(sorted(requests.items())[:200]), "google_requests": req_google,
            "resolves": resolves, "google_event_types": google_events,
            "google_hosts": google, "sb_hosts": sorted(h for h in hosts if h in SB_HOSTS),
            "google_urls": sorted(u for u in urls if is_google(re.sub(r"^\w+://([^/:]+).*$", r"\1", u))
                                  and "testsafebrowsing.appspot.com" not in u)[:60]}


def run_case(a, cid, url, expected, marker, native_ui_check=False):
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
    screenshot(os.path.join(a.out, f"{cid}.png"))
    passed = got == expected
    rec = {"id": cid, "url": url, "expected": expected, "got": got, "pass": passed, "source": src,
           "text_head": (text or "")[:300]}
    if got.startswith("blocked"):
        h = honesty(a.devtools, url)
        rec["honesty"] = h
        if h is None or not h["pass"]:
            rec["pass"] = passed = False
    if native_ui_check:
        # native Android UI (message banners, e.g. "Enhanced protection is on") is invisible to DevTools
        ui = ui_text()
        hits = sorted(set(m.group(0) for m in re.finditer(r"[^\n]{0,60}\bChrome\b[^\n]{0,60}", ui)
                          if CHROME_WORD.search(m.group(0))))
        rec["native_ui_chrome_hits"] = hits
        if hits:
            rec["pass"] = passed = False
    hp = rec.get("honesty") or {}
    print(f"{cid}: expected={expected} got={got} ({src}) honesty={hp.get('problems', '-')} "
          f"native_chrome={rec.get('native_ui_chrome_hits', '-')} "
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

    # c2c: variations source must not be the field-trial testing config (args.gn)
    res["variations"] = variations_state(a.devtools)
    print("variations:", {k: v for k, v in res["variations"].items() if k != "raw"})
    ok = ok and res["variations"]["pass"]

    # patches/0015 Download Shield (reported separately until the 0015 APK is built: DOWNLOAD_SHIELD_E2E)
    res["download_shield"] = [download_case(a.package, c, e, a.out) for c, e in DL_CASES]
    for r_ in res["download_shield"]:
        print("download shield:", {k: v for k, v in r_.items() if k != "texts"})

    # c2c: Standard protection network audit (browser process, NetLog trace): local pages + example.com + idle
    def standard_actions():
        for u in (CASES[0][1], "https://example.com/", FORM_URL, CASES[1][1]):
            adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", u, a.package, timeout=40)
            time.sleep(6)
        time.sleep(30)
    res["net_standard"] = netlog_trace(a.devtools, standard_actions)
    ns_ = res["net_standard"]
    print("net standard:", {k: v for k, v in ns_.items() if k not in ("hosts", "google_urls", "requests", "resolves", "google_hosts")})

    # 3) Enhanced protection through the Settings UI, then the same kind of checks
    if not a.skip_esb:
        esb = set_safe_browsing(a.package, "Enhanced protection", a.out)
        print("enhanced protection:", {k: v for k, v in esb.items() if k != "page_text"})
        res["esb"] = esb
        ok = ok and esb["set"]
        # c2c: Safe Browsing page summaries (both radios are on the page)
        esb["sb_page_truth"] = sb_page_truth(esb.get("page_text"))
        print("sb page truth:", esb["sb_page_truth"])
        ok = ok and esb["sb_page_truth"]["pass"]
        if esb["set"]:
            res["esb_details"] = esb_details(a.package, a.out)
            print("esb details:", {k: v for k, v in res["esb_details"].items() if k != "texts"})
            ok = ok and res["esb_details"]["pass"]
        if esb["set"]:
            esb["debug_pages"] = enable_debug_pages(a.devtools)
            time.sleep(2)
            esb["rt_page_open"] = open_internal(a.devtools, "chrome://safe-browsing/#tab-rt-lookup")
            time.sleep(3)
            esb_recs = []

            def esb_actions():
                for cid, url, expected in ESB_CASES:
                    esb_recs.append(run_case(a, cid, url, expected, MARKERS.get(cid[4:], ""), native_ui_check=True))
            res["net_enhanced"] = netlog_trace(a.devtools, esb_actions)
            for rec in esb_recs:
                ok = ok and rec["pass"]
                res["cases"].append(rec)
            ne_ = res["net_enhanced"]
            print("net enhanced:", {k: v for k, v in ne_.items() if k not in ("hosts", "google_urls", "requests", "resolves", "google_hosts")})
            rt = internal_text(a.devtools, "chrome://safe-browsing", ALL_TEXT_JS) or ""
            esb["rt_lookup_page"] = {"chars": len(rt),
                                     "mentions_public_canary": "swiftra_shield_canary" in rt,
                                     "mentions_unwanted": "unwanted.html" in rt, "head": rt[:1500],
                                     "rt_context": [rt[max(0, m.start() - 200):m.end() + 300]
                                                    for m in re.finditer(r"swiftra_shield_canary|unwanted\.html", rt)][:4]}
            esb["components_open"] = open_internal(a.devtools, "chrome://components/")
            time.sleep(3)
            comp = internal_text(a.devtools, "chrome://components") or ""
            esb["components"] = [l.strip() for l in comp.splitlines() if re.search(r"(?i)safe|allowlist|real.?time", l)][:20]
            # Standard-protection claim "if a page does something suspicious, URLs and page content are sent to
            # Google Safe Browsing" depends on the client-side phishing model (optimization guide) being present
            esb["optguide_open"] = open_internal(a.devtools, "chrome://optimization-guide-internals/")
            time.sleep(4)
            og = internal_text(a.devtools, "chrome://optimization-guide-internals", ALL_TEXT_JS) or ""
            esb["optimization_guide"] = {"chars": len(og), "head": og[:800], "model_lines": sorted(set(
                l.strip()[:200] for l in og.splitlines() if re.search(r"(?i)phish|client.?side|CLIENT_SIDE|model", l)))[:30]}
            print("debug pages:", esb["debug_pages"])
            print("optimization guide:", esb["optimization_guide"]["chars"], esb["optimization_guide"]["model_lines"][:8])
            print("rt lookup page:", {k: v for k, v in esb["rt_lookup_page"].items() if k not in ("head", "rt_context")})
            print("components:", esb["components"])
        back = set_safe_browsing(a.package, "Standard protection", a.out)   # leave the device as found
        res["esb_restore_standard"] = {k: v for k, v in back.items() if k != "page_text"}

    # c2c network verdict: Standard must not contact a Safe Browsing endpoint. The Enhanced window is the
    # positive control (real-time lookups to Google must show up), so an empty Standard result is meaningful.
    ns_, ne_ = res.get("net_standard", {}), res.get("net_enhanced", {})
    control = bool(ne_.get("ok") and ne_.get("sb_hosts"))
    if ns_.get("ok") and ns_.get("sb_hosts"):
        verdict = "sb_contact_in_standard"
    elif ns_.get("ok") and control:
        verdict = "clean"
    else:
        verdict = "inconclusive"
    quiet = quiet_violations(ns_.get("requests"))
    if ns_.get("ok") and quiet and verdict != "sb_contact_in_standard":
        verdict = "no_key_or_logging_request"
    res["net_audit"] = {"verdict": verdict, "positive_control": control, "quiet_violations": quiet,
                        "standard_google_hosts": sorted(ns_.get("google_hosts", {})),
                        "standard_google_requests": ns_.get("google_requests"),
                        "standard_requests_total": sum((ns_.get("requests") or {}).values()),
                        "enhanced_sb_hosts": ne_.get("sb_hosts")}
    print("net audit:", res["net_audit"])
    ok = ok and verdict not in ("sb_contact_in_standard", "no_key_or_logging_request")

    res["pass"] = ok
    with open(os.path.join(a.out, "shield_e2e.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    srv.shutdown()
    print("SHIELD_E2E", "PASS" if ok else "FAIL")
    ds = res.get("download_shield") or []
    print("DOWNLOAD_SHIELD_E2E", "PASS" if ds and all(r_["pass"] for r_ in ds) else ("NOT_RUN" if not ds else "FAIL"),
          " ".join(f"{r_['case']}={r_['verdict']}" for r_ in ds))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
