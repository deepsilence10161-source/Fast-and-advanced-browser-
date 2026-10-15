#!/usr/bin/env python3
"""Generate native-app/FEATURE_PARITY.md + reports/feature-parity.json.

Every feature row is traced to a Chromium source directory that is CHECKED to
exist (gitiles JSON) at the Chrome Stable source commit. Status is derived ONLY
from evidence files produced by real runs (reports/ui-compare/*/comparison.json);
unknown never defaults to pass.

Usage: feature_inventory.py --commit 43a195105613ac83c21d3f14de279f4a045c7da0 --stable 155.0.8059.80
"""
import argparse, json, os, sys, urllib.request

J = "chrome/android/java/src/org/chromium/chrome/browser/"
B = "chrome/browser/"
# (id, area, feature, source paths, ui-capture screen keys that exercise it, external dependency)
FEATURES = [
 ("F01","Launch","First-run experience (terms, sign-in choice, notifications prompt)",[J+"firstrun"],["01_first_run"],"Google account/Play Services for sign-in"),
 ("F02","Launch","Default-browser prompt / role",[J+"firstrun", B+"ui/android/default_browser_promo"],[],"Android RoleManager"),
 ("F03","NTP","New tab page: logo, search box, shortcuts (Most visited)",[J+"ntp", J+"suggestions"],["02_ntp"],"Google search/doodle services"),
 ("F04","NTP","Discover/feed",[B+"feed"],["02_ntp"],"Google Discover backend (private)"),
 ("F05","Omnibox","Omnibox focus, keyboard, URL/search input",[J+"omnibox"],["03_omnibox_focused"],"—"),
 ("F06","Omnibox","Autocomplete suggestions (history, search suggest)",[J+"omnibox", "components/omnibox"],["04_omnibox_suggestions"],"Google Suggest API"),
 ("F07","Omnibox","Voice search",[J+"omnibox"],[],"Google app / speech service"),
 ("F08","Omnibox","Lens / camera search",[J+"lens"],[],"Google Lens app (private)"),
 ("F09","Navigation","Load page, back/forward/reload/stop",[J+"tab", J+"toolbar"],["05_page_loaded"],"—"),
 ("F10","Security","Page info / connection security / site permissions sheet",[J+"page_info", "components/page_info"],["06_page_info"],"—"),
 ("F11","Menu","App (overflow) menu",[J+"toolbar", J+"ui"],["07_app_menu"],"—"),
 ("F12","Tabs","Multiple tabs, new tab",[J+"tabmodel", J+"tab"],["08_second_tab_ntp"],"—"),
 ("F13","Tabs","Tab switcher (grid), close/restore, groups",[J+"hub", J+"tasks", "chrome/browser/tab_ui"],["09_tab_switcher"],"—"),
 ("F14","Incognito","Incognito tabs and NTP",[J+"incognito"],["10_incognito_ntp","10b_tab_switcher_incognito"],"—"),
 ("F15","Settings","Settings hierarchy",[J+"settings"],["11_settings","11b_settings_scrolled"],"—"),
 ("F16","History","History",[J+"history"],["12_history"],"Sync for cross-device history"),
 ("F17","Bookmarks","Bookmarks",[J+"bookmarks"],["13_bookmarks"],"Sync for cross-device"),
 ("F18","Downloads","Downloads manager",[J+"download"],["14_downloads"],"—"),
 ("F19","Theme","Dark theme (system)",[J+"appearance"],["15_dark_page","15b_dark_menu"],"—"),
 ("F20","Layout","Landscape orientation",[J+"toolbar"],["16_landscape"],"—"),
 ("F21","Passwords","Password manager / autofill",[J+"password_manager", J+"autofill"],[],"Google Password Manager backend / Play Services"),
 ("F22","Sync","Sign-in and Chrome Sync",[J+"signin", J+"sync"],[],"Chrome Sync API — restricted for Chromium derivatives"),
 ("F23","Translate","Page translation",[J+"translate"],[],"Google Translate service"),
 ("F24","Share","Share, QR code, send to devices",[J+"share", J+"sharing"],[],"Sync for send-to-device"),
 ("F25","Find","Find in page",[J+"findinpage"],[],"—"),
 ("F26","Reading","Reader mode / simplified view",[J+"dom_distiller"],[],"—"),
 ("F27","Desktop","Request desktop site",[J+"desktop_site"],[],"—"),
 ("F28","Safety","Safe Browsing",[J+"safe_browsing"],[],"Safe Browsing API key"),
 ("F29","Safety","Safety check",[J+"safety_check"],[],"Password leak check backend"),
 ("F30","Privacy","Delete browsing data / quick delete",[J+"browsing_data", J+"quick_delete"],[],"—"),
 ("F31","Permissions","Site permissions (camera, mic, location, notifications)",[J+"permissions", J+"site_settings"],[],"Android runtime permissions"),
 ("F32","Notifications","Web push notifications",[J+"notifications", J+"push_messaging"],[],"Firebase Cloud Messaging (GCM sender) — requires Google keys"),
 ("F33","PWA","Install app / add to home screen (WebAPK)",[J+"webapps"],[],"WebAPK minting server (private)"),
 ("F34","Custom Tabs","Custom Tabs provider",[J+"customtabs", J+"browserservices"],[],"—"),
 ("F35","Media","Media playback, fullscreen, picture-in-picture",[J+"media", J+"fullscreen"],[],"—"),
 ("F36","Print","Print",[J+"printing"],[],"Android print framework"),
 ("F37","PDF","PDF viewing",[J+"pdf"],[],"—"),
 ("F38","Contextual","Touch to search / contextual search",[J+"contextualsearch"],[],"Google backend"),
 ("F39","Context menu","Long-press context menu (links/images)",[J+"contextmenu"],[],"—"),
 ("F40","Offline","Offline pages / read later",[J+"offlinepages", J+"read_later"],[],"—"),
 ("F41","Accessibility","Accessibility settings, text scaling, TalkBack labels",[J+"accessibility"],[],"—"),
 ("F42","Multi-window","Multi-window / multi-instance",[J+"multiwindow"],[],"—"),
 ("F43","Widgets","Search / quick action / bookmarks widgets",[J+"searchwidget", J+"quickactionsearchwidget", J+"bookmarkswidget"],[],"—"),
 ("F44","AI","AI Mode chip, Ask Gemini toolbar button, context picker",[J+"chrome_item_picker", J+"omnibox"],["02_ntp"],"Google AI/Gemini backend (private)"),
 ("F45","Enterprise","Enterprise policy",[J+"policy", J+"enterprise"],[],"—"),
 ("F46","Supervised","Family Link / supervised users",[J+"supervised_user"],[],"Google Family Link (private)"),
 ("F47","Updates","In-app update / Omaha",[J+"omaha"],[],"Google Play (Chrome) — project needs own update channel"),
 ("F48","Gestures","Gesture navigation / back handling",[J+"gesturenav"],[],"—"),
 ("F49","Payments","Web Payments",[J+"payments"],[],"Google Pay (private) for some flows"),
 ("F50","DevTools","Remote debugging",[J+"devtools"],[],"—"),
]

