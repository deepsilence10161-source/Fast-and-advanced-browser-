#!/usr/bin/env python3
"""PERSONAL_GEMINI: the Settings > "Gemini chat" entry and "stay signed in to Google after Delete browsing data".

No Google account is used or needed. What is measured (synthetic probe cookies only):
  M00 the three Settings rows exist (Gemini chat, Gemini chat history, Stay signed in ...)
  M01 tapping "Gemini chat" opens gemini.google.com in a browser tab and Google does not refuse this browser
  M02 switch ON (default): after Delete browsing data (All time, cookies+cache) a probe cookie on .google.com SURVIVES while a
      probe cookie on another site is DELETED
  M03 switch OFF: after Delete browsing data BOTH probe cookies are deleted (the switch really changes the behaviour)
  I01 INFO: which app files still mention gemini.google.com after the deletion with the switch ON vs OFF
It does NOT measure a real sign-in, real Gemini chats or their history (those need an account and live in Google's servers).
Line format: `PERSONAL_GEMINI <id> <PASS|FAIL|NOT_RUN|INFO> <detail>`.
"""
import argparse
import json
import os
import re
import secrets
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import personal_e2e as P  # noqa: E402
import personal_forensics_e2e as F  # noqa: E402

ROWS = {"open": r"(?i)^gemini chat$", "history": r"(?i)^gemini chat history$",
        "keep": r"(?i)^stay signed in to google after deleting data$"}
PROBE_GOOGLE = "swiftra_keep_probe"
PROBE_OTHER = "swiftra_other_probe"


def out(cid, status, detail=""):
    print(f"PERSONAL_GEMINI {cid} {status} {detail}", flush=True)
    return status


def pages():
    P.adb("forward", "tcp:9222", "localabstract:chrome_devtools_remote")
    time.sleep(1)
    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=10).read())
    return [t for t in tabs if t.get("type") == "page"]


