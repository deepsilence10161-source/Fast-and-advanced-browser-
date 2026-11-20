#!/usr/bin/env python3
"""PERSONAL_FORENSIC: after the user clears browsing data, can the visited page still be read from the app's files?

User requirement (20 Nov): history deleted must not be recoverable by someone who reads the raw files ("coders ... history
nikal lete hain"). This MEASURES it; it does not claim anything about flash blocks or the OS.

Method (synthetic canary only, loopback only, no account): open http://127.0.0.1/visited_<t>/page?q=secret_<t> whose <title>
is ftitle_<t>; scan the app's data dirs with `grep -a -F` (raw bytes, so SQLite free pages, -wal/-journal, LevelDB tombstones,
cache entries and tab_state all count) for the three patterns:
  live      right after browsing (app running)       -> which stores hold the visit at all
  stopped   after force-stop (WAL flushed)            -> same, at rest
  cleared   Settings > Clear browsing data (All time, history+cookies+cache) -> force-stop -> scan again
Every line: `PERSONAL_FORENSIC <id> <STATUS> <detail>`; STATUS in INFO | CLEAN | REMNANTS | NOT_RUN. Never PASS/FAIL, never gates.
Exit 0 unless the harness itself breaks (2).
"""
import argparse
import http.server
import json
import os
import re
import secrets
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import personal_e2e as P  # noqa: E402

