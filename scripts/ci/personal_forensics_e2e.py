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


def visible_texts(dev, limit=25):
    try:
        return [n["text"] or n["desc"] for n in dev.nodes(dev.dump()) if (n["text"] or n["desc"])][:limit]
    except Exception:  # noqa: BLE001
        return []


def open_clear_screen(dev, pkg):
    """The visible menu path (Settings > Privacy and security > Delete browsing data). A direct show_fragment launch crashed SettingsActivity.onStart (no arguments), which also left a crash dump in the app, so it is not used."""
    P.adb("shell", "am", "start", "-W", "-n", f"{pkg}/org.chromium.chrome.browser.settings.SettingsActivity", timeout=60)
    time.sleep(4)
    for _ in range(4):   # extra Swiftra rows at the top (Gemini chat, 0114) push the Privacy row below the fold
        if dev.find(r"(?i)^privacy and security$|^privacy$", ("text", "desc")):
            break
        P.sh("input swipe 540 1700 540 600 300")
        time.sleep(1.5)
    if dev.tap(r"(?i)^privacy and security$|^privacy$", wait=3.0, tries=3) and dev.tap(r"(?i)^(clear|delete) browsing data$", wait=3.0, tries=3):
        for _ in range(4):
            if dev.find(r"(?i)^(clear|delete) data$|time range", ("text", "desc")):
                return True, "settings menu path"
            time.sleep(2)
    return False, "screen not found; visible=" + repr(visible_texts(dev))


def clear_all_time(dev, pkg):
    """Drive Settings > Clear browsing data. Returns (ok, detail). ok only if the Clear button was really pressed."""
    opened, how = open_clear_screen(dev, pkg)
    if not opened:
        return False, "clear-browsing-data " + how
    if dev.tap(r"(?i)last hour|last 24 hours|last 7 days|last 4 weeks|time range", wait=1.5, tries=1):
        dev.tap(r"(?i)^all time$", wait=1.5, tries=2)
    pressed = dev.tap(r"(?i)^(clear|delete) data$", wait=3.0, tries=3)
    if not pressed:
        return False, "Clear/Delete data button not found; visible=" + repr(visible_texts(dev))
    dev.tap(r"(?i)^(clear|delete)$", wait=3.0, tries=1)   # confirmation dialog, when shown
    time.sleep(8)
    return True, f"Clear data pressed via {how} (time range All time requested)"


def pull_remnants(pkg, files, outdir, tag):
    """Copy small remnant files into the artifact (synthetic canary only) so the exact location can be inspected."""
    os.makedirs(outdir, exist_ok=True)
    for rel in files[:12]:
        src = rel if rel.startswith("/") else f"/data/data/{pkg}/{rel}"
        dst = os.path.join(outdir, f"{tag}__" + rel.strip("/").replace("/", "__").replace(" ", "_"))
        r = P.adb("pull", src, dst, timeout=60)
        if not os.path.exists(dst):
            print(f"PERSONAL_FORENSIC pull_failed {rel}: {r.strip()[:100]}", flush=True)


def close_tabs_via_cdp(pkg):
    """Close every tab through the DevTools HTTP endpoint (no websocket needed): /json lists tabs, /json/close/<id> closes."""
    import urllib.request
    try:
        P.adb("forward", "tcp:9222", "localabstract:chrome_devtools_remote")
        time.sleep(1)
        tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=10).read())
        closed = 0
        for t in tabs:
            if t.get("type") == "page":
                urllib.request.urlopen("http://127.0.0.1:9222/json/close/" + t["id"], timeout=10).read()
                closed += 1
        return {"pages_closed": closed, "listed": len(tabs)}
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)[:160]}


