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
                "checkable": n.get("checkable") == "true",
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

    def foreground_activity(self):
        o = shell("dumpsys activity activities | grep -E 'topResumedActivity|mResumedActivity' | head -1")
        m = re.search(r"\s([\w.]+/[\w.$]+)", o)
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

def launcher_component(pkg):
    """MAIN/LAUNCHER activity (वही जो launcher icon खोलता है)।"""
    o = shell(f"cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER {pkg}")
    last = [l.strip() for l in o.splitlines() if l.strip()]
    return last[-1] if last and last[-1].startswith(pkg + "/") else None

def launch(d):
    """Launcher-icon जैसा start। पहले `am start -n <launcher activity>` (हर Android पर), monkey केवल fallback:
    Redroid (run 38909149132) पर `monkey -c LAUNCHER 1` ने कोई process शुरू ही नहीं किया था।"""
    comp = launcher_component(d.pkg)
    o = shell(f"am start -W -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n {comp}", timeout=40) if comp else ""
    if not comp or "Error" in o or "Status: ok" not in o:
        d.log(f"launch: am start failed ({comp}: {o.strip()[-120:]!r}); monkey fallback")
        shell(f"monkey -p {d.pkg} -c android.intent.category.LAUNCHER 1")
    time.sleep(6)

def handle_system_dialog(d, xml):
    """System dialogs (default-browser role prompt / runtime permission)। Chromium का default-browser promo उस
    device पर आता है जहाँ कोई default browser नहीं (Redroid run 38911943802)। दर्ज करके "Cancel/Don't allow"।"""
    if d.foreground_pkg() not in ("com.android.permissioncontroller", "com.google.android.permissioncontroller"):
        return False
    title = d.find(r"\?\s*$", ("text",), xml=xml, clickable_pref=False) or d.find(r".+", ("text",), xml=xml, clickable_pref=False)
    btn = d.find(r"^(Cancel|Don't allow|Don’t allow|Not now|No thanks)$", ("text",), xml=xml) \
        or d.find(r":id/(permission_deny_button|button2)$", ("id",), xml=xml)
    d.log(f"system dialog: {title['text'] if title else '?'} -> {btn['text'] if btn and btn.get('text') else 'BACK'}")
    d.system_dialogs = getattr(d, "system_dialogs", []) + [title["text"] if title else "?"]
    if btn: d.tap_node(btn)
    else: d.back()
    time.sleep(2)
    return True

def wait_ready(d, seconds=60):
    t0 = time.time()
    while time.time() - t0 < seconds:
        ok, xml = is_browser_ready(d)
        if ok:
            return True
        if handle_system_dialog(d, xml): continue
        # handle first-run / promo dialogs generically
        n = d.find(FRE_BUTTONS, ("text",), xml=xml)
        if n:
            d.log(f"FRE/promo button: {n['text']}")
            d.tap_node(n); time.sleep(3)
        else:
            time.sleep(2)
    return False

def is_hub_open(d, xml=None):
    xml = xml if xml is not None else d.dump()
    return bool(re.search(r':id/(hub_pane_host|tab_list_recycler_view|tab_switcher_view_holder)"', xml))

def wait_for(d, pred, seconds):
    t0 = time.time()
    while time.time() - t0 < seconds:
        if pred(d): return True
        time.sleep(1)
    return False

PROMO_DISMISS = r"^(No thanks|No, thanks|Not now|Got it|Dismiss)$"

def dismiss_promo_sheet(d):
    """Bottom-sheet promos (NTP customization, default browser, …) — दर्ज करके बंद।"""
    xml = d.dump()
    if not re.search(r':id/(bottom_sheet|sheet_container|bottom_sheet_content)', xml): return False
    btn = d.find(PROMO_DISMISS, ("text",), xml=xml)
    if not btn: return False
    title = d.find(r".{12,}", ("text",), xml=xml, clickable_pref=False)
    d.log(f"promo sheet dismissed: {title['text'] if title else '?'} -> {btn['text']}")
    d.promos = getattr(d, "promos", []) + [title["text"] if title else "?"]
    d.tap_node(btn); time.sleep(1.5)
    return True

