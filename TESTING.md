# TESTING: क्या चला, क्या पास/फेल हुआ, क्या बाकी है

तारीख 2026-10-15। हर पंक्ति एक वास्तविक run से है। Machine-readable रूप: `reports/verification-summary.json`।
Status शब्दावली: `PASS (actual Android device)` · `PASS (Android emulator)` · `PASS (desktop/browser component)` · `PASS (static/signature/format only)` · `NOT RUN / BLOCKED` · `FAIL`।

## 1. परीक्षण की परतें (अलग-अलग gates)

| परत | कहाँ | कैसे चलाएँ |
|---|---|---|
| L1 Unit (Python 10, Node 6) | local + `unit-tests.yml` (हर push) | `python3 -m unittest discover -s tests -v`; `node --test experiments/chat-rendering/chat-store.test.js` |
| L2 Browser component (synthetic chat fixture) | desktop Google Chrome headless, `unit-tests.yml` job `chat-experiment-desktop` ×3 | `scripts/ci/run_chat_fixture.py` (CDP) |
| L3 Android emulator E2E | `ui-capture.yml` (manual dispatch): API 36 x86_64, Pixel 6 profile, 1080×2400 @420 dpi, gesture nav, en-US, light theme, no account | `scripts/ci/run_capture.sh <target>` → `scripts/ui_capture.py` + chat fixture |
| L4 Artifact integrity | `release-artifacts.yml` | MD5/CRC32C (GCS metadata), SHA-256, `apksigner`, `aapt2`, `zipalign -P 16`, source ZIP gitleaks |
| L5 Secret hygiene | `secret-scan.yml` (हर push), local pre-commit/pre-push hooks | gitleaks v8.30.1 |
| L6 Physical ARM64 device | उपयोगकर्ता का फ़ोन | §5 protocol: **NOT RUN** |
| L7 Account / Arena E2E | उपयोगकर्ता का फ़ोन + उसका अपना login | §6 protocol: **NOT RUN** |

## 2. परिणाम (platform अनुसार)

### 2.1 Android emulator: UI journey (run 38701948978; ARM64 run 38699920976)
| Target | Package / version | Screens captured | ANR | Status |
|---|---|---|---|---|
| `chrome_ref` | `com.android.chrome` 133.0.6943.137 (image में preinstalled) | 20/21 (15b dark menu: `menu_button` MISS) | 0 | PASS (Android emulator): reference capture |
| `chromium_desktop_x64` | `org.chromium.chrome` 155.0.8059.0 (805900079) | 21/21 | 0 | PASS (Android emulator): install/launch/FRE/journey |
| `chromium_arm64` | `org.chromium.chrome` 155.0.8059.0 (805900004), arm64-v8a via `libndk_translation` | 21/21 (run 38699920976) | 0 | PASS (Android emulator), पर अस्थिर (नीचे) |
| `chromium_arm64` | वही | 7 (run 38701948978) | **37** | **FAIL**: translation में ANR, browser UI तक नहीं पहुँचा |
| सभी 3 (दोहराव) | वही | 20 / 21 / 21 (run 38704128045) | 0 / 0 / 0 | PASS (Android emulator) |

ARM64 का कुल रिकॉर्ड (journey): 6 runs (38695373107, 38697226252, 38698517502, 38699920976, 38701948978, 38704128045) में से 2 में ANR से FAIL।

**UI parity:** Chromium 155 बनाम Chrome 133 के सभी 20 साझा screens = `mismatch` (`reports/ui-compare/*/COMPARISON.md`)। **Stable 155 के सामने: NOT RUN / BLOCKED।**

### 2.2 Startup और memory (emulator; प्रतिनिधि नहीं)
एक ही config पर दो runs के बीच बड़ा अंतर दिखा (जैसे Chrome 133 का cold median run 38701948978 में 824 ms और run 38704128045 में 1263 ms)। इसलिए emulator timings केवल smoke-level हैं और browsers की तुलना के लिए **अनुपयुक्त** हैं।

