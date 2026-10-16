# b1 (Swiftra) branding check — 16-10-2026

Source: build runs x64 38896651753, arm64 38896660409 (commit b621868); ui-capture run 38899621628 (x64, API 36 emulator).

| Check | Result | Method |
|---|---|---|
| Package | `com.swiftra.app` (x64 + arm64) | aapt2 badging (BUILD_INFO), emulator `pm` (meta.json) |
| Launcher label | `Swiftra` | aapt2 `application-label`, androguard `get_app_name()` |
| debuggable | absent (non-debuggable) | aapt2 badging has no `application-debuggable` |
| Signature | v3, CN=Swiftra, RSA 4096, cert SHA-256 `029de0fa…10fe06` = `patches/signing_cert_sha256.txt` | apksigner verify (build-tools 37) |
| Adaptive icon fg/bg (10 files, 5 densities) | pixel-identical to `patches/overlay` (max diff 0; stored as WebP) | androguard resource resolution → pixel diff |
| Legacy `app_icon` (5) | alpha diff 0, visible (premultiplied) RGB diff 0 | same |
| Themed/monochrome icon | Swiftra path present (`res/wq.xml`); Chromium path absent | byte search in compiled XML |
| UI journey | PASS — all screens in `com.swiftra.app`, crash 0; cold median 1060 ms, warm 796 ms; PSS 127 MB | ui-capture |
| Long-chat fixture | 10/10 PASS | chat_fixture.txt |

## बाकी "Chrome"/"Chromium" (b2 का काम)
- Android strings (android_chrome_strings.grd): "Make Chrome your own", "Chrome notifications make things easier",
  "Customize and control Google Chrome" (menu button), "About Chrome", "Sign in to Chrome",
  "…apps that open links in Chrome", FRE: "Chrome sends usage and crash data to Google".
- chromium_strings.grd: Incognito NTP "Chromium won’t save".
- First-run screen पर Chromium logo (in-app drawable, launcher icon नहीं)।
- NTP default tiles: chromium.org / googlesource / codereview (Chromium popular-sites fallback)।
- "Ask Google or type URL" = default search engine का नाम (branding नहीं)।
