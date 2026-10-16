# b2 — in-app branding (Swiftra), 2026-10-16

मापक: `scripts/ci/branding_scan.py` — हर capture हुई screen के uiautomator xml में app-UI (`com.swiftra.app`, WebView
content छोड़कर) के text/content-desc में "Chrome"/"Chromium" (सुरक्षित: chrome://, Web Store, ChromeOS, The Chromium Authors,
Google legal doc नाम)। Calibration: b1 APK (run 38918534121 / 38918537719) पर **38 / 36 leaks**।

| चरण | build | device E2E | branding leaks (x64 / arm64) |
|---|---|---|---|
| b1 (पहले) | icon-fix 38907965672 / 38907969325 | 38918534121 / 38918537719 | 38 / 36 |
| strings (4 grd) + logo + tiles + 0003 | 38925419556 / 38925431150 (732706d) | `interim-*`: 38928444001 / 38928448688 | 8 / 8 (menu button, incognito) |
| + android_ui_strings, scoped components_strings, लिप्यंतरण | 38935765027 / 38931729325 (patch hash 33c1d71b4e9c) | 38938906018 / 38938909743 | **0 / 0** |

अंतिम runs: device_checks 9/9, chat fixture 10/10, crash 0, ANR 0, tab switcher 2 tabs + BACK -> tab; cold start median
1023.5 ms (x64 emulator) / 709 ms (arm64 Redroid), warm 818 / 254 ms। Redroid = native arm64 CPU, software GPU — **real phone नहीं**।

दृश्य जाँच (screenshots): FRE पर Swiftra logo + "Make Swiftra your own" / "Welcome to Swiftra", footer केवल ToS
(झूठा "sends usage and crash data to Google" हटा — 0003); पहली NTP tiles Facebook/YouTube/Amazon/Wikipedia/ESPN
(पहले chromium.org/codereview/freenode); Incognito "Swiftra won't save"; menu button "Customize and control Swiftra"।

सीमाएँ: केवल capture हुई ~24 screens मापी गईं (Settings के भीतरी पन्ने, dialogs आदि नहीं); generated_resources /
components_strings की बाकी grds अभी नहीं बदलीं; inflected भाषाओं (hr, hu…) के रूप native review माँगते हैं;
legal gate G1: ToS link अभी Google Terms of Service, Swiftra की अपनी ToS/Privacy नहीं।