def ensure_main(d, tries=4):
    """Return to the tabbed browser surface: close pickers/sheets, relaunch if another app is in front."""
    for _ in range(tries):
        if subprocess.run(["adb", "get-state"], capture_output=True, timeout=20).stdout.decode().strip() != "device":
            d.log("ensure_main: device not ready, waiting"); subprocess.run(["timeout", "60", "adb", "wait-for-device"]); continue
        if handle_system_dialog(d, d.dump()): continue
        if d.foreground_pkg() != d.pkg:
            d.log("ensure_main: relaunch (foreground=%s)" % d.foreground_pkg()); launch(d); continue
        xml = d.dump()
        if d.handle_anr(xml): continue
        fre = d.find(FRE_BUTTONS, ("text",), xml=xml)
        if fre and "firstrun" in (d.foreground_activity() or "").lower():   # FRE पर BACK = FRE बंद (run 38909149132)
            d.log(f"ensure_main: FRE button {fre['text']}"); d.tap_node(fre); time.sleep(3); continue
        # sheet_container NTP पर हमेशा पूरे आकार में रहता है (sheet न हो तब भी) → उस पर BACK = app बाहर (run 38916663718)
        if d.find(r":id/(chrome_item_picker_container|bottom_sheet|bottom_sheet_content|menu_list)$", ("id",), xml=xml, clickable_pref=False) \
           or not d.find(r":id/(menu_button|tab_switcher_button)$", ("id",), xml=xml, clickable_pref=False):
            d.log("ensure_main: back (overlay present)"); d.back(); continue
        return True
    return False

SETTINGS_SKIP = r"^(Sign in|Turn on sync|Sign in to .*)$"   # login/account flow — PROJECT_RULES: बिना login


def slug(t):
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")[:28] or "x"


def on_settings_main(d, xml=None):
    xml = xml if xml is not None else d.dump()
    main = r'text="(Search engine|Address bar|Privacy and security|Safety check|Default browser|Autofill and passwords|Tabs and tab groups|Homepage|Notifications|Appearance|Accessibility|Site settings|Languages|Downloads|Developer options|About Swiftra|About Chromium)" resource-id="android:id/title"'
    return bool(re.search(r'text="Settings"', xml)) and len(re.findall(main, xml)) >= 2


# level-2: इन top-level पन्नों के भीतर के पन्ने भी (सत्यता/branding scan हेतु)। Search engine/Address bar/Homepage = radio सूचियाँ (छोड़ें)
SETTINGS_DEEP = r"^(Privacy and security|Autofill and passwords|Site settings|Languages|Accessibility|Google services|Appearance|Tabs and tab groups|Downloads|About Swiftra)$"
# भीतर छोड़ें: login, बाहरी कानूनी पन्ने (browser tab खोलते हैं), Safety check (rows expand होती हैं)
SUBPAGE_SKIP = r"^(Sign in.*|Turn on sync|Terms of Service|Privacy [Nn]otice|Google Privacy Policy|Safety check|Help|Send feedback)$"


def row_has_toggle(nodes, t):
    """title वाली row में switch/checkbox/radio हो तो tap = setting बदलना — ऐसी rows नहीं छूते।"""
    y0, y1 = t["bounds"][1] - 70, t["bounds"][3] + 90
    for n in nodes:
        if n is t or not n["checkable"]:
            continue
        cy = (n["bounds"][1] + n["bounds"][3]) / 2
        if y0 <= cy <= y1:
            return True
    return False


def on_page(d, title, xml=None):
    xml = xml if xml is not None else d.dump()
    return any(n["text"] == title and n["bounds"][1] < 400 and n["id"] != "android:id/title" for n in d.nodes(xml))


