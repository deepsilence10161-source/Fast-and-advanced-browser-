# b1 (Swiftra) device E2E — icon fix के बाद (16-10-2026)

APK (icon fix, commit 26f8a45; builds x64 38907965672, arm64 38907969325):
- x64  SHA-256 `e298584d324f42e90761ed04ac3ba3455ea9f3d3570d75d18c14b117e392c38e`
- arm64 SHA-256 `11cd819c7126422864c292001a147aab310a34c8ccb12cf485be9a6b136edbbb`
- दोनों: `com.swiftra.app`, label Swiftra, non-debuggable, v3 CN=Swiftra, cert `029de0fa…10fe06`

| platform | status | device checks | UI journey | chat fixture | crash |
|---|---|---|---|---|---|
| x64: Android 16 emulator (API 36, Pixel launcher, swiftshader) — run 38913748996 | PASS (Android emulator) | 9/9 | browser UI ready, सभी screens | 10/10 | app crash 0 |
| arm64: Redroid 14 container, **native arm64 CPU** (ubuntu-24.04-arm, कोई translation नहीं), software GPU, Launcher3 — run 38913752278 | PASS (Android emulator श्रेणी; असली phone नहीं) | 9/9 | browser UI ready, सभी screens | 10/10 | app crash 0, ApplicationExitInfo में कोई मौत नहीं |

Device checks: 01 installed · 02 launcher activity · 03 launcher app-drawer में "Swiftra" (uiautomator + screenshot) ·
04 non-debuggable (flags + run-as refused) · 05 same-key update · 06 दूसरी key वाला update →
`INSTALL_FAILED_UPDATE_INCOMPATIBLE` और installed signer अपरिवर्तित · 07 असली touch-scroll (CDP rAF) ·
08 process alive / crash buffer साफ़ · 09 uninstall + reinstall।

## इस दौर में मिले और ठीक हुए bugs (हर एक device test से पकड़ा गया)
1. **Launcher icon (उत्पाद bug)**: Chromium में `ic_launcher_round` = `layered_app_icon_background` + पारदर्शी foreground,
   और `ic_launcher` = सफ़ेद background + `layered_app_icon`। हमारा glyph केवल foreground में था →
   Pixel launcher पर सिर्फ़ gradient गोला (`bug-icon-before/pixel_launcher_run-38904972738.jpg`),
   Launcher3 पर सफ़ेद खाली square (`bug-icon-before/launcher3_run-38907136262.jpg`)। Static जाँच (15 images pixel-identical)
   इसे नहीं पकड़ सकती थी। Fix: दोनों PNG में पूरा icon; regression test `test_layered_icons_each_contain_full_artwork`
   (पुराने icons पर FAIL, नए पर PASS)। बाद: `icon_after_both_launchers.jpg`।
2. **Check 06 parser**: adb failure line (stderr) पहले और "Performing Streamed Install" (stdout) बाद में छपता है → केवल
   आखिरी line पढ़ना गलत। अब पूरा output `device_checks_install.log` में + signer तुलना।
3. **Check 07 तरीका**: `dumpsys gfxinfo` (HWUI) Chromium के compositor frames नहीं गिनता → CDP rAF + असली swipes।
4. **Harness launch (Redroid)**: `monkey -c LAUNCHER 1` ने process शुरू ही नहीं किया → `am start -n <launcher activity>`।
5. **Harness FRE**: overlay पर BACK दबाने से FRE बंद हो जाता था → FRE buttons tap; system dialog
   ("Set Swiftra as your default browser app?" — Chromium का default-browser promo, Redroid पर कोई default browser नहीं) → दर्ज + Cancel।

## Finding वापस लिया (ईमानदार सुधार)
- पहले लिखा: "tab switcher में BACK → app बाहर (FAIL)"। **गलत था**: `09_tab_switcher.png` असल में NTP है — step 08 पर
  NTP customization promo sheet ("Now you can customize your homepage") ने tab-switcher tap निगल लिया; फिर NTP पर BACK से app
  background (Chrome में भी यही)। Chromium 155 `HubCoordinator.handleBackPress()` → `selectCurrentTabAndHideHub()`।
  पुराने सभी runs (snapshot builds भी) में यही harness गलती थी। Harness अब promo बंद करता, hub खुलना और BACK पर tab assert करता है।
- Page-info: omnibox status icon a11y tree में नहीं; app menu > "Site controls" से खुलता है (पहले से दर्ज)।

## Performance (software GPU — प्रतिनिधि नहीं, तुलना के लिए नहीं)
| | cold median (p95) | warm median | PSS after example.com | touch scroll |
|---|---|---|---|---|
| x64 emulator | 712 ms (771) | 498 ms | 151 MB | 21.5 fps, p50 49.9 ms |
| arm64 Redroid | 669.5 ms (717) | 246.5 ms | 284 MB | 15 fps स्थिर (66.7 ms = software compositor) |
Cold start अब `landing_activities` = ChromeTabbedActivity (FRE के बाद) — तुलना-योग्य।

## सीमा (ईमानदारी)
असली phone (असली GPU/driver, OEM launcher, battery/thermal) पर यह b1 build **NOT RUN** है — assistant के पास physical device नहीं।
Redroid = वही arm64 machine code असली ARM CPU पर, पर container (host kernel साझा) और software GPU।