class Cdp:
    def __init__(self, url):
        import websocket
        self.ws = websocket.create_connection(url, timeout=30, suppress_origin=True)
        self.n = 0

    def call(self, method, params=None):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                return m.get("result", {})

    def eval(self, expr):
        r = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return (r.get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:  # noqa: BLE001
            pass


def cookies_named(cdp):
    cdp.call("Network.enable")
    allc = cdp.call("Network.getAllCookies").get("cookies", [])
    return {c["name"] for c in allc if c.get("name") in (PROBE_GOOGLE, PROBE_OTHER)}, len(allc)


def set_probes(cdp, tok):
    exp = time.time() + 365 * 86400
    a = cdp.call("Network.setCookie", {"name": PROBE_GOOGLE, "value": tok, "domain": ".google.com", "path": "/",
                                       "secure": True, "expires": exp})
    b = cdp.call("Network.setCookie", {"name": PROBE_OTHER, "value": tok, "domain": "127.0.0.1", "path": "/",
                                       "expires": exp})
    return a.get("success"), b.get("success")


def any_page(prefer=r"google|127\.0\.0\.1"):
    ps = pages()
    for t in ps:
        if re.search(prefer, t.get("url", "")):
            return t
    return ps[0] if ps else None


def open_settings(dev, pkg):
    P.adb("shell", "am", "start", "-W", "-n", f"{pkg}/org.chromium.chrome.browser.settings.SettingsActivity", timeout=60)
    time.sleep(4)


def open_clear_screen_scrolling(dev, pkg):
    """Same menu path as the forensics script, but with a scroll: the three Gemini rows at the top push 'Privacy and security' down."""
    P.adb("shell", "am", "start", "-W", "-n", f"{pkg}/org.chromium.chrome.browser.settings.SettingsActivity", timeout=60)
    time.sleep(4)
    for _ in range(4):
        if dev.find(r"(?i)^privacy and security$|^privacy$", ("text", "desc")):
            break
        P.sh("input swipe 540 1700 540 600 300")
        time.sleep(1.5)
    if dev.tap(r"(?i)^privacy and security$|^privacy$", wait=3.0, tries=3) and dev.tap(r"(?i)^(clear|delete) browsing data$", wait=3.0, tries=3):
        for _ in range(4):
            if dev.find(r"(?i)^(clear|delete) data$|time range", ("text", "desc")):
                return True, "settings menu path (scrolled)"
            time.sleep(2)
    return False, "screen not found; visible=" + repr(F.visible_texts(dev))


F.open_clear_screen = open_clear_screen_scrolling


def prefs_value(pkg):
    txt = P.sh(f"grep -h 'swiftra_keep_google_signin' /data/data/{pkg}/shared_prefs/*.xml 2>/dev/null | head -1", 30)
    m = re.search(r'value="(true|false)"', txt or "")
    return m.group(1) if m else "default(true)"


def probe_cycle(dev, pkg, label, expect_google_kept):
    """Set probes on a live tab, press Delete data, read the probes again. Returns (status, detail)."""
    tok = secrets.token_hex(6)
    P.open_url(pkg, f"http://127.0.0.1:{P.PORT}/gemini_probe_{tok}")
    time.sleep(8)
    page = any_page(r"127\.0\.0\.1")
    if not page:
        return "NOT_RUN", "no tab page to attach DevTools to"
    c = Cdp(page["webSocketDebuggerUrl"])
    try:
        ok_g, ok_o = set_probes(c, tok)
        before, total = cookies_named(c)
    finally:
        c.close()
    if before != {PROBE_GOOGLE, PROBE_OTHER}:
        return "NOT_RUN", f"probes could not be planted (set google={ok_g} other={ok_o}, seen={sorted(before)})"
    ok, why = F.clear_all_time(dev, pkg)
    if not ok:
        return "NOT_RUN", why
    time.sleep(4)
    page = any_page(r"127\.0\.0\.1")
    if not page:
        return "NOT_RUN", "tab gone after deletion (cannot read cookies)"
    c = Cdp(page["webSocketDebuggerUrl"])
    try:
        after, total_after = cookies_named(c)
    finally:
        c.close()
    google_kept = PROBE_GOOGLE in after
    other_kept = PROBE_OTHER in after
    detail = (f"{label}: pref={prefs_value(pkg)} probes before={sorted(before)} after={sorted(after)} "
              f"cookies_total {total}->{total_after}; {why}")
    good = (google_kept == expect_google_kept) and not other_kept
    return ("PASS" if good else "FAIL"), detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pkg = a.package
    os.makedirs(a.out, exist_ok=True)
    import http.server
    import threading
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", P.PORT), F.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    F.TOKEN["v"] = "gemini"
    P.go_root()
    P.reverse()
    out("M_env", "INFO", f"package={pkg} abi={P.sh('getprop ro.product.cpu.abi')} sdk={P.sh('getprop ro.build.version.sdk')}")
    results = {}
    try:
        from ui_capture import Device, launch, wait_ready
        F.launch, F.wait_ready = launch, wait_ready
        dev = Device(pkg, a.out, lambda l: print("PERSONAL_GEMINI_UI", l, flush=True))
        P.adb("shell", "am", "force-stop", pkg)
        launch(dev)
        wait_ready(dev, seconds=180)

        # M00 rows
        open_settings(dev, pkg)
        found = {k: bool(dev.find(rx, ("text", "desc"))) for k, rx in ROWS.items()}
        if not all(found.values()):
            dev.nodes(dev.dump())
            time.sleep(2)
            found = {k: bool(dev.find(rx, ("text", "desc"))) for k, rx in ROWS.items()}
        results["M00_rows"] = out("M00_rows", "PASS" if all(found.values()) else "FAIL",
                                  f"rows present={found} first_texts={F.visible_texts(dev, 12)}")

        # M01 open Gemini
        if dev.tap(ROWS["open"], ("text", "desc"), wait=12, tries=2):
            time.sleep(8)
            try:
                gp = [t for t in pages() if "gemini.google.com" in t.get("url", "") or "accounts.google.com" in t.get("url", "")]
                if not gp:
                    results["M01_open"] = out("M01_open", "NOT_RUN", f"no Google page after tapping (offline runner?) pages={[(t['url'][:60]) for t in pages()][:4]}")
                else:
                    t = gp[0]
                    c = Cdp(t["webSocketDebuggerUrl"])
                    body = (c.eval("document.body ? document.body.innerText.slice(0,500) : ''") or "")
                    ua = c.eval("navigator.userAgent")
                    c.close()
                    refused = re.search(r"(?i)browser or app may not be secure|not supported|unsupported browser|couldn.t sign you in", body + t.get("title", ""))
                    st = "FAIL" if refused else "PASS"
                    results["M01_open"] = out("M01_open", st, f"url={t['url'][:90]} title={t.get('title','')[:60]!r} ua={ua!r} body_start={body[:140]!r} (no account used)")
            except Exception as e:  # noqa: BLE001
                results["M01_open"] = out("M01_open", "NOT_RUN", "harness: " + repr(e)[:160])
        else:
            results["M01_open"] = out("M01_open", "FAIL", "the 'Gemini chat' row could not be tapped; visible=" + repr(F.visible_texts(dev, 15)))

        # M04 three-dot menu row
        P.adb("shell", "am", "force-stop", pkg)
        launch(dev)
        wait_ready(dev, seconds=120)
        try:
            opened = dev.tap(r"menu_button", ("id",), wait=2.5, tries=3)
            row = None
            seen = []
            for _ in range(7):   # the menu is long: Gemini chat sits right above Settings, below the fold
                if not opened:
                    break
                xml = dev.dump()
                for x in F.visible_texts(dev, 60):
                    if x not in seen:
                        seen.append(x)
                row = dev.find(r"(?i)^gemini chat$", ("text", "desc"), xml=xml)
                if row:
                    break
                P.sh("input swipe 540 1600 540 700 300")
                time.sleep(1.2)
            texts = seen
            if not row:
                results["M04_menu_row"] = out("M04_menu_row", "FAIL", f"menu opened={opened}; 'Gemini chat' not in the three-dot menu; visible={texts}")
            else:
                idx_g = texts.index("Gemini chat") if "Gemini chat" in texts else -1
                idx_s = texts.index("Settings") if "Settings" in texts else -1
                dev.tap_node(row)
                time.sleep(12)
                gp = [t for t in pages() if "gemini.google.com" in t.get("url", "")]
                results["M04_menu_row"] = out("M04_menu_row", "PASS" if gp else "FAIL",
                                              f"menu row order: Gemini chat at {idx_g}, Settings at {idx_s}; tapping it opened gemini tab={bool(gp)} urls={[t['url'][:60] for t in pages()][:4]}")
        except Exception as e:  # noqa: BLE001
            results["M04_menu_row"] = out("M04_menu_row", "NOT_RUN", "harness: " + repr(e)[:160])

        # M02 keep ON (default)
        P.adb("shell", "am", "force-stop", pkg)
        launch(dev)
        wait_ready(dev, seconds=120)
        st, d = probe_cycle(dev, pkg, "switch ON (default)", True)
        results["M02_keep_on"] = out("M02_keep_on", st, d)
        gem_on = F.summarize_hits(F.scan(pkg, {"gem": "gemini.google.com"}))
        out("I01_on", "INFO", f"files mentioning gemini.google.com after deletion with the switch ON: {gem_on['files'][:25]}")

        # turn the switch OFF in Settings
        P.adb("shell", "am", "force-stop", pkg)
        launch(dev)
        wait_ready(dev, seconds=120)
        open_settings(dev, pkg)
        flipped = dev.tap(ROWS["keep"], ("text", "desc"), wait=2, tries=3)
        time.sleep(2)
        out("M03_switch", "INFO", f"tapped switch row={flipped} pref_now={prefs_value(pkg)}")
        P.adb("shell", "am", "force-stop", pkg)
        launch(dev)
        wait_ready(dev, seconds=120)
        st, d = probe_cycle(dev, pkg, "switch OFF", False)
        results["M03_keep_off"] = out("M03_keep_off", st, d)
        gem_off = F.summarize_hits(F.scan(pkg, {"gem": "gemini.google.com"}))
        out("I01_off", "INFO", f"files mentioning gemini.google.com after deletion with the switch OFF: {gem_off['files'][:25]}")
    except Exception as e:  # noqa: BLE001
        print("PERSONAL_GEMINI harness_error", repr(e)[:300], flush=True)
        return 2
    finally:
        P.adb("shell", "am", "force-stop", pkg)
        try:
            srv.shutdown()
        except Exception:  # noqa: BLE001
            pass
    c = {s: sum(1 for v in results.values() if v == s) for s in ("PASS", "FAIL", "NOT_RUN")}
    json.dump({"package": pkg, "results": results}, open(os.path.join(a.out, "personal_gemini.json"), "w"), indent=1)
    print(f"PERSONAL_GEMINI_SUMMARY pass={c['PASS']} fail={c['FAIL']} not_run={c['NOT_RUN']}", flush=True)
    return 1 if c["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