PORT = P.PORT
TOKEN = {"v": ""}
PAGE = "<!doctype html><meta name=viewport content='width=device-width'><title>ftitle_{t}</title><body><h1>forensic canary page</h1>"


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = PAGE.format(t=TOKEN["v"]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def data_dirs(pkg):
    return [f"/data/data/{pkg}", f"/data/user_de/0/{pkg}", f"/sdcard/Android/data/{pkg}",
            "/sdcard/Download", "/sdcard/Android/media", "/sdcard/DCIM", "/sdcard/Pictures"]


def parse_grep_files(out, pkg):
    """Lines of `grep -l` output -> sorted unique paths relative to the package dir (name only; contents never printed)."""
    files = set()
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("/") or "No such file" in line or "Permission denied" in line:
            continue
        files.add(re.sub(rf"^/data/(?:data|user_de/0)/{re.escape(pkg)}/", "", line))
    return sorted(files)


def scan(pkg, patterns):
    """{label: [relative file, ...]} for every pattern; one grep per pattern so the hit is attributable."""
    found = {}
    dirs = " ".join(d for d in data_dirs(pkg))
    for label, pat in patterns.items():
        out = P.sh(f"grep -r -a -l -F -e '{pat}' {dirs} 2>/dev/null", timeout=240)
        found[label] = parse_grep_files(out, pkg)
    return found


def size_of(pkg, rel):
    out = P.sh(f"ls -l /data/data/{pkg}/{rel} 2>/dev/null | head -1")
    m = re.search(r"\s(\d+)\s+\d{4}-\d\d-\d\d", out)
    return int(m.group(1)) if m else None


def summarize_hits(found):
    allfiles = sorted({f for v in found.values() for f in v})
    return {"files": allfiles, "by_pattern": {k: len(v) for k, v in found.items()}}


def clear_all_time(dev, pkg):
    """Drive Settings > Clear browsing data. Returns (ok, detail). ok only if the Clear button was really pressed."""
    for frag in ("org.chromium.chrome.browser.browsing_data.ClearBrowsingDataTabsFragment",
                 "org.chromium.chrome.browser.browsing_data.ClearBrowsingDataFragment"):
        P.adb("shell", "am", "start", "-W", "-n", f"{pkg}/org.chromium.chrome.browser.settings.SettingsActivity",
              "--es", "show_fragment", frag, timeout=60)
        time.sleep(4)
        if dev.find(r"(?i)clear data|time range", ("text", "desc", "id")):
            break
    else:
        return False, "clear-browsing-data screen not found"
    if dev.tap(r"(?i)last hour|last 24 hours|last 7 days|last 4 weeks|time range", wait=1.5, tries=1):
        dev.tap(r"(?i)^all time$", wait=1.5, tries=2)
    pressed = dev.tap(r"(?i)^clear data$", wait=3.0, tries=3)
    if not pressed:
        return False, "Clear data button not found"
    dev.tap(r"(?i)^clear$", wait=3.0, tries=1)   # confirmation dialog, when shown
    time.sleep(8)
    return True, "Clear data pressed (time range All time requested)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pkg = a.package
    os.makedirs(a.out, exist_ok=True)
    TOKEN["v"] = secrets.token_hex(8)
    tok = TOKEN["v"]
    pats = {"url_path": f"visited_{tok}", "url_query": f"secret_{tok}", "title": f"ftitle_{tok}"}
    out = {"package": pkg, "phases": {}}

    def line(cid, status, detail=""):
        print(f"PERSONAL_FORENSIC {cid} {status} {detail}", flush=True)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    P.go_root()
    P.reverse()
    uid0 = P.sh("id -u")
    line("F00_env", "INFO", f"package={pkg} abi={P.sh('getprop ro.product.cpu.abi')} sdk={P.sh('getprop ro.build.version.sdk')} root_uid={uid0}")
    if uid0 != "0":
        line("F01_live", "NOT_RUN", "no root shell: cannot read the app's private files")
        return 0
    try:
        from ui_capture import Device, launch, wait_ready  # noqa: E402
        dev = Device(pkg, a.out, lambda l: print("PERSONAL_FORENSIC_UI", l, flush=True))
        P.adb("shell", "am", "force-stop", pkg)
        launch(dev)
        wait_ready(dev, seconds=180)
        url = f"http://127.0.0.1:{PORT}/visited_{tok}/page?q=secret_{tok}"
        for _ in range(2):
            P.open_url(pkg, url)
            time.sleep(10)
        live = scan(pkg, pats)
        out["phases"]["live"] = summarize_hits(live)
        line("F01_live", "INFO", f"visit canary found in {len(out['phases']['live']['files'])} files while running: {out['phases']['live']['files'][:40]}")
        P.adb("shell", "am", "force-stop", pkg)
        time.sleep(3)
        stopped = scan(pkg, pats)
        out["phases"]["stopped"] = summarize_hits(stopped)
        sizes = {f: size_of(pkg, f) for f in out["phases"]["stopped"]["files"][:40]}
        line("F02_stopped", "INFO", f"after force-stop: by_pattern={out['phases']['stopped']['by_pattern']} files={sizes}")
        # clear
        launch(dev)
        wait_ready(dev, seconds=120)
        ok, why = clear_all_time(dev, pkg)
        out["clear_ui"] = {"ok": ok, "detail": why}
        P.adb("shell", "am", "force-stop", pkg)
        time.sleep(3)
        if not ok:
            line("F03_cleared", "NOT_RUN", why)
        else:
            cleared = scan(pkg, pats)
            out["phases"]["cleared"] = summarize_hits(cleared)
            n = len(out["phases"]["cleared"]["files"])
            sizes = {f: size_of(pkg, f) for f in out["phases"]["cleared"]["files"][:40]}
            line("F03_cleared", "CLEAN" if n == 0 else "REMNANTS",
                 f"{why}; files still holding the canary after Clear: {n} by_pattern={out['phases']['cleared']['by_pattern']} files={sizes}")
        lc = P.adb("logcat", "-d", timeout=60)
        hits = sum(lc.count(p) for p in pats.values())
        line("F04_logcat", "INFO", f"canary occurrences in logcat: {hits} (a URL in the log would be a leak outside the app dir)")
        out["logcat_hits"] = hits
    except Exception as e:  # noqa: BLE001
        print("PERSONAL_FORENSIC harness_error", repr(e)[:300], flush=True)
        json.dump(out, open(os.path.join(a.out, "personal_forensics.json"), "w"), indent=1)
        return 2
    json.dump(out, open(os.path.join(a.out, "personal_forensics.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
