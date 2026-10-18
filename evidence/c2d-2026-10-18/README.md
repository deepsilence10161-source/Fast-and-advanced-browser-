# c2d प्रमाण (18-10-2026): cold start से network audit + 0009 quiet start

| चीज़ | मान |
|---|---|
| Patch commit | c6e85e3 (`patches/0009-swiftra-quiet-start.patch`) |
| Gate commit | 282e31f (`scripts/ci/startup_netlog.py`, `shield_e2e.py` `quiet_violations`) |
| Builds | x64 39090930315, arm64 39090931393 (BUILD_INFO में 0009) |
| APK sha256 x64 | cce7c854bc2bd13eab26e2eed28e5702e8e06b4e15ec2b0d33db8366d3e6de7f |
| APK sha256 arm64 | 275ae7089b1b49a03d8b73da5f58afb3d51db8435ee49fa7e8d26dde6537569c |
| E2E (अंतिम) | ui-capture x64 39094623643, arm64 Redroid 39094624570: SHIELD_E2E PASS, STARTUP_NETLOG PASS |
| पहले (0009 से पहले) | x64 39084556269, arm64 39084557684 (startup NetLog पहली बार) |

## तरीका
Chromium की अपनी NetLog, process start से: `am set-debug-app` + `/data/local/tmp/chrome-command-line`
(`CommandLineInitUtil.java`, `SplitCompatApplication.java` @155) में `--log-net-log --net-log-file-format=ndjson --net-log-duration=75`।
Scenario: सब tabs बंद → cold start → 25 s idle → New Tab Page → idle। कोई test page नहीं। APK में कोई बदलाव नहीं।

## परिणाम (startup_pre_post.json)
| Request | 0009 से पहले | बाद में | निर्णय |
|---|---|---|---|
| discover-pa.googleapis.com (Discover feed, key नहीं) | 2 | 0 | हटाया; NTP से "Can't refresh Discover" गया |
| www.google.com/async/ddllog (doodle impression ping) | 2 | 0 | हटाया; doodle अब भी दिखता है |
| content-autofill.googleapis.com (Standard window, address form page के साथ) | — | 0 | key बिना बंद |
| accounts.google.com/ListAccounts | 1–2 | 1 | बचा 1 AI Mode eligibility (`folae`) के साथ; gate: अकेला = FAIL |
| async/ddljson, async/folae, complete/search, update.googleapis.com | हाँ | हाँ | feature: doodle, AI Mode, suggestions (setting), सुरक्षा components |
| Safe Browsing | 0 | 0 | — |

Start median (cold/warm): x64 emulator 1157 / 777.5 ms; arm64 Redroid 698.5 / 184 ms। device 9/9, cases 13/13, crash 0, ANR 0, leaks 0।

## सीमाएँ
- `dns.google` (arm64) runner के system DNS का auto-upgrade है, Swiftra का अपना नहीं; `clients2.google.com/time` (network time, SSL clock
  जाँच) कभी-कभी आता है: सुरक्षा feature, रखा।
- metrics recorders वाले बदलाव code-स्तर पर सत्यापित; मापन में अलग से असर सिद्ध नहीं (पहले भी दोनों ListAccounts folae के पास थे)।
- असली फ़ोन NOT RUN।