def crawl_subpages(d, pkg, parent, pkey, deadline):
    """parent पन्ने की हर navigational row: tap -> capture -> BACK (parent पर)। लौट न पाए तो False।"""
    out, seen, idle, j = [], set(), 0, 0
    while time.time() < deadline and idle < 2:
        xml = d.dump(); ns = d.nodes(xml)
        if not on_page(d, parent, xml):
            return out, False
        rows = [x for x in ns if x["id"] == "android:id/title" and x["pkg"] == pkg and x["h"] >= 45
                and x["text"] and x["text"] not in seen]
        if not rows:
            idle += 1; shell("input swipe 540 1700 540 900 400"); time.sleep(1.3); continue
        idle = 0
        for x in rows:
            if time.time() >= deadline:
                break
            t = x["text"]; seen.add(t)
            if re.search(SUBPAGE_SKIP, t):
                out.append({"title": t, "skipped": "rule"}); continue
            cur_xml = d.dump(); cur_ns = d.nodes(cur_xml)
            cur = [n for n in cur_ns if n["text"] == t and n["id"] == "android:id/title"]
            if not cur:
                out.append({"title": t, "skipped": "not found"}); continue
            if row_has_toggle(cur_ns, cur[0]) or not cur[0]["enabled"]:
                out.append({"title": t, "skipped": "toggle/disabled"}); continue
            d.tap_node(cur[0]); time.sleep(2.2); j += 1
            fg = d.foreground_pkg(); rec = {"title": t, "foreground": fg}
            nx = d.dump()
            if fg == pkg and not on_page(d, parent, nx):
                key = f"{pkey}__{j:02d}_{slug(t)}"
                d.capture(key, f"settings → {parent} → {t}"); rec["key"] = key
                if 'scrollable="true"' in nx:
                    shell("input swipe 540 1700 540 700 400"); time.sleep(1.2)
                    d.capture(key + "_b", f"settings → {parent} → {t} (scrolled)")
            elif fg != pkg:
                rec["left_app"] = True
            else:
                rec["no_navigation"] = True       # dialog/expand नहीं — parent ही दिखा
            out.append(rec)
            if fg == pkg and on_page(d, parent, nx):
                continue
            for _ in range(3):
                d.back(1.6)
                if on_page(d, parent):
                    break
            else:
                d.log(f"settings deep crawl: '{parent}' पर वापसी नहीं ('{t}' के बाद)")
                return out, False
    return out, True