| Target | cold median / p95 ms | warm median / p95 ms | PSS KB | Run |
|---|---|---|---|---|
| Chrome 133 | 824 / 957 | 511.5 / 699 | 132,082 | 38701948978 |
| Chromium 155 x86_64 | 721.5 / 819 | 626.5 / 693 | 156,473 | 38701948978 |
| Chromium 155 ARM64 (translation) | 1531.5 / 1685 | 1001 / 5523 | 499,439 | 38699920976 |
| Chrome 133 | 1263 / 1345 | 779 / 1206 | 129,910 | 38704128045 |
| Chromium 155 x86_64 | 1181.5 / 1299 | 1136.5 / 1666 | 156,099 | 38704128045 |
| Chromium 155 ARM64 (translation) | 1404.5 / 1510 | 943 / 4909 | 508,221 | 38704128045 |

### 2.3 Synthetic long-chat fixture (10 cases: T1 300 messages, T2 4 updates @1 s, T3 draft/focus/selection, T4 anchor drift ≤1 px, T5 duplicates, T6 gap-resync, T7 background catch-up, T8 reconnect resume, T9 no reload, T10 content-visibility)
| Platform | Browser | Result | Run / evidence |
|---|---|---|---|
| desktop/browser component | HeadlessChrome 155.0.0.0, Linux, viewport 500×764 (393×851 माँगा था; headless न्यूनतम width 500) | **3 × 10/10** | 38699618638, `evidence/chat-desktop-run-38699618638/` |
| Android emulator | Chrome 133 (com.android.chrome) | **10/10** (T1 first render 505 ms, T4 drift −0.13 px) | 38701948978, `evidence/ui-capture-run-38701948978/chrome_ref/chat_fixture.*` |
| Android emulator | Chromium 155 x86_64 | **10/10** (T1 312 ms) | 38701948978 |
| Android emulator | Chromium 155 ARM64 (translation) | **FAIL (environment)**: run 38704128045 में page पर "Aw, Snap!"। logcat: sandboxed renderer `SIGSEGV` in `libndk_translation.so` (`berberis::RunGuestCall`), हर नया renderer ~150 ms में crash। Run 38701948978 में ANR, run 38699920976 में harness ने गलत socket चुना | `evidence/ui-capture-run-38704128045/chromium_arm64_renderer_SIGSEGV/` |
| Android emulator (दोहराव) | Chrome 133 और Chromium 155 x86_64 | **10/10 और 10/10** दोबारा | 38704128045 |

यह **real Arena data, account session या native integration नहीं** है। यह केवल rendering रणनीति का synthetic परीक्षण है।

### 2.4 Artifact integrity (run 38700392608): PASS (static/signature/format only)
| फ़ाइल | SHA-256 | Signature | zipalign 16 KB |
|---|---|---|---|
| `ChromePublic-Android_Arm64.apk` (381,736,687 B) | `7f5793c0a152b583afbba6ff73ca0927e58cf9d66b19d11a321efaf78071d501` | v2, 1 signer | OK |
| `ChromePublic-AndroidDesktop_x64.apk` (414,179,322 B) | `a2e1ed8f06201687dbd85e3750780bf17c4bacc067b29ecf4c0f895ee1b93191` | v2, 1 signer | OK |
| `source-3524e07.zip` | `dc22789b25ea69afd7b59757b9d9fa1c2c783111c2a750f1767970622da5e50e` | gitleaks साफ़ | — |

Download के बाद local `sha256sum -c SHA256SUMS.txt` = 7/7 OK।

**अंतिम release run 38705582126** (commit `31b8091`, सभी docs/evidence सहित): दोनों APK के SHA-256 ऊपर वाले से **बिल्कुल समान** (fetch reproducible); `source-31b8091.zip` (358 files) SHA-256 `578d7d2fa1338e36598524410c599716caa7972ab479c26591836c588bed49d4`; 7/7 checksums local रूप से OK। सीमा: `apksigner --print-certs` का signer DN grep से नहीं आया। Signature verify हुई, पर signer की पहचान दर्ज नहीं है।

### 2.5 Unit / static
| Test | Result | Run |
|---|---|---|
| Python unit tests (crc32c, node parsing, omnibox regex regression, compare, loader regression) | 10/10 PASS | `unit-tests.yml` 38699618638 और बाद के |
| Node `ChatStore` tests | 6/6 PASS | वही |
| Build preflight standard runner पर exit 3 (disk < 100 GB) | PASS (अपेक्षित इनकार) | 38698511862 और बाद के |
| gitiles source-path check: 50/50 मौजूद; negative control (नकली path) = False | PASS | local, `reports/feature-parity.json` |
| gitleaks full history | PASS हर push पर; leak-detection self-test run 38692792832 में जानबूझकर FAIL (अपेक्षित) | `secret-scan.yml` |