def run_scenario(dev, pkg, out, a, name, close_tabs):
    tok = secrets.token_hex(8)
    TOKEN["v"] = tok
    pats = {"url_path": f"visited_{tok}", "url_query": f"secret_{tok}", "title": f"ftitle_{tok}"}
    res = {"scenario": name, "close_tabs_before_clear": close_tabs}

    def line(cid, status, detail=""):
        print(f"PERSONAL_FORENSIC {name}/{cid} {status} {detail}", flush=True)

    P.adb("shell", "am", "force-stop", pkg)
    launch(dev)
    wait_ready(dev, seconds=180)
    url = f"http://127.0.0.1:{PORT}/visited_{tok}/page?q=secret_{tok}"
    for _ in range(2):
        P.open_url(pkg, url)
        time.sleep(10)
    live = summarize_hits(scan(pkg, pats))
    res["live"] = live
    line("F01_live", "INFO", f"{len(live['files'])} files hold the visit while running: {live['files'][:40]}")
    P.adb("shell", "am", "force-stop", pkg)
    time.sleep(3)
    stopped = summarize_hits(scan(pkg, pats))
    res["stopped"] = stopped
    line("F02_stopped", "INFO", f"after force-stop by_pattern={stopped['by_pattern']} files={stopped['files'][:40]}")
    launch(dev)
    wait_ready(dev, seconds=120)
    if close_tabs:
        res["tabs_closed"] = close_tabs_via_cdp(pkg)
        line("F02b_tabs", "INFO", f"close all tabs via DevTools: {res['tabs_closed']}")
        time.sleep(5)
    ok, why = clear_all_time(dev, pkg)
    res["clear_ui"] = {"ok": ok, "detail": why}
    P.adb("shell", "am", "force-stop", pkg)
    time.sleep(3)
    if not ok:
        line("F03_cleared", "NOT_RUN", why)
        return res
    cleared = summarize_hits(scan(pkg, pats))
    res["cleared"] = cleared
    n = len(cleared["files"])
    line("F03_cleared", "CLEAN" if n == 0 else "REMNANTS",
         f"{why}; files still holding the canary after Delete: {n} by_pattern={cleared['by_pattern']} files={cleared['files']}")
    if n:
        pull_remnants(pkg, cleared["files"], os.path.join(a.out, "remnants"), name)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pkg = a.package
    os.makedirs(a.out, exist_ok=True)
    out = {"package": pkg, "scenarios": []}
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    P.go_root()
    P.reverse()
    uid0 = P.sh("id -u")
    print(f"PERSONAL_FORENSIC F00_env INFO package={pkg} abi={P.sh('getprop ro.product.cpu.abi')} sdk={P.sh('getprop ro.build.version.sdk')} root_uid={uid0}", flush=True)
    if uid0 != "0":
        print("PERSONAL_FORENSIC F01_live NOT_RUN no root shell: cannot read the app's private files", flush=True)
        return 0
    try:
        global launch, wait_ready
        from ui_capture import Device, launch, wait_ready  # noqa: E402
        dev = Device(pkg, a.out, lambda l: print("PERSONAL_FORENSIC_UI", l, flush=True))
        for name, close in (("tabs_open", False), ("tabs_closed", True)):
            out["scenarios"].append(run_scenario(dev, pkg, out, a, name, close))
        lc = P.adb("logcat", "-d", timeout=60)
        tags = {}
        for ln in lc.splitlines():
            if "visited_" in ln:
                m = re.match(r"\S+\s+\S+\s+\d+\s+\d+\s+\w\s+(\S+?)\s*:", ln)
                tags[m.group(1) if m else "?"] = tags.get(m.group(1) if m else "?", 0) + 1
        print(f"PERSONAL_FORENSIC F04_logcat INFO lines with a visited_ canary by log tag: {tags}", flush=True)
        out["logcat_tags"] = tags
    except Exception as e:  # noqa: BLE001
        print("PERSONAL_FORENSIC harness_error", repr(e)[:300], flush=True)
        json.dump(out, open(os.path.join(a.out, "personal_forensics.json"), "w"), indent=1)
        return 2
    json.dump(out, open(os.path.join(a.out, "personal_forensics.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