def gitiles_exists(commit, path):
    url = f"https://chromium.googlesource.com/chromium/src/+/{commit}/{path}?format=JSON"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", required=True); ap.add_argument("--stable", required=True)
    ap.add_argument("--compare-dir", default="reports/ui-compare")
    a = ap.parse_args()
    comps = {}
    if os.path.isdir(a.compare_dir):
        for d in sorted(os.listdir(a.compare_dir)):
            p = os.path.join(a.compare_dir, d, "comparison.json")
            if os.path.exists(p):
                comps[d] = json.load(open(p))
    rows = []
    for fid, area, feat, paths, keys, dep in FEATURES:
        src = {p: gitiles_exists(a.commit, p) for p in paths}
        ev = {}
        for name, c in comps.items():
            scr = {s["screen"]: s for s in c["screens"]}
            got = [k for k in keys if k in scr and scr[k].get("status_vs_emulator_reference") in ("verified", "mismatch")]
            ref_only = [k for k in keys if k in scr and scr[k].get("status") == "blocked"]
            ev[name] = {"screens_compared": got, "artifact_did_not_reach": ref_only,
                        "statuses": {k: scr[k].get("status_vs_emulator_reference", scr[k].get("status")) for k in keys if k in scr}}
        exercised = any(v["screens_compared"] for v in ev.values())
        rows.append({"id": fid, "area": area, "feature": feat, "source_paths_verified": src,
                     "all_sources_exist": all(src.values()), "ui_capture_screens": keys,
                     "external_dependency": dep, "evidence": ev,
                     "status_vs_chrome_stable": "not-tested",
                     "status_vs_emulator_reference": ("mismatch-or-verified (see evidence)" if exercised else "not-tested")})
    json.dump({"stable": a.stable, "commit": a.commit, "features": rows}, open("reports/feature-parity.json", "w"), indent=1, ensure_ascii=False)
    L = ["# Feature parity matrix", "",
         f"- Chrome Stable target: **{a.stable}** (source commit `{a.commit}`)",
         "- हर source path को gitiles पर इसी commit पर जाँचा गया है (✔ = मौजूद, ✘ = नहीं मिला)।",
         "- Status केवल वास्तविक run के evidence से तय होता है। अज्ञात को कभी pass नहीं माना जाता। Stable 155 का reference न होने से हर feature की स्थिति `status vs Stable = not-tested` है।",
         "- यह script से बनी फ़ाइल है: `python3 scripts/feature_inventory.py --commit … --stable …`", "",
         "| ID | क्षेत्र | Feature | Source (commit पर) | UI-capture screens | Evidence (emulator ref बनाम artifact) | vs Stable | बाहरी निर्भरता |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        srcs = "<br>".join(("✔ " if ok else "✘ ") + f"`{p}`" for p, ok in r["source_paths_verified"].items())
        evs = []
        for name, v in r["evidence"].items():
            if v["statuses"]:
                evs.append(f"{name}: " + ", ".join(f"{k}={s}" for k, s in v["statuses"].items()))
        rows_ev = "<br>".join(evs) if evs else ("कोई runnable परीक्षण अभी नहीं" if not r["ui_capture_screens"] else "चलाया नहीं गया")
        L.append(f"| {r['id']} | {r['area']} | {r['feature']} | {srcs} | {', '.join(r['ui_capture_screens']) or '—'} | {rows_ev} | not-tested | {r['external_dependency']} |")
    L += ["", f"कुल features: {len(rows)}। Source path मौजूद: {sum(r['all_sources_exist'] for r in rows)}/{len(rows)}। Evidence वाले features: {sum(1 for r in rows if r['status_vs_emulator_reference'] != 'not-tested')}।",
          "", "**सीमा:** यह सूची Chrome के top-level feature क्षेत्रों को कवर करती है। हर क्षेत्र के अंदर के उप-features (जैसे हर Settings screen) की exhaustive सूची `research/CHROME_UI_INVENTORY.md` में reference screenshots मिलने पर बढ़ाई जाएगी।"]
    open("native-app/FEATURE_PARITY.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L[-3:]))

if __name__ == "__main__":
    main()
