#!/usr/bin/env python3
"""Scripted, reproducible native-UI capture for an Android browser package.

Runs the SAME scripted journey against any Chrome-like package (Google Chrome
reference on the emulator image, or our Chromium-based artifact) and stores,
for every screen: screenshot PNG, UIAutomator XML, and a JSON summary of every
visible node (text, content-desc, resource-id, class, bounds, clickable).
Also records cold/warm start timings (am start -W) and PSS memory.

No account, no login, no private data: only about:blank / example.com /
example.org (IANA reserved demo domains) are opened.

Usage:
  ui_capture.py --package com.android.chrome --label chrome_ref --out out/chrome_ref
  ui_capture.py --package org.chromium.chrome --label artifact --out out/artifact --apk path/ChromePublic.apk
"""
import argparse, json, os, re, statistics, subprocess, sys, time, xml.etree.ElementTree as ET

def sh(*args, timeout=45, check=False):
    try:
        r = subprocess.run(["adb", *args], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[adb timeout] {' '.join(args)[:120]}", flush=True)
        return ""
    if check and r.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)} failed: {r.stderr.decode(errors='replace')}")
    return r.stdout.decode("utf-8", errors="replace")

def shell(cmd, timeout=45):
    return sh("shell", cmd, timeout=timeout)

class Device:
    def __init__(self, pkg, out, log):
        self.pkg, self.out, self.log = pkg, out, log
        self.steps = []

    # ---------- UI tree ----------
    def dump(self, retries=4):
        for i in range(retries):
            shell("rm -f /sdcard/ui.xml")
            o = shell("uiautomator dump /sdcard/ui.xml", timeout=25)
            x = sh("exec-out", "cat", "/sdcard/ui.xml")
            if x.strip().startswith("<?xml"):
                return x
            time.sleep(1.5)
        return ""

    @staticmethod
    def nodes(xml):
        out = []
        if not xml:
            return out
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return out
        for n in root.iter("node"):
            b = re.findall(r"\d+", n.get("bounds", "[0,0][0,0]"))
            b = list(map(int, b)) if len(b) == 4 else [0, 0, 0, 0]
            out.append({
                "text": n.get("text", ""), "desc": n.get("content-desc", ""),
                "id": n.get("resource-id", ""), "cls": n.get("class", ""),
                "pkg": n.get("package", ""), "clickable": n.get("clickable") == "true",
                "enabled": n.get("enabled") == "true", "focused": n.get("focused") == "true",
                "selected": n.get("selected") == "true", "checked": n.get("checked") == "true",
                "bounds": b, "w": b[2] - b[0], "h": b[3] - b[1],
            })
        return out

    def find(self, pattern, fields=("text", "desc", "id"), xml=None, clickable_pref=True):
        xml = xml if xml is not None else self.dump()
        rx = re.compile(pattern, re.I)
        hits = [n for n in self.nodes(xml) if any(rx.search(n[f] or "") for f in fields) and n["w"] > 0 and n["h"] > 0]
        if clickable_pref:
            hits.sort(key=lambda n: (not n["clickable"], n["w"] * n["h"]))
        return hits[0] if hits else None

    anr_count = 0
    def handle_anr(self, xml=None):
        xml = xml if xml is not None else self.dump()
        if re.search(r"isn(&apos;|')t responding", xml):
            self.anr_count += 1
            self.log(f"ANR dialog seen (#{self.anr_count}) — tapping Wait")
            n = self.find(r":id/aerr_wait$", ("id",), xml=xml)
            if n: self.tap_node(n); time.sleep(5)
            return True
        return False

    def tap_node(self, n):
        x = (n["bounds"][0] + n["bounds"][2]) // 2
        y = (n["bounds"][1] + n["bounds"][3]) // 2
        shell(f"input tap {x} {y}")

    def tap(self, pattern, fields=("text", "desc", "id"), wait=2.0, tries=3):
        for _ in range(tries):
            n = self.find(pattern, fields)
            if n:
                self.tap_node(n); time.sleep(wait)
                self.log(f"tap OK  /{pattern}/ -> {n['id'] or n['text'] or n['desc']}")
                return True
            time.sleep(1.5)
        self.log(f"tap MISS /{pattern}/")
        return False

    def key(self, k, wait=1.2):
        shell(f"input keyevent {k}"); time.sleep(wait)

    def back(self, wait=1.5):
        self.key("KEYCODE_BACK", wait)

    def text(self, s):
        shell("input text " + s.replace(" ", "%s")); time.sleep(1.0)

    def foreground_pkg(self):
        o = shell("dumpsys activity activities | grep -E 'topResumedActivity|mResumedActivity' | head -1")
        m = re.search(r"\s([\w.]+)/", o)
        return m.group(1) if m else ""

    # ---------- capture ----------
    def capture(self, key, note=""):
        time.sleep(1.0)
        xml = self.dump()
        if self.handle_anr(xml):  # only re-dump when an ANR dialog was actually dismissed
            xml = self.dump()
        png = os.path.join(self.out, f"{key}.png")
        with open(png, "wb") as f:
            f.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=60).stdout)
        open(os.path.join(self.out, f"{key}.xml"), "w").write(xml)
        ns = self.nodes(xml)
        visible = [n for n in ns if n["w"] > 0 and n["h"] > 0 and (n["text"] or n["desc"] or n["id"])]
        rec = {"key": key, "note": note, "foreground": self.foreground_pkg(),
               "node_count": len(ns), "nodes": visible,
               "png": os.path.basename(png), "png_bytes": os.path.getsize(png),
               "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        json.dump(rec, open(os.path.join(self.out, f"{key}.json"), "w"), indent=1)
        self.steps.append({k: rec[k] for k in ("key", "note", "foreground", "node_count", "png_bytes")})
        self.log(f"captured {key} ({len(visible)} labelled nodes, fg={rec['foreground']})")
        return rec


FRE_BUTTONS = r"^(Use without an account|No thanks|No, thanks|Accept & continue|Accept and continue|Continue|Got it|Done|Skip|Not now|No Thanks|Stay signed out|Use without account)$"

def is_browser_ready(d):
    xml = d.dump()
    return bool(d.find(r"(search_box_text|url_bar|search_box|location_bar)", ("id",), xml=xml)), xml

def launch(d):
    shell(f"monkey -p {d.pkg} -c android.intent.category.LAUNCHER 1")
    time.sleep(6)

def wait_ready(d, seconds=60):
    t0 = time.time()
    while time.time() - t0 < seconds:
        ok, xml = is_browser_ready(d)
        if ok:
            return True
        # handle first-run / promo dialogs generically
        n = d.find(FRE_BUTTONS, ("text",), xml=xml)
        if n:
            d.log(f"FRE/promo button: {n['text']}")
            d.tap_node(n); time.sleep(3)
        else:
            time.sleep(2)
    return False

def ensure_main(d, tries=4):
    """Return to the tabbed browser surface: close pickers/sheets, relaunch if another app is in front."""
    for _ in range(tries):
        if subprocess.run(["adb", "get-state"], capture_output=True, timeout=20).stdout.decode().strip() != "device":
            d.log("ensure_main: device not ready, waiting"); subprocess.run(["timeout", "60", "adb", "wait-for-device"]); continue
        if d.foreground_pkg() != d.pkg:
            d.log("ensure_main: relaunch (foreground=%s)" % d.foreground_pkg()); launch(d); continue
        xml = d.dump()
        if d.handle_anr(xml): continue
        if d.find(r":id/(chrome_item_picker_container|bottom_sheet|sheet_container|menu_list)$", ("id",), xml=xml, clickable_pref=False) \
           or not d.find(r":id/(menu_button|tab_switcher_button)$", ("id",), xml=xml, clickable_pref=False):
            d.log("ensure_main: back (overlay present)"); d.back(); continue
        return True
    return False

def start_timings(pkg, activity, n_cold, n_warm, log):
    res = {"cold_ms": [], "warm_ms": [], "activity": activity}
    for i in range(n_cold):
        shell(f"am force-stop {pkg}"); time.sleep(1.5)
        o = shell(f"am start -W -n {activity} -a android.intent.action.VIEW -d about:blank", timeout=40)
        m = re.search(r"TotalTime:\s*(\d+)", o)
        if m: res["cold_ms"].append(int(m.group(1)))
    for i in range(n_warm):
        shell("input keyevent KEYCODE_HOME"); time.sleep(1.5)
        o = shell(f"am start -W -n {activity} -a android.intent.action.VIEW -d about:blank", timeout=40)
        m = re.search(r"TotalTime:\s*(\d+)", o)
        if m: res["warm_ms"].append(int(m.group(1)))
    for k in ("cold_ms", "warm_ms"):
        v = sorted(res[k])
        if v:
            res[k + "_median"] = statistics.median(v)
            res[k + "_p95"] = v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]
    log(f"timings: {res}")
    return res

