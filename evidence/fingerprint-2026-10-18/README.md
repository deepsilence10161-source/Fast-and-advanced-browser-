# Fingerprint Shield (patch 0011): before/after device evidence

## Before: APK built from 0010, without 0011 (2026-10-18)

| Target | Run | APK sha256 | Result |
|---|---|---|---|
| arm64 (Redroid) | 39127649494 | 5c0131ca…0b0c | `FINGERPRINT_E2E FAIL verdict=no_shield`: canvas/WebGL/audio identical on fp-a.example.com and fp-b.example.net (canvas 0a5580d762e9ae52, WebGL 7b89e8b5661e9d72, audio 172.67165154411487). `ADVANCED_E2E PASS` (HFM warning dialog, 3PC blocked) |
| x64 (emulator) | 39127648131 | 268568d6…1c30 (verified from BUILD_INFO) | `FINGERPRINT_E2E FAIL verdict=no_shield`: canvas 0a5580d762e9ae52 and WebGL 7b89e8b5661e9d72 identical on both sites, audio 172.6716519226975 on both. `ADVANCED_E2E PASS` (HFM warning dialog, 3PC blocked). Screenshot reviewed: the page rendered the result JSON (the red omnibox icon is expected because the test server uses a self-signed certificate) |

This is the expected baseline: without the shield, a tracker reads the same fingerprint on every site.
After: E2E on the 0011 APKs, once builds 39127524068 / 39127525981 finish.
