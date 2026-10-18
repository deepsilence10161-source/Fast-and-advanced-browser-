# Fingerprint Shield (patch 0011): before/after device evidence

## Before: APK built from 0010, without 0011 (2026-10-18)

| Target | Run | APK sha256 | Result |
|---|---|---|---|
| arm64 (Redroid) | 39127649494 | 5c0131ca…0b0c | `FINGERPRINT_E2E FAIL verdict=no_shield`: canvas/WebGL/audio identical on fp-a.example.com and fp-b.example.net (canvas 0a5580d762e9ae52, WebGL 7b89e8b5661e9d72, audio 172.67165154411487). `ADVANCED_E2E PASS` (HFM warning dialog, 3PC blocked) |
| x64 (emulator) | 39127648131 | 268568d6…1c30 (verified from BUILD_INFO) | `FINGERPRINT_E2E FAIL verdict=no_shield`: canvas 0a5580d762e9ae52 and WebGL 7b89e8b5661e9d72 identical on both sites, audio 172.6716519226975 on both. `ADVANCED_E2E PASS` (HFM warning dialog, 3PC blocked). Screenshot reviewed: the page rendered the result JSON (the red omnibox icon is expected because the test server uses a self-signed certificate) |

This is the expected baseline: without the shield, a tracker reads the same fingerprint on every site.

## After: APK built with 0011 (2026-10-18)

| Target | Run | APK sha256 | Result |
|---|---|---|---|
| arm64 (Redroid, Android 14) | 39144748799 | 8954118e…14fd (BUILD_INFO patches 0000-0011) | `FINGERPRINT_E2E PASS verdict=shielded reasons=[]`. Canvas: fp-a.example.com 9837d91e131d14d0, fp-b.example.net 5cf263a416bf2b59 (different per site); re-read, strip, sub-rect and toDataURL stable within a site (`reread_same/strip_same/subrect_same/url_same: true`); max per-channel deviation 1. WebGL: bdfc1b6188594cac vs 44f393bfaab156ea. Audio sum: 172.67109696869738 vs 172.6709835237998. Same-site iframe read the same canvas hash as the top frame. `ADVANCED_E2E PASS`. Screenshot fp-b.example.net.png reviewed: the page rendered the result JSON |
| x64 (emulator, API 36) | 39144742833 | dbcfbb84…be24be (BUILD_INFO patches 0000-0011) | `FINGERPRINT_E2E PASS verdict=shielded reasons=[]`. Canvas bd512fac3551a6b2 vs 117f8c21204a8422; WebGL 8b60381c45af4932 vs 33d3a244839bef1d; audio 172.67380781197426 vs 172.66978841124364; each site's iframe matches its top frame. `ADVANCED_E2E PASS` |

Status: **PASS (actual device: arm64 Redroid) + PASS (emulator: x64)**.
Files: `after-arm64-39144748799/`, `after-x64-39144742833/` (BUILD_INFO, advanced_e2e.json/.txt, screenshots).