def pss_kb(pkg):
    o = shell(f"dumpsys meminfo {pkg} | grep -E 'TOTAL PSS|TOTAL:' | head -1")
    m = re.search(r"(?:TOTAL PSS:|TOTAL:?)\s*(\d+)", o)
    return int(m.group(1)) if m else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True); ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--apk")
    ap.add_argument("--cold", type=int, default=10); ap.add_argument("--warm", type=int, default=10)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    logf = open(os.path.join(a.out, "journey.log"), "a")
    def log(m):
        line = f"[{time.strftime('%H:%M:%S')}] {m}"; print(line, flush=True); logf.write(line + "\n"); logf.flush()

    meta = {"label": a.label, "package": a.package}
    if a.apk:
        log("install: " + sh("install", "-r", "-g", a.apk, timeout=600).strip().splitlines()[-1])
    pkginfo = shell(f"dumpsys package {a.package}")
    meta["versionName"] = (re.search(r"versionName=(\S+)", pkginfo) or [None, None])[1]
    meta["versionCode"] = (re.search(r"versionCode=(\d+)", pkginfo) or [None, None])[1]
    meta["primaryCpuAbi"] = (re.search(r"primaryCpuAbi=(\S+)", pkginfo) or [None, None])[1]
    for k, p in {"android_release": "ro.build.version.release", "sdk": "ro.build.version.sdk",
                 "model": "ro.product.model", "abilist": "ro.product.cpu.abilist",
                 "native_bridge": "ro.dalvik.vm.native.bridge", "locale": "persist.sys.locale"}.items():
        meta[k] = shell(f"getprop {p}").strip()
    meta["wm_size"] = shell("wm size").strip(); meta["wm_density"] = shell("wm density").strip()
    meta["font_scale"] = shell("settings get system font_scale").strip()
    meta["navigation_mode"] = shell("settings get secure navigation_mode").strip()
    meta["webview"] = shell("dumpsys webviewupdate | grep 'Current WebView package'").strip()
    log(f"meta: {meta}")
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"), indent=2)   # early write (watchdog safety)

    d = Device(a.package, a.out, log)
    shell(f"pm clear {a.package}"); shell("cmd uimode night no")
    shell("settings put system accelerometer_rotation 0"); shell("settings put system user_rotation 0")
    shell(f"am set-debug-app --persistent {a.package}") if False else None
    shell("input keyevent KEYCODE_WAKEUP"); shell("wm dismiss-keyguard")

    # 01 first run
    launch(d)
    d.capture("01_first_run", "first launch after pm clear")
    fre_i = 0
    t0 = time.time(); ready = False
    while time.time() - t0 < 90:
        ok, xml = is_browser_ready(d)
        if ok: ready = True; break
        if d.handle_anr(xml): continue
        n = d.find(FRE_BUTTONS, ("text",), xml=xml)
        if n:
            fre_i += 1
            d.capture(f"01_first_run_{fre_i}", f"before tapping '{n['text']}'")
            d.tap_node(n); time.sleep(3)
        else:
            time.sleep(2)
    meta["first_run_steps"] = fre_i; meta["reached_browser_ui"] = ready
    log(f"browser UI ready: {ready}")
    if not ready:
        d.capture("01_stuck", "browser UI not reached in 90s")

    # 02 new tab page
    time.sleep(3); d.capture("02_ntp", "new tab page / start surface")

    # 03 omnibox focus
    if d.tap(r":id/(search_box_text|url_bar)$", ("id",)):
        d.capture("03_omnibox_focused", "omnibox focused, keyboard expected")
        d.text("example.com"); time.sleep(2.5)
        d.capture("04_omnibox_suggestions", "typed 'example.com'")
        d.key("KEYCODE_ENTER", 7)
    if not d.find(r"example\.com", ("text",)):
        d.log("omnibox navigation not confirmed; using VIEW intent")
        shell(f"am start -a android.intent.action.VIEW -d https://example.com {a.package}"); time.sleep(7)
    ensure_main(d)
    d.capture("05_page_loaded", "https://example.com loaded")
    meta["pss_kb_after_example"] = pss_kb(a.package)

    # 06 page info
    opened = d.tap(r":id/(location_bar_status_icon|location_bar_status|security_button|status_icon)$", ("id",), tries=1) \
             or d.tap(r"(View site information|site information|Connection is secure)", ("desc",), tries=1)
    if not opened and d.tap(r"menu_button", ("id",)):
        if d.tap(r"^(Site controls|Site settings|Page info)$", ("text", "desc")):
            time.sleep(2)
            opened = d.foreground_pkg() == a.package
            d.log(f"page-info via app menu 'Site controls': {opened}")
            if opened: meta.setdefault("findings", []).append("page info reached via app menu > Site controls (no omnibox status icon)")
        else:
            d.back()
    if not opened:
        d.log("FINDING: no page-info/security status entry point exposed in the accessibility tree")
        meta.setdefault("findings", []).append("page-info entry point (location_bar_status_icon) absent from a11y tree on page")
    if opened:
        d.capture("06_page_info", "page info / connection security sheet")
        d.back(); ensure_main(d)

    # 07 app menu
    if d.tap(r"menu_button", ("id",)) or d.tap(r"(More options|Customize and control)", ("desc",)):
        d.capture("07_app_menu", "overflow/app menu on a web page")
        d.back(); ensure_main(d)

    # 08 new tab via menu, 09 tab switcher
    if d.tap(r"menu_button", ("id",)) and d.tap(r"^New tab$", ("text",)):
        d.capture("08_second_tab_ntp", "second tab opened from menu")
    if d.tap(r"tab_switcher_button", ("id",)) or d.tap(r"(Switch or close tabs|tabs open)", ("desc",)):
        time.sleep(2); d.capture("09_tab_switcher", "tab switcher grid, 2 tabs")
        d.back(); ensure_main(d)

    # 11-14 menu destinations
    for key, label in (("11_settings", r"^Settings$"), ("12_history", r"^History$"),
                       ("13_bookmarks", r"^Bookmarks$"), ("14_downloads", r"^Downloads$")):
        if d.tap(r"menu_button", ("id",)):
            if not d.find(label, ("text",)):
                shell("input swipe 800 1700 800 700 400"); time.sleep(1.2)
            if d.tap(label, ("text",)):
                time.sleep(2); d.capture(key, f"menu → {label.strip('^$')}")
                if key == "11_settings":
                    shell("input swipe 540 1800 540 600 400"); time.sleep(1.5)
                    d.capture("11b_settings_scrolled", "settings scrolled")
                d.back(2)
            else:
                d.back()
        ensure_main(d)

    # 15 dark theme
    shell("cmd uimode night yes"); time.sleep(3)
    shell(f"am start -a android.intent.action.VIEW -d https://example.org {a.package}"); time.sleep(6)
    d.capture("15_dark_page", "system dark theme, example.org")
    if d.tap(r"menu_button", ("id",)):
        d.capture("15b_dark_menu", "dark theme app menu"); d.back()
    shell("cmd uimode night no"); time.sleep(2)

    # 16 landscape
    shell("settings put system user_rotation 1"); shell("wm user-rotation lock 1"); time.sleep(5)
    rec = d.capture("16_landscape", "landscape orientation")
    from struct import unpack
    with open(os.path.join(a.out, rec["png"]), "rb") as f:
        hdr = f.read(24)
    w, h = unpack(">II", hdr[16:24]) if hdr[:8] == b"\x89PNG\r\n\x1a\n" else (0, 0)
    meta["landscape_png_size"] = [w, h]; meta["landscape_rotated"] = w > h
    d.log(f"landscape screenshot {w}x{h} rotated={w > h}")
    shell("wm user-rotation lock 0"); shell("settings put system user_rotation 0"); time.sleep(3)

    # 10 incognito (kept last: FLAG_SECURE + observed adb hang afterwards)
    if d.tap(r"menu_button", ("id",)) and d.tap(r"^New Incognito tab$", ("text",)):
        d.capture("10_incognito_ntp", "incognito new tab page")
        if d.tap(r"tab_switcher_button", ("id",)) or d.tap(r"(Switch or close tabs|tabs open)", ("desc",)):
            time.sleep(2); d.capture("10b_tab_switcher_incognito", "tab switcher incognito pane"); d.back()
    # Incognito windows set FLAG_SECURE (screenshots blank by design) — force-stop afterwards
    shell(f"am force-stop {a.package}"); time.sleep(2); launch(d); ensure_main(d)


    # 17 performance (same device, about:blank, am start -W)
    act = shell(f"cmd package resolve-activity --brief -a android.intent.action.VIEW -d https://example.com {a.package} | tail -1").strip()
    if "/" not in act:
        act = shell(f"cmd package resolve-activity --brief {a.package} | tail -1").strip()
    meta["start_activity"] = act
    meta["timings"] = start_timings(a.package, act, a.cold, a.warm, log) if "/" in act else None
    meta["steps"] = d.steps; meta["anr_dialogs"] = d.anr_count
    crash = sh("logcat", "-d", "-b", "crash")
    meta["crash_buffer_lines"] = len([l for l in crash.splitlines() if a.package in l or "FATAL" in l])
    open(os.path.join(a.out, "crash.txt"), "w").write(crash)
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"), indent=2)
    log("done")

if __name__ == "__main__":
    main()