def crawl_settings(d, pkg, budget_s=420, deep_budget_s=0):
    """Settings का हर top-level item: tap -> capture (scroll हो तो दूसरा capture) -> BACK। branding scan सब xml देखता है।"""
    t0 = time.time(); pages = []; visited = set(); idle = 0; n = 0
    deep_deadline = t0 + budget_s + deep_budget_s; budget_s += deep_budget_s
    while time.time() - t0 < budget_s and idle < 2:
        xml = d.dump()
        if not on_settings_main(d, xml):
            d.log("settings crawl: main list पर नहीं — रुकते हैं"); break
        titles = [x for x in d.nodes(xml) if x["id"] == "android:id/title" and x["pkg"] == pkg and x["h"] >= 45
                  and x["text"] not in visited]   # पूरी (57px) या लगभग पूरी दिखती row; नीचे की आख़िरी row भी (About)
        if not titles:
            idle += 1; shell("input swipe 540 1800 540 900 400"); time.sleep(1.5); continue
        idle = 0
        for x in titles:
            if time.time() - t0 >= budget_s:
                break
            t = x["text"]; visited.add(t)
            if re.search(SETTINGS_SKIP, t):
                pages.append({"title": t, "skipped": "login"}); continue
            # list scroll हो चुकी हो सकती है — title फिर से खोजें
            cur = d.find("^" + re.escape(t) + "$", ("text",))
            if not cur:
                pages.append({"title": t, "skipped": "not found"}); continue
            d.tap_node(cur); time.sleep(2.5); n += 1
            fg = d.foreground_pkg()
            rec = {"title": t, "foreground": fg}
            if fg == pkg:
                key = f"20_set_{n:02d}_{slug(t)}"
                c = d.capture(key, f"settings → {t}"); rec["key"] = key
                xs = open(os.path.join(d.out, key + ".xml")).read()
                if 'scrollable="true"' in xs:
                    shell("input swipe 540 1800 540 700 400"); time.sleep(1.5)
                    d.capture(key + "_b", f"settings → {t} (scrolled)"); rec["scrolled"] = True
                if deep_budget_s and re.search(SETTINGS_DEEP, t) and time.time() < deep_deadline:
                    if rec.get("scrolled"):          # भीतर की सूची ऊपर से
                        shell("input swipe 540 700 540 1800 400"); shell("input swipe 540 700 540 1800 400"); time.sleep(1.2)
                    try:
                        sub, ok = crawl_subpages(d, pkg, t, key, min(deep_deadline, time.time() + 240))
                    except Exception as e:
                        sub, ok = [{"error": repr(e)}], False
                    rec["subpages"] = sub
                    d.log(f"settings deep crawl: {t}: {len([x for x in sub if x.get('key')])} पन्ने")
            else:
                rec["left_app"] = True; d.log(f"settings crawl: '{t}' ने app छोड़ा (fg={fg})")
            pages.append(rec)
            for _ in range(5):
                d.back(1.8)
                if on_settings_main(d):
                    break
            else:
                d.log("settings crawl: main list पर वापसी नहीं — रुकते हैं")
                return pages
    d.log(f"settings crawl: {len([p for p in pages if p.get('key')])} पन्ने capture, {round(time.time()-t0)} s")
    return pages



