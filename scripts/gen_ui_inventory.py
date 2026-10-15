#!/usr/bin/env python3
"""Generate research/CHROME_UI_INVENTORY.md from a REAL reference capture.

Only elements actually observed in the reference capture are listed per screen
(no imagined screens). The full checklist from the project brief is appended,
with every item not covered by the capture explicitly marked NOT OBSERVED.

Usage: gen_ui_inventory.py --ref evidence/<run>/chrome_ref --run-id <id> --out research/CHROME_UI_INVENTORY.md
"""
import argparse, glob, json, os

CHECKLIST = [
 ("app launch / welcome / terms / default-browser / sign-in expectations", ["01_first_run"]),
 ("normal startup / home / new tab, logo/search, top/bottom toolbar", ["02_ntp"]),
 ("omnibox focus, suggestions, autocomplete, clipboard, clear, mic, incognito marks", ["03_omnibox_focused", "04_omnibox_suggestions"]),
 ("back/forward/reload/stop/share/translate/bookmark/site-info/secure states", ["05_page_loaded", "06_page_info", "07_app_menu"]),
 ("tabs, incognito, groups, create/reorder/close/restore, long-press, empty state", ["08_second_tab_ntp", "09_tab_switcher", "10_incognito_ntp", "10b_tab_switcher_incognito"]),
 ("menu, More/overflow actions, settings hierarchy and all core screens", ["07_app_menu", "11_settings", "11b_settings_scrolled"]),
 ("history / synced tabs / downloads / bookmarks / passwords / autofill / privacy / languages / accessibility", ["12_history", "13_bookmarks", "14_downloads"]),
 ("site permissions / page info / pop-ups, camera/mic/location, file chooser, media/fullscreen/print/share", ["06_page_info"]),
 ("home-screen shortcuts, PWAs, external intents/app links, Custom Tabs, back gestures", []),
 ("light/dark, portrait/landscape, IME open, gesture nav-bar, status bar, cutout/edge-to-edge", ["15_dark_page", "16_landscape", "03_omnibox_focused"]),
 ("accessibility labels, TalkBack, switch access, touch targets, large text, contrast", []),
 ("offline/retry, renderer crash recovery, background/restore, rotation, memory pressure", []),
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True); ap.add_argument("--run-id", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--stable", default="155.0.8059.80")
    a = ap.parse_args()
    meta = json.load(open(os.path.join(a.ref, "meta.json")))
    screens = {}
    for j in sorted(glob.glob(os.path.join(a.ref, "*.json"))):
        if os.path.basename(j) in ("meta.json", "provenance.json"): continue
        s = json.load(open(j))
        if "key" not in s or "nodes" not in s: continue
        screens[s["key"]] = s
    pkg = meta["package"]
    L = ["# Chrome Android UI inventory", "",
         "## 1. Reference की पहचान (ईमानदार स्थिति)", "",
         f"- **लक्ष्य reference:** Google Chrome Stable **{a.stable}** (phone)। यह अभी **उपलब्ध नहीं** है।",
         f"- **इस फ़ाइल में देखा गया reference:** `{pkg}` **{meta.get('versionName')}**, emulator image पर पहले से installed (`{meta.get('model')}`, Android {meta.get('android_release')} / API {meta.get('sdk')}, {meta.get('wm_size')}, {meta.get('wm_density')}, font_scale {meta.get('font_scale')}, navigation_mode {meta.get('navigation_mode')} (2 = gesture), locale `{meta.get('locale') or 'default (en-US)'}`, light theme, बिना Google account के)।",
         f"- **Evidence:** GitHub Actions run `{a.run_id}`, artifact `ui-chrome_ref`। Screenshots/XML: `evidence/`।",
         "- यह Stable 155 से 22 major versions पुराना है। इसलिए नीचे की हर पंक्ति **Chrome 133 का अवलोकन** है, Stable 155 का नहीं।", "",
         "## 2. Capture protocol (हर reference के लिए समान)", "",
         "1. `pm clear <package>`, light theme, portrait, animations बंद, कोई account नहीं।",
         "2. `scripts/ui_capture.py` का scripted journey: first run → NTP → omnibox focus → `example.com` टाइप → page → page info → menu → नया tab → tab switcher → settings → history → bookmarks → downloads → dark theme → landscape → incognito।",
         "3. हर screen पर: PNG screenshot, UIAutomator XML, और labelled nodes का JSON (text, content-desc, resource-id, class, bounds, clickable)।",
         "4. केवल IANA demo domains (`example.com`/`example.org`)। कोई login, account photo, email या निजी chat नहीं।",
         "5. **उपयोगकर्ता के फ़ोन से Stable 155 reference:** यही क्रम manually दोहराएँ, हर screen का screenshot लें, और Chrome version (Settings → About Chrome), फ़ोन model, Android version, display size, font size, theme और gesture/3-button navigation लिख दें। Account वाले screens न भेजें।", "",
         "## 3. देखे गए screens और elements (Chrome " + str(meta.get("versionName")) + ", emulator)", ""]
    for key, s in screens.items():
        own = [n for n in s["nodes"] if n.get("pkg") == pkg]
        L += [f"### `{key}` — {s.get('note','')}", f"Screenshot: `{s['png']}` · labelled nodes: {len(own)}", "",
              "| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |", "|---|---|---|---|---|---|---|"]
        for n in own:
            if not (n["text"] or n["desc"] or n["clickable"]): continue
            st = ",".join(k for k in ("clickable", "focused", "selected", "checked") if n.get(k)) or ("disabled" if not n.get("enabled") else "")
            L.append(f"| `{n['id'].split(':id/')[-1]}` | {n['text'][:60].replace('|','/')} | {n['desc'][:60].replace('|','/')} | {n['cls'].split('.')[-1]} | {n['bounds']} | {n['w']}×{n['h']} | {st} |")
        L.append("")
    L += ["## 4. Brief की पूरी checklist: क्या देखा गया, क्या नहीं", "", "| क्षेत्र | इस capture में screens | स्थिति |", "|---|---|---|"]
    for area, keys in CHECKLIST:
        got = [k for k in keys if k in screens]
        st = ("आंशिक रूप से देखा (Chrome %s, emulator)" % meta.get("versionName")) if got else "**NOT OBSERVED**"
        L.append(f"| {area} | {', '.join(got) or '—'} | {st} |")
    L += ["", "**Stable 155 के लिए हर पंक्ति: NOT OBSERVED।** Animation, latency, transition और TalkBack का अवलोकन अभी दर्ज नहीं हुआ है; journey में इन्हें मापने के steps जोड़ने बाकी हैं।"]
    L += ["", "## 5. Chromium 155 artifact से अंतर", "",
          "Chromium 155.0.8059.0 snapshot के वही screens इसी run में capture हुए हैं। Screen-दर-screen अंतर (missing/extra resource-ids, text, a11y labels, pixel MAD, side-by-side PNG) `reports/ui-compare/<target>/COMPARISON.md` में हैं। मुख्य देखे गए अंतर: 155 में नीचे का toolbar (`bottom_bar_*`, Home / Ask Gemini / New tab / Tabs / Menu), NTP पर `composeplate_button` \"AI Mode\" chip, omnibox में security status icon का न होना (page info केवल menu → Site controls से), और FRE का अलग क्रम। 133 में ये controls ऊपर toolbar में हैं और `location_bar_status_icon` मौजूद है। ये Stable 155 में भी ऐसे ही हैं या नहीं (field trials), यह Stable 155 reference के बिना **अज्ञात** है।"]
    open(a.out, "w").write("\n".join(L) + "\n")
    print(f"wrote {a.out}: {len(screens)} screens")

if __name__ == "__main__":
    main()