### 2.6 Chromium source build pipeline (सत्र 2, 15-10-2026)
| परीक्षण | परिणाम | Evidence |
|---|---|---|
| Resume-विधि (local + CI unit): ninja बीच में रोकना → PAX pack/restore → बचा काम बराबर (16→16); negative control (seconds-only tar + नई source mtime) पर 30/30 rebuild, यानी watchdog इसे पकड़ता है | PASS (desktop/browser component) | `tests/test_scripts.py::TestStagedBuildResume` |
| Fresh stage: tag 155.0.8059.80 का बिना-history sync + android deps + hooks + gn gen + src pack (13.4 GB, 8 भाग) upload | PASS (CI) | run 38745313869 (s0), state release `crstate-155.0.8059.80-x64-a1` |
| Restore check: src download/checksum/extract (514 s), commit `43a195105613…` सत्यापित, gn (63,340 targets), `ninja -n` = 57,552 edges | PASS (CI) | run 38751068356 |
| Stage 0 → 1 हस्तांतरण (x64): s0 ने 33,501/57,552 edges बनाए, timeout पर ninja साफ़ रुका (rc 124), out-state 0.84 GB upload हुआ, s1 अपने-आप शुरू हुआ | PASS (CI) | job 116457313511, `progress.json` |
| Stage 1 (x64) restore + watchdog | PASS (CI): restore 677 s, बचे edges 24,051 → 24,053 (watchdog सीमा के भीतर) | job 116601424088 |
| Stage 1 (x64) compile | **build पूरा हुआ**: `[24053/24053] ACTION //chrome/android:chrome_public_apk__create` (~3 घंटे 50 मिनट) | job 116601424088 log |
| Stage 1 (x64) completion step | **FAIL (script bug)**: ninja के "no work to do" पर `grep` का exit 1, `set -euo pipefail` के कारण script रुक गई। APK upload नहीं हुआ और runner के साथ खो गया। Out-state s0 सुरक्षित रहा। सुधार: `scripts/ci/stage_lib.sh::count_remaining` (कभी non-zero नहीं), APK सबसे पहले upload, out-state हमेशा save, सत्यापन non-fatal पर स्पष्ट gates के साथ। Regression tests `TestStageLib` (3)। पुराना code local पर rc=1 से पुनःउत्पन्न किया | commit b7a2f0d |
| x64 पुनः-run (b7a2f0d, out-s0 से resume) | **FAIL (script bug #2)**: restore (646 s) के बाद `line 135: ./stage_lib.sh: No such file` — `cd "$ROOT"` के बाद relative `$0` से path बना। Compile शुरू नहीं हुआ; out-s0 सुरक्षित। सुधार eb4e22f में (`CI_DIR` `cd` से पहले) | run 38837246181 job 116769022289 |
| arm64 stage s2 (पुराना 47ce94e script) | **FAIL (bug #1, अनुमानित)**: build **पूरा** (8895/8895, `chrome_public_apk__create`), फिर exit 1 — APK खोया। out-s1 सुरक्षित | run 38750988168 job 116738710930 |
| Stage script का end-to-end अनुकरण (`tests/test_stage_e2e.py`) | **PASS (desktop component)**: असली script, workflow जैसा (`bash scripts/ci/chromium_stage.sh`, ephemeral ROOT), stub gh/sudo/zstd/gn/apksigner/aapt2, असली ninja। timeout-stage → पूरा (APK/BUILD_INFO/DONE) → already-done → branded variant (seed, 2 edges, package gate) → negative gate FAIL (APK फिर भी सुरक्षित) → patch हटाना; watchdog अब भी पकड़ता है। **Negative controls:** b7a2f0d पर वही `line 135: ./stage_lib.sh` त्रुटि; 47ce94e पर 64/64 के बाद exit 1 और APK नहीं — दोनों CI विफलताएँ हूबहू दोहराईं। साथ में monitor loop का orphan `sleep` (output pipe पकड़े रहता था) पाया, `setsid` + group kill से सुधारा | इसी commit |
| Patch तंत्र (`patches/`, `scripts/ci/patches.py`) — इस परियोजना के source बदलाव staged build में | **PASS (desktop component, static/unit)**: `TestPatches` (5) — ninja के साथ 4-stage अनुकरण: वही patches = 0 rebuild; patch बदला/हटाया = ठीक 2 प्रभावित outputs दोबारा, हटाए patch का output नहीं बचा; negative control (सीधा `patch`) stale output छोड़ता है; पुरानी state (बिना `patches` key) संगत; ख़राब patch / `../` प्रविष्टि = rc 1। CI पर असली Chromium के साथ: **NOT RUN** (baseline APK सत्यापन के बाद) | इसी commit |
| Out-state का नाम हर run/stage में अलग (`out-s<N>-r<run>-<attempt>`) | static: पहले एक ही नाम पर `--clobber` upload विफल होने पर एकमात्र out state नष्ट हो सकती थी (run 38837246181 अभी पुराने नामकरण पर है — जोखिम स्वीकार) | इसी commit |
| arm64 chain | s0, s1 PASS (timeout पर state save); s2 build पूरा पर bug #1 से APK खोया; **पुनः-run 38841258069 (6cb8de2) PASS**: restore 349 s, watchdog 8895→8895, patch_changed=0 args_changed=0, compile `[8895/8895]` ninja_rc 0, out-state 1.83 GB, APK + BUILD_INFO + DONE upload (2 घंटे 40 मिनट) | run 38841258069, `evidence/source-build-arm64-ui-run-38856553471/build_stage_log_excerpt.txt` |
| arm64 source APK सत्यापन (CI) | **PASS (static/signature/format only)**: `ChromePublic-155.0.8059.80-arm64.apk` 395,857,811 bytes, SHA-256 `a3a30881fa6d2a1e3a4fde98097309b9980f3b153bb3e8e0d6004b6d0cda98da`; apksigner rc 0 (v2, Chromium debug key, CN=Unknown); aapt2: `org.chromium.chrome` versionName 155.0.8059.80 (805908004), targetSdk 37, `native-code: arm64-v8a`, label "Chromium"; clang llvmorg-24-init-7747 | `evidence/source-build-arm64-ui-run-38856553471/BUILD_INFO.txt` |
| arm64 source APK: emulator install + browser UI journey (API 36, x86_64 + ARM translation) | **PASS (Android emulator)**: install Success; ui-capture में SHA-256 BUILD_INFO से मेल; first-run → NTP → omnibox → suggestions → page → Site controls → app menu → नया tab → tab switcher → Settings → History → Bookmarks → Downloads → dark → landscape → Incognito, सभी screens capture हुईं; cold start median 1809 ms (p95 1963), warm median 910 ms; PSS 555 MB | ui-capture run 38856553471 |
| arm64 source APK: web page rendering (emulator) | **FAIL (environment)**: हर page पर "Aw, Snap!"; 68 sandboxed renderer crash, `SIGSEGV` in `libndk_translation.so` (`berberis_HandleNoExec`) — official snapshot (run 38704128045) वाली ही समस्या, वही BuildId। Chat fixture `WebSocketTimeoutException`। असली ARM64 phone पर जाँच ज़रूरी (NOT RUN) | `evidence/source-build-arm64-ui-run-38856553471/` |
| arm64 source APK: असली phone पर install/परीक्षण | **NOT RUN** (प्रतीक्षा): user ने 16-10-2026 को अपने phone पर install की अनुमति दी। Download: draft release `crstate-155.0.8059.80-arm64-a1`; GitHub asset digest `sha256:a3a30881…98da` = BUILD_INFO SHA-256 | — |
| x64 chain पुनः-run (6cb8de2) | **PASS (CI)**: restore 656 s, watchdog 24051→24053 (सीमा में), patch_changed=0 args_changed=0, compile 24,053 edges ninja_rc 0 (~4 घंटे 14 मिनट), out-state 1.74 GB, APK + BUILD_INFO + DONE | run 38841255946 |
| x64 source APK सत्यापन (CI) | **PASS (static/signature/format only)**: `ChromePublic-155.0.8059.80-x64.apk` 397,403,679 bytes, SHA-256 `11c8110a952f6c5bb4825ade3a53cdfe13292bd76c53a8f15ddd5f76a327c392`; apksigner rc 0 (v2, वही Chromium debug cert `32a2fc74…`); aapt2: `org.chromium.chrome` 155.0.8059.80 (805908008), targetSdk 37, `native-code: x86_64` | `evidence/source-build-x64-ui-run-38865720986/BUILD_INFO.txt` |
| x64 source APK: emulator install + पूरा UI journey + page rendering (API 36 x86_64, native) | **PASS (Android emulator)**: install Success; SHA-256 BUILD_INFO से मेल; first-run → NTP → omnibox → suggestions → example.com render → Site controls → app menu → नया tab → tab switcher → Settings → History → Bookmarks → Downloads → dark → landscape → Incognito; **renderer crash 0**; cold start median 1432.5 ms (p95 1516), warm median 736 ms (p95 1679); PSS 178 MB | ui-capture run 38865720986 |
| x64 source APK: synthetic long-chat fixture (Arena जैसा व्यवहार, असली Arena नहीं) | **PASS (Android emulator)** 10/10: 300 messages first render 839.5 ms; streaming in place; draft/focus/selection सुरक्षित; reading-position drift −0.11 px; duplicates ignored; gap resync; background catch-up 1 render; reconnect exactly-once; no reload; content-visibility | `evidence/source-build-x64-ui-run-38865720986/chat_fixture.txt` |

पहले के `build_chromium_baseline.sh --preflight-only` (exit 3) का अर्थ अब केवल इतना है कि वह local guard 100 GB से कम disk पर मना करता है। Standard runner पर cleanup के बाद 111 GB मिलते हैं (मापा गया)। "Source build असंभव" वाला पुराना निष्कर्ष वापस लिया गया (RESEARCH_REPORT §3b)।

## 3. विफलताओं का इतिहास (ईमानदार क्रम; कुछ भी पहली बार में पास नहीं हुआ)
| # | Run | क्या हुआ | कारण | सुधार |
|---|---|---|---|---|
| 1 | 38695330921 (ui-capture #1) | cancelled | emulator-runner `script:` की हर line अलग shell में चलती है, multi-line logic टूटा | `scripts/ci/run_capture.sh` wrapper |
| 2 | 38695373107 (#2) | Chromium jobs सफल; `chrome_ref` incognito के बाद अटका (uiautomator/dumpsys खाली, `am start` timings hang), cancel किया | Incognito (FLAG_SECURE) के बाद adb/uiautomator stall | Incognito अंत में, force-stop + relaunch, adb timeouts, watchdog |
| 3 | 38695373107 | `search_box` regex ने `search_box_plus_button` पकड़ा, attach sheet खुला | substring match | exact ids `:id/(search_box_text|url_bar)$` + regression unit test |
| 4 | 38697226252 (#3) | ARM64: FRE पर "Chromium isn't responding" ANR, आगे के सभी steps MISS | ARM translation में धीमापन | ANR dialog पर "Wait" (`aerr_wait`), गिनती `meta.json` में |
| 5 | 38697226252 | desktop_x64: page info, menu, tabs MISS | Page-info के लिए status icon की जगह blind tap ने omnibox focus किया और bottom toolbar छिप गया | blind tap हटाया; app menu → "Site controls" fallback |
| 6 | 38697226252 और पहले | `16_landscape` असल में portrait (1080×2400) | Android 16 पर `settings put system user_rotation` पर्याप्त नहीं | `wm user-rotation lock 1` + PNG आकार की जाँच (`landscape_rotated`) |
| 7 | 38699368721 (unit-tests) | chat desktop jobs FAIL: `Cannot find module …/experiments/chat-rendering` | Node 22 में `node --test <dir>` directory स्वीकार नहीं करता | explicit test file path |
| 8 | 38699920976 (#5) | ARM64 chat fixture: harness exit 2 | `webview_devtools_remote_*` socket चुन लिया गया | `chrome_devtools_remote` को प्राथमिकता; सभी sockets log में |
| 9 | 38698517502 (#4), 38699920976 (#5) | `chrome_ref` / desktop jobs 25 min से ज़्यादा अटके; मैंने cancel किए | Wrapper में `adb logcat -d` / `wait-for-device` बिना timeout के | हर adb call पर `timeout`; प्रति capture एक ही dump |
| 10 | 38701948978 (#6) | ARM64: 37 ANR, 7 screens, fixture harness exit 2 | Translation में अस्थिरता (5 में से 2 ARM64 runs) | सुधार संभव नहीं: emulator की सीमा। **असली ARM64 फ़ोन आवश्यक** |
| 12 | 38704128045 (#7) | ARM64: journey 21/21, 0 ANR; पर chat fixture tab में "Aw, Snap!", harness `WebSocketTimeoutException` | Renderer process ARM translation में SIGSEGV (`libndk_translation.so`); यही crash runs 38699920976 और 38701948978 के logcat में भी (11–12 बार); x86_64 और Chrome 133 में 0 | Emulator पर ठीक नहीं हो सकता। ARM64 web-rendering परिणाम **केवल असली ARM64 फ़ोन** से |
| 11 | पुराना (पिछली chat) | synthetic chat प्रयोग की मूल फ़ाइलें इस workspace में मौजूद नहीं थीं | handoff में बताए paths (`/home/user/android-browser/…`) उपलब्ध नहीं | प्रयोग **नए सिरे से बनाया** (`experiments/chat-rendering/`)। पिछली रिपोर्ट के 30/30 और उसकी विफलताओं (≈9647 px ऊँचाई, 139 px scroll shift, fractional CSS) को यहाँ दोबारा सत्यापित नहीं किया गया |

## 4. चलाया नहीं गया / blocked
| क्या | क्यों | क्या चाहिए |
|---|---|---|
| Chrome Stable 155 का UI reference | Emulator image में Chrome 133; Play update के लिए account चाहिए; third-party mirror नहीं | उपयोगकर्ता के फ़ोन से screenshots (§5) |
| Full Chromium source build | ≥100 GB disk / ≥8 GB RAM (official); standard runner preflight exit 3 | Large runner (paid, आपकी अनुमति) या आपकी मशीन |
| Physical ARM64 device install/launch/perf | फ़ोन उपलब्ध नहीं | §5 |
| Google sign-in, Sync | Chromium fork में Google API keys/OAuth प्रतिबंधित | Google की अनुमति / अपनी keys; website login का उपयोगकर्ता-साक्षी test |
| Arena long chat E2E | उपयोगकर्ता का session; credentials कभी नहीं माँगे जाएँगे | §6 |
| TalkBack, large-font, animation/latency निरीक्षण | journey में अभी नहीं | अगला चरण |

## 5. उपयोगकर्ता द्वारा: फ़ोन reference + ARM64 install (privacy-safe)
1. Chrome → Settings → About Chrome: version लिखें। फ़ोन model, Android version, Display size, Font size, theme और navigation (gesture/3-button) भी लिखें।
2. `research/CHROME_UI_INVENTORY.md` §2 के क्रम में screenshots लें: NTP, omnibox focus, `example.com` page, page info, menu, tab switcher, settings, history, bookmarks, downloads, dark theme, landscape। **Account, email, photo या निजी tabs वाले screens न भेजें।**
3. `release-artifacts` से `ChromePublic-Android_Arm64.apk` install करें। बताएँ: install हुआ? खुला? first-run screens? crash? `example.com` खुला? पहली स्क्रीन का screenshot भी भेजें।

## 6. उपयोगकर्ता-साक्षी Arena protocol (credentials कभी साझा नहीं)
पूर्व-शर्त: आप स्वयं अपने फ़ोन पर login करें। मैं password, OTP, cookie या token कभी नहीं माँगूँगा। Screenshots में chat का text न दिखे (blur करें)। URLs से user/chat IDs हटाएँ।
हर browser (Chrome Stable और Chromium artifact) में, एक ही फ़ोन और network पर, ये steps चलाएँ:
- (i) लंबी chat cold-open (app बंद करके) और warm-open: पहली दिखने वाली सामग्री तक का समय (stopwatch/screen recording)।
- (ii) नया प्रश्न भेजें: उत्तर stream होता दिखा या refresh करना पड़ा?
- (iii) पूरे test में hard reload की ज़रूरत पड़ी? (हाँ/नहीं, कितनी बार)
- (iv) उत्तर आते समय app background → 30 s → foreground; rotation; airplane mode 10 s on/off: उत्तर जारी रहा या टूटा?
- (v) composer में अधूरा draft + selection + पुराने संदेश पर scroll: update के बाद सब वैसा ही रहा?
- (vi) कोई संदेश दो बार गया या दिखा?
परिणाम हाँ/नहीं और समय के रूप में भेजें। यह test **Google website login**, **Chrome Sync**, **Arena session** और **live transport** को अलग-अलग दर्ज करता है।
