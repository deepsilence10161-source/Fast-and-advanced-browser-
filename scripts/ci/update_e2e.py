#!/usr/bin/env python3
"""patches/0020: Swiftra update channel, checked on the device through the real upstream menu.

The rolling release holds swiftra-update-e2e.json(+.sig): a manifest signed by publish-latest.yml with the real key
whose entries are "published" in 2100, so any installed APK sees it as newer. This script serves it on the runner
(adb reverse -> device 127.0.0.1:PORT; the update check uses Android's HttpURLConnection, not Chromium's network
stack, so --host-resolver-rules does not apply) and points the app at it with the test-only command-line switch
--swiftra-update-manifest-url (command-line file, honoured because the package is the debug app). Cases:
  bad   one byte of the manifest changed, same signature  -> no menu item, no badge (signature check works)
  good  the signed manifest as published                  -> "Update Swiftra" menu item + badge on the menu button
The menu item is never tapped (it would start a ~380 MB download).
Prints UPDATE_E2E PASS / FAIL / NOT_RUN (NOT_RUN: the app never fetched the manifest, e.g. an APK without 0020).
"""
import argparse
import http.server
import json
import os
import re
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shield_e2e import adb, screenshot  # noqa: E402
from startup_netlog import CMDLINE_FILE, resolve_launcher  # noqa: E402

PORT = 8790
REL = "https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/releases/download/swiftra/"
ITEM_TEXT = "update swiftra"
BADGE_DESC = "update available"
FILES, HITS = {}, []


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        HITS.append(self.path)
        body = FILES.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def tamper(manifest):
    """Same JSON shape, one digit of published_ms changed: the signature no longer matches."""
    m = re.search(rb'"published_ms": *(\d)', manifest)
    if not m:
        return None
    d = m.group(1)
    return manifest[:m.start(1)] + (b"3" if d != b"3" else b"2") + manifest[m.end(1):]


def ui_xml(tag, out):
    adb("shell", "uiautomator", "dump", f"/sdcard/upd_{tag}.xml", timeout=40)
    xml = adb("shell", "cat", f"/sdcard/upd_{tag}.xml", timeout=20) or ""
    with open(os.path.join(out, f"{tag}.xml"), "w") as f:
        f.write(xml)
    return xml


def node_bounds(xml, rid_suffix):
    for m in re.finditer(r'<node [^>]*>', xml):
        n = m.group(0)
        if re.search(r'resource-id="[^"]*' + re.escape(rid_suffix) + '"', n):
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
            desc = re.search(r'content-desc="([^"]*)"', n)
            if b:
                x1, y1, x2, y2 = map(int, b.groups())
                return (x1 + x2) // 2, (y1 + y2) // 2, (desc.group(1) if desc else "")
    return None


def verdict(res):
    cases = res.get("cases", {})
    if not cases or not any(c.get("fetched") for c in cases.values()):
        return "not_run"
    bad, good = cases.get("bad", {}), cases.get("good", {})
    if not (bad.get("fetched") and good.get("fetched")):
        return "fail"
    if bad.get("item") or bad.get("badge"):
        return "fail"
    return "pass" if (good.get("item") and good.get("badge")) else "fail"


def run_case(pkg, comp, name, out):
    flags = f"_ --swiftra-update-manifest-url=http://127.0.0.1:{PORT}/{name}.json"
    adb("shell", "am", "force-stop", pkg)
    adb("shell", f"echo '{flags}' > {CMDLINE_FILE} && chmod 644 {CMDLINE_FILE}")
    adb("logcat", "-c")
    n0 = len(HITS)
    adb("shell", "am", "start", "-W", "-n", comp, timeout=60) if comp else adb(
        "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
    sig_path = f"/{name}.json.sig"
    t0 = time.time()
    while time.time() - t0 < 40 and sig_path not in HITS[n0:]:
        time.sleep(1)
    fetched = f"/{name}.json" in HITS[n0:]
    time.sleep(5)                                   # status -> menu state (posted to the UI thread)
    xml = ui_xml(f"{name}_toolbar", out)
    mb = node_bounds(xml, ":id/menu_button")
    badge = bool(mb and BADGE_DESC in mb[2].lower())
    item = False
    if mb:
        adb("shell", "input", "tap", str(mb[0]), str(mb[1]))
        time.sleep(2.5)
        item = ITEM_TEXT in ui_xml(f"{name}_menu", out).lower()
        screenshot(os.path.join(out, f"{name}_menu.png"))
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
    log = adb("logcat", "-d", "-s", "SwiftraUpdate:*", "cr_SwiftraUpdate:*", timeout=30) or ""
    return {"fetched": fetched, "hits": HITS[n0:], "menu_button": bool(mb),
            "menu_desc": mb[2] if mb else None, "badge": badge, "item": item,
            "log": [l for l in log.splitlines() if "SwiftraUpdate" in l][-5:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    res = {"package": a.package}
    try:
        good, sig = fetch(REL + "swiftra-update-e2e.json"), fetch(REL + "swiftra-update-e2e.json.sig")
    except Exception as e:  # noqa: BLE001
        res["error"] = f"e2e manifest not available: {e}"
        good = sig = None
    bad = tamper(good) if good else None
    if good and sig and bad:
        FILES.update({"/good.json": good, "/good.json.sig": sig, "/bad.json": bad, "/bad.json.sig": sig})
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        adb("reverse", f"tcp:{PORT}", f"tcp:{PORT}")
        adb("shell", "am", "set-debug-app", "--persistent", a.package)
        comp = resolve_launcher(a.package)
        res["cases"] = {}
        try:
            for name in ("bad", "good"):
                res["cases"][name] = run_case(a.package, comp, name, a.out)
        finally:
            adb("shell", "am", "force-stop", a.package)
            adb("shell", "rm", "-f", CMDLINE_FILE)
            adb("reverse", "--remove", f"tcp:{PORT}")
            srv.shutdown()
    res["verdict"] = verdict(res)
    with open(os.path.join(a.out, "update_e2e.json"), "w") as f:
        json.dump(res, f, indent=1)
    c = res.get("cases", {})
    print("UPDATE_E2E", {"pass": "PASS", "fail": "FAIL"}.get(res["verdict"], "NOT_RUN"),
          " ".join(f"{k}:fetched={v.get('fetched')},item={v.get('item')},badge={v.get('badge')}" for k, v in c.items()),
          res.get("error", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