def start_timings(pkg, activity, n_cold, n_warm, log):
    res = {"cold_ms": [], "warm_ms": [], "activity": activity}
    for i in range(n_cold):
        shell(f"am force-stop {pkg}"); time.sleep(1.5)
        o = shell(f"am start -W -n {activity} -a android.intent.action.VIEW -d about:blank", timeout=40)
        m = re.search(r"TotalTime:\s*(\d+)", o)
        if m: res["cold_ms"].append(int(m.group(1)))
        la = re.search(r"Activity:\s*(\S+)", o)
        if la: res.setdefault("landing_activities", set()).add(la.group(1))
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
    # FRE पूरा न हुआ हो तो cold start FirstRunActivity तक का होता है — browser start से तुलना योग्य नहीं
    res["landing_activities"] = sorted(res.get("landing_activities", ()))
    res["comparable"] = bool(res["landing_activities"]) and not any("firstrun" in x.lower() for x in res["landing_activities"])
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
        if handle_system_dialog(d, xml): continue
        n = d.find(FRE_BUTTONS, ("text",), xml=xml)
        if n:
            fre_i += 1
            d.capture(f"01_first_run_{fre_i}", f"before tapping '{n['text']}'")
            d.tap_node(n); time.sleep(3)
        else:
            time.sleep(2)
    meta["first_run_steps"] = fre_i; meta["reached_browser_ui"] = ready
    meta["system_dialogs"] = getattr(d, "system_dialogs", [])
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
    # NTP promo sheet ("Now you can customize your homepage") tab-switcher tap को निगल लेता था → 09 असल में NTP था
    # और BACK से app बाहर गया (runs 38913748996/38913752278 के screenshots) — पहले promo बंद, फिर hub की पुष्टि।
    dismiss_promo_sheet(d)
    hub_open = False
    for attempt in range(2):
        if d.tap(r"tab_switcher_button", ("id",)) or d.tap(r"(Switch or close tabs|tabs open)", ("desc",)):
            hub_open = wait_for(d, is_hub_open, 8)
            if hub_open: break
            d.log(f"tab switcher not open after tap (attempt {attempt + 1})"); dismiss_promo_sheet(d)
    meta["tab_switcher_opened"] = hub_open
    if hub_open:
        xml = d.dump()
        meta["tab_switcher_tabs"] = len(re.findall(r'content-desc="[^"]*, tab"', xml, re.I))
        time.sleep(1); d.capture("09_tab_switcher", "tab switcher grid, 2 tabs")
        d.back(); time.sleep(1.5)
        xml = d.dump()
        back_ok = d.foreground_pkg() == d.pkg and not is_hub_open(d, xml) and \
            bool(d.find(r":id/(menu_button|tab_switcher_button)$", ("id",), xml=xml, clickable_pref=False))
        meta["tab_switcher_back_returns_to_tab"] = back_ok
        d.log(f"tab switcher: opened, tabs={meta['tab_switcher_tabs']}, BACK returns to tab: {back_ok}")
        if back_ok: d.capture("09b_after_back_from_switcher", "BACK from tab switcher -> current tab")
    else:
        d.log("FINDING: tab switcher did not open")
    ensure_main(d)

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
                    shell("input swipe 540 600 540 1800 400"); shell("input swipe 540 600 540 1800 400"); time.sleep(1.2)
                    try:
                        meta["settings_pages"] = crawl_settings(d, a.package, deep_budget_s=720)
                    except Exception as e:   # crawler harness को न तोड़े
                        meta["settings_pages"] = None; meta["settings_crawl_error"] = repr(e); d.log(f"settings crawl error: {e!r}")
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
    meta["promo_sheets"] = getattr(d, "promos", [])
    # b2: app UI में Chrome/Chromium नाम (हर capture xml) — मापने योग्य branding जाँच; chrome_ref के लिए केवल जानकारी
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ci"))
        import branding_scan
        by = {}
        for f in sorted(os.listdir(a.out)):
            if f.endswith(".xml"):
                l = branding_scan.scan_xml(open(os.path.join(a.out, f), encoding="utf-8", errors="replace").read(), a.package)
                if l:
                    by[f] = l
        meta["branding_leaks"] = sum(len(v) for v in by.values())
        meta["branding_leak_values"] = sorted({x["value"] for v in by.values() for x in v})
        json.dump({"leaks": meta["branding_leaks"], "by_screen": by}, open(os.path.join(a.out, "branding_scan.json"), "w"),
                  ensure_ascii=False, indent=1)
        log(f"branding scan: {meta['branding_leaks']} leaks")
    except Exception as e:  # जाँच harness को न तोड़े
        meta["branding_leaks"] = None; meta["branding_scan_error"] = repr(e)
    # सत्यता scan (Chrome शब्द-रहित असत्य दावे: Google LLC copyright, metrics toggle, "is up to date")
    try:
        bad, seen = {}, set()
        for f in sorted(os.listdir(a.out)):
            if f.endswith(".xml"):
                l, s_ = branding_scan.scan_claims(open(os.path.join(a.out, f), encoding="utf-8", errors="replace").read(), a.package)
                seen |= s_
                if l:
                    bad[f] = l
        meta["false_claims"] = sum(len(v) for v in bad.values())
        meta["false_claim_values"] = sorted({x["claim"] + ": " + x["value"] for v in bad.values() for x in v})
        meta["expected_texts_found"] = sorted(seen)
        json.dump({"false_claims": meta["false_claims"], "by_screen": bad, "expected_found": sorted(seen),
                   "expected_all": sorted(branding_scan.EXPECTED)}, open(os.path.join(a.out, "truth_scan.json"), "w"),
                  ensure_ascii=False, indent=1)
        log(f"truth scan: {meta['false_claims']} false claims, expected found {sorted(seen)}")
    except Exception as e:
        meta["false_claims"] = None; meta["truth_scan_error"] = repr(e)
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"), indent=2)
    log("done")

if __name__ == "__main__":
    main()
