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
| arm64 source APK: असली phone पर install/परीक्षण | **PASS (actual device, user-reported)**: 16-10-2026 को दोबारा download के बाद install सफल और websites ठीक खुलीं (user की पुष्टि; screenshot/model/Android version अभी नहीं मिले)। पहली कोशिश में "package appears to be invalid" आया था, जो दोबारा download करने पर ठीक हो गया। इससे अनुमान है कि पहली फ़ाइल अधूरी या खराब थी, पर यह जाँचकर पक्का नहीं किया गया। Emulator पर ARM translation वाला renderer crash असली ARM phone पर नहीं दिखा | user संदेश 16-10-2026 |
| x64 chain पुनः-run (6cb8de2) | **PASS (CI)**: restore 656 s, watchdog 24051→24053 (सीमा में), patch_changed=0 args_changed=0, compile 24,053 edges ninja_rc 0 (~4 घंटे 14 मिनट), out-state 1.74 GB, APK + BUILD_INFO + DONE | run 38841255946 |
| x64 source APK सत्यापन (CI) | **PASS (static/signature/format only)**: `ChromePublic-155.0.8059.80-x64.apk` 397,403,679 bytes, SHA-256 `11c8110a952f6c5bb4825ade3a53cdfe13292bd76c53a8f15ddd5f76a327c392`; apksigner rc 0 (v2, वही Chromium debug cert `32a2fc74…`); aapt2: `org.chromium.chrome` 155.0.8059.80 (805908008), targetSdk 37, `native-code: x86_64` | `evidence/source-build-x64-ui-run-38865720986/BUILD_INFO.txt` |
| x64 source APK: emulator install + पूरा UI journey + page rendering (API 36 x86_64, native) | **PASS (Android emulator)**: install Success; SHA-256 BUILD_INFO से मेल; first-run → NTP → omnibox → suggestions → example.com render → Site controls → app menu → नया tab → tab switcher → Settings → History → Bookmarks → Downloads → dark → landscape → Incognito; **renderer crash 0**; cold start median 1432.5 ms (p95 1516), warm median 736 ms (p95 1679); PSS 178 MB | ui-capture run 38865720986 |
| x64 source APK: synthetic long-chat fixture (Arena जैसा व्यवहार, असली Arena नहीं) | **PASS (Android emulator)** 10/10: 300 messages first render 839.5 ms; streaming in place; draft/focus/selection सुरक्षित; reading-position drift −0.11 px; duplicates ignored; gap resync; background catch-up 1 render; reconnect exactly-once; no reload; content-visibility | `evidence/source-build-x64-ui-run-38865720986/chat_fixture.txt` |
| b1 (Swiftra branding + release signing): local तैयारी | **PASS (desktop component)**: (1) `TestPatches` overlay — ninja के साथ multi-stage: overlay लगे, स्थिर रहे (0 rebuild), बदले/हटाने पर प्रभावित outputs दोबारा बनें; लक्ष्य फ़ाइल src में न हो या symlink हो तो rc 1। (2) repo के 16 overlay लक्ष्य Chromium 155.0.8059.80 (gitiles) में मौजूद हैं, और pixel आकार मूल icons जैसे हैं। (3) `test_stage_e2e`: build step को secrets नहीं मिलते; secrets न हों / गलत key / गलत password = FAIL और DONE नहीं; सही key पर cert मिलान, DONE और कहीं भी password नहीं; a1 baseline पर patches = REFUSED; non-debuggable gate। (4) **असली tools**: `apksigner` (build-tools 36 और 37) ने असली x64 APK (397 MB) को Swiftra keystore से sign किया (3 s); cert `029de0fa…fe06` keytool से मेल खाता है; सभी `.so` का offset %16384 = 0 बना रहा। `finalize_apk.sh` असली tools पर: सही cert → DONE, गलत cert → FAIL और कुछ upload नहीं; password किसी फ़ाइल या log में नहीं | commits ca039ba, 80d7cf2 और यह commit |
| b1 पहला CI run (x64 38892991040, arm64 38892993229) | **FAIL (script bug #3, सुरक्षित तरीके से रुका)**: दोनों का incremental build पूरा हुआ (restore + compile ~17 मिनट), presign APK सुरक्षित रहा, sign rc 0। पर Chromium 155 के **build-tools 37** का `apksigner` cert को `V3.0 Signer: certificate SHA-256 digest:` format में छापता है, जबकि parser केवल पुराना `Signer #1 certificate …` (build-tools 36, जिससे local जाँच हुई थी) पहचानता था → cert "?" → gate ने upload रोका, DONE नहीं लिखा। यह format हमारे a1 evidence (`V2 Signer: …`) में पहले से था; मिलान पहले कर लेना चाहिए था। सुधार: `stage_lib.sh::cert_digests` दोनों formats पढ़ता है, सारे signer digests इकट्ठा करता है, अलग-अलग digest मिलें तो FAIL। Tests `TestCertDigests` (6, असली outputs से)। build-tools 37 के असली apksigner पर दोबारा: सही → DONE, गलत → FAIL | runs 38892991040, 38892993229 |
| b1 पुनः-run (b621868; x64 38896651753, arm64 38896660409) | **PASS (CI, static/signature/format only)**: restore के बाद 0 edges, sign step में release signing; दोनों APK: `com.swiftra.app`, label "Swiftra", non-debuggable, v3 `CN=Swiftra` RSA-4096, cert `029de0fa…10fe06` अपेक्षित मान से मेल। x64 SHA-256 `9d88a604…8e79` (397,723,443 B), arm64 `5135db70…0316` (396,177,489 B) | `evidence/source-build-b1-swiftra-run-38899621628/BUILD_INFO-*.txt` |
| b1 APK में icon | **PASS (static)**: manifest → resource resolution; 15 launcher images pixel-identical (APK में WebP; दिखने वाला अंतर 0); themed monochrome में Swiftra path, Chromium path नहीं | `…/branding_check.md`, `…/apk_extracted_icons.png` |
| b1 x64: emulator UI journey + chat fixture | **PASS (Android emulator)**: सभी screens `com.swiftra.app` में, renderer crash 0; cold median 1060 ms (p95 1184), warm median 796 ms; PSS 127 MB; fixture 10/10। Non-debuggable होने पर भी DevTools socket काम किया | ui-capture run 38899621628 |
| b1: app के अंदर branding | **PARTIAL**: launcher नाम/icon/package Swiftra; पर app के अंदर "Make Chrome your own", "About Chrome", "Customize and control Google Chrome", "Chromium won’t save", FRE पर Chromium logo, NTP tiles chromium.org — b2 में | `…/branding_check.md` |
| b1 device E2E पहला दौर (x64 ui-capture 38904972738, arm64 Redroid 38905074382/38907136262/38909149132) | **FAIL → ठीक किया**: (1) **launcher icon उत्पाद bug** — Pixel launcher पर केवल gradient गोला, Launcher3 पर सफ़ेद खाली square (roundIcon/ic_launcher की Chromium संरचना; glyph केवल foreground में था); (2) check 06 parser (stderr/stdout क्रम); (3) check 07 gfxinfo web frames नहीं गिनता; (4) Redroid पर `monkey` launch विफल; (5) FRE पर BACK; (6) adb "more than one device" (Redroid) | `evidence/device-e2e-b1-iconfix-2026-10-16/README.md` |
| b1 icon fix (26f8a45; builds x64 38907965672, arm64 38907969325) | **PASS (static/signature/format only)**: 768 edges incremental, release signer `029de0fa…`; x64 `e298584d…c38e`, arm64 `11cd819c…dbbb`; regression test पुराने icons पर FAIL / नए पर PASS | builds |
| b1 x64: emulator E2E (icon fix) — run 38913748996 | **PASS (Android emulator)**: device checks 9/9 (Pixel launcher में Swiftra icon सही, non-debuggable, same-key update, दूसरी key का update `INSTALL_FAILED_UPDATE_INCOMPATIBLE`, touch scroll, reinstall); UI journey ready; fixture 10/10; app crash 0; cold 712 ms / warm 498 ms / PSS 151 MB (प्रतिनिधि नहीं) | `evidence/device-e2e-b1-iconfix-2026-10-16/x64-emulator-run-38913748996/` |
| b1 arm64: native arm64 Android (Redroid 14 container, ubuntu-24.04-arm, software GPU) — run 38913752278 | **PASS (Android emulator श्रेणी — असली phone नहीं)**: वही arm64 APK असली ARM CPU पर बिना translation; device checks 9/9 (Launcher3 icon सही); UI journey ready (default-browser system prompt दर्ज + Cancel); fixture 10/10; app crash 0, ApplicationExitInfo खाली; cold 669.5 ms / warm 246.5 ms / PSS 284 MB (प्रतिनिधि नहीं) | `evidence/device-e2e-b1-iconfix-2026-10-16/arm64-redroid-run-38913752278/` |
| Tab switcher BACK व्यवहार | **PASS (Android emulator)** x64 API 36 + **PASS (arm64 Redroid 14 — real phone नहीं)**: Hub खुला (2 tabs), BACK -> वही tab (Chromium 155 `HubCoordinator.handleBackPress()` -> `selectCurrentTabAndHideHub()` जैसा); relaunch 0, crash 0, device checks 9/9। पहले लिखा FAIL harness की गलती थी (NTP promo sheet ने tap निगला) — वापस लिया | runs 38918534121 / 38918537719 (और 38916663718 / 38916666704); `evidence/tab-switcher-back-parity-2026-10-16/` |
| b2 in-app branding (Swiftra नाम/logo, app UI में Chrome/Chromium नहीं) | **PASS (Android emulator)** x64 API 36 + **PASS (arm64 Redroid 14 — real phone नहीं)**: मापे गए ~24 screens पर branding leaks 38/36 -> **0/0** (`scripts/ci/branding_scan.py`); FRE Swiftra logo + "Make Swiftra your own", footer केवल ToS (non-branded build में UMA बंद — झूठा "sends usage and crash data to Google" हटाया); पहली NTP tiles Facebook/YouTube/…; Incognito "Swiftra won't save"; device checks 9/9, chat 10/10, crash 0। सीमा: बाकी screens/grds, inflected भाषाएँ native review, G1 legal (Google ToS link) | builds 38935765027 / 38931729325; E2E 38938906018 / 38938909743; `evidence/b2-branding-2026-10-16/` |
| c1 सत्यता (Settings में Chrome-शब्द-रहित असत्य दावे) | **PASS (Android emulator)** x64 API 36 + **PASS (arm64 Redroid 14 — real phone नहीं)**: Settings crawler (17-18 top-level items, 15 capture) + truth scan (`branding_scan.py` FALSE_CLAIMS/EXPECTED): असत्य दावे x64 4 / arm64 6 -> **0/0**। About "Copyright Google LLC" -> "The Chromium Authors" (81 भाषाएँ Chromium desktop अनुवाद से); Google services का निष्क्रिय "sends usage statistics and crash reports to Google" switch छिपा (UMA बंद + crash upload URL null); Safety check "Swiftra is up to date" (जाँच कभी नहीं चलती) -> "Can’t check Swiftra version / Version 155.0.8059.80", dead "Go to Google Play" button छिपा। device checks 9/9, chat 10/10, crash 0। arm64 का एक run (38993004513) Redroid graphics stack ढहने से 6/9 — rerun 9/9 (दोहराया नहीं)। सीमा: copyright wording G1 legal review; "Make searches and browsing better" रखा (zero-suggest से दावा सत्य हो सकता है) | builds 38995292721 / 38995294189; E2E 38996588758 / 38996590010; `evidence/truthfulness-c1-2026-10-17/` |
| b1 arm64: असली phone | **NOT RUN** (assistant के पास physical device नहीं; user ने install न करने को कहा) | — |

पहले के `build_chromium_baseline.sh --preflight-only` (exit 3) का अर्थ अब केवल इतना है कि वह local guard 100 GB से कम disk पर मना करता है। Standard runner पर cleanup के बाद 111 GB मिलते हैं (मापा गया)। "Source build असंभव" वाला पुराना निष्कर्ष वापस लिया गया (RESEARCH_REPORT §3b)।

### 2.7 Swiftra Shield: on-device Safe Browsing (c2, 17-10-2026)
APKs (commit 9617ac5, patch 0006): x64 `5fe4be348a8603f87efaeae116a26b7039091e1050957a0de336d3fc4c823345`, arm64 `0c643f9121f2bc64e56bf3f225494d5c6f368dbae86347be6b3407e8153480b8` (builds 39006048509 / 39006052864; signer `029de0fa…fe06`)।
पिछले (c1b) APKs: x64 `ce52a4bf…a155`, arm64 `827485c0…660f`।

| जाँच | परिणाम | प्रकार / प्रमाण |
|---|---|---|
| Canonicalization (Python ↔ Java) 37 vectors + 14 URLs | PASS | desktop component, `tests/test_shield.py` |
| Chromium errorprone + NullAway (JSpecify) @155 flags, दोनों Java files | 0 चेतावनी (negative control ने चेतावनी पकड़ी) | static; Chromium custom plugin नहीं चला |
| `shield-db.yml` run 39006024815: build → sign → self-verify → publish | PASS, 908,341 entries, 5,686,256 B | CI |
| Public URL से बिना login download + embedded key से verify | Verified OK, sha `1284e47e…` | static/signature |
| Published list पर 72 lookups (28 लोकप्रिय भारतीय/वैश्विक sites SAFE, 4 canaries, 40 random असली phishing URLs) | 72/72 | desktop component |
| Device पर list download + verify + decode | `list updated: 908341 entries` (दोनों) | PASS (Android emulator / Redroid) |
| Interstitial E2E, 6 cases (local safe, local phishing, local malware, Google test phishing/malware, example.com) | x64 run 39010302985: 6/6; arm64 run 39010304091: 6/6; block 6.1–6.2 s में तैयार | PASS (Android emulator), PASS (Redroid arm64), DOM text via DevTools |
| Regression: device checks 9/9, crash 0, ANR 0, false_claims 0 | PASS | दोनों |
| Cold/warm median start | x64 827.5/597 ms; arm64 704/248 ms (c1b: 1238/1050.5, 720.5/246.5) | emulator, प्रतिनिधि नहीं |

विफलताएँ और सीमाएँ:
- पहला shield-db run 39005982060 FAIL: runner पर pytest नहीं था (unittest में बदला)।
- पहला E2E 39007913283 / 39007914486: Shield FAIL (harness bug)। DevTools WebSocket 403 (Origin) के कारण हर case "unknown" आया। Screenshots में फिर भी interstitials दिखे। Fix 5ea03cf (`suppress_origin`)।
- Redroid (arm64) screenshots एक frame पीछे रहते हैं (guest GPU), इसलिए वहाँ फ़ैसला DOM text से होता है। x64 के screenshots सभी 6 सही हैं।
- नई crawl coverage (Autofill subpages) में 8 branding leaks मिले ("Chromium can autofill…", "…in Chrome")। ये Shield से नहीं हैं; इन्हें c2b में ठीक करना है।
- Interstitial पर "Chrome strongly recommends…" और "Turn on enhanced protection to get Chrome's highest level of security" दिखते हैं। यह branding और सच्चाई दोनों का मुद्दा है (c2b)।
- Evidence: `evidence/shield-c2-2026-10-17/`।

### 2.8 सच्चा interstitial + Enhanced protection (c2b, 17-10-2026)
APKs (commit a58f8ec, patches 0001–0007): x64 `20e288a58e0dbfdecd603deedb0d46de6fa0437056f7dcf3b5ecc7230e23b8e6`, arm64 `f861a40204cdba3f92863e57c74c1c70ff152abcf6b7312eab489f65ebc81e68` (builds 39025744172 / 39025748557)।

| जाँच | परिणाम | प्रकार / प्रमाण |
|---|---|---|
| 0002 transform: components_strings + security_interstitials/autofill/autofill_payments grdp + generated_resources.grd (केवल grd) | 91 + 101 IDs; translation coverage-guard PASS; हिंदी जाँची | desktop component (असली grit + 81 xtb) |
| 0007 patch pristine @155 पर fuzz 0 | PASS | static |
| 0007 C++ compile | Chromium build PASS (दोनों ABI) | build |
| Unit suite | 83 passed (CI unit gate भी success) | desktop component |
| Google RT endpoint बिना key (`tools/sb_rt_probe.py`) | phishing/unwanted DANGEROUS, canary SAFE | desktop, live network |
| Standard: 8 cases (6 पुराने + public canary + unwanted) | x64 8/8, arm64 8/8; unwanted **खुलता है** (UwS सूची नहीं) | PASS (Android emulator / Redroid arm64), DOM text |
| Enhanced (Settings UI से): 5 cases | x64 5/5, arm64 5/5; unwanted → harmful interstitial (Google RT सक्रिय) | वही |
| हर blocked page की honesty check | 0 समस्याएँ (दोनों) | DOM via DevTools |
| Native UI में "Chrome" (Enhanced banner) | round 1 में leak (visual) → fix → round 2: 0 | uiautomator + screenshot |
| leaks / false_claims / crash / ANR / device checks | 0 / 0 / 0 / 0 / 9/9 (दोनों) | regression |
| Cold/warm median | x64 1270/976 ms (c2: 827.5/597); arm64 711/254 ms (c2: 704/248) | emulator, प्रतिनिधि नहीं; x64 धीमापन जाँचना बाकी |

विफलताएँ और सीमाएँ:
- Round 1 (4935b29; runs 39022805609 / 39023099504) के tests PASS हुए, फिर भी screenshot में Enhanced banner "You have Chrome’s strongest security…" और Google "G" icon दिखा। automated check native UI नहीं देखता था। Fix a58f8ec; harness में native-UI check जोड़ा गया।
- 0007 का real-time fallback (Google SAFE → Shield) device पर नहीं चला। async mode में local DB checker ने block किया। यह हिस्सा static only है।
- Enhanced में Shield verdicts भी Google को `WARNING_SHOWN` report के रूप में जाते हैं। यह Enhanced की सूचना के भीतर है, पर privacy के लिहाज़ से दर्ज है।
- Standard का विवरण ("…URLs and bits of page content are sent to Google Safe Browsing") सच है या नहीं, यह खुला है। optimization guide में कोई model नहीं दिखा।
- "Learn more about this warning" link अब भी Google Chrome help page पर जाता है (मौजूदा स्थिति, विश्लेषण बाकी)।
- G1: Google का internal Safe Browsing endpoint इस्तेमाल करना Google की शर्तों का कानूनी प्रश्न है (BLOCKED)।
- Evidence: `evidence/shield-c2b-2026-10-17/`।

### 2.9 Settings की सच्चाई + variations + NetLog audit (c2c, 17-10-2026)
- Patch: 0008 standard-local-and-esb-honest (PhishGuard Standard में बंद, ESB विवरण के झूठे bullets छिपे), 0002 FACT_FIXES (Standard/ESB summary), `disable_fieldtrial_testing_config = true` (Chromium `testing/variations/README.md` की सलाह)।
- E2E (`scripts/ci/shield_e2e.py`): Standard 8/8, Enhanced 5/5, SB page truth, ESB details truth, chrome://version variations source, NetLog trace (Standard window + Enhanced positive control)।
- परिणाम: x64 emulator (39053115486, 39055927613) और arm64 Redroid (39053116960, 39055928718) दोनों पर SHIELD_E2E PASS। Standard में Google URL requests 0, SB hosts 0; Enhanced में `safebrowsing.google.com/safebrowsing/clientreport/{realtime,malware}` दिखते हैं।
- सीमा: trace startup के बाद शुरू; connection-level preconnect events बाकी; असली फ़ोन NOT RUN।
- प्रमाण: `evidence/c2c-2026-10-17/`।

### 2.10 Cold start network audit + 0009 quiet start (c2d, 18-10-2026)
- तरीका: `scripts/ci/startup_netlog.py` — debug-app command line से Chromium NetLog process start से (APK अपरिवर्तित); सब tabs बंद → cold
  start → NTP → idle। Gate: Safe Browsing संपर्क, या 0009 द्वारा हटाए गए requests (`quiet_violations`), या AI Mode `folae` के बिना
  ListAccounts = FAIL। Negative control: 0009 से पहले के data पर gate FAIL (ddllog, discover-pa)।
- परिणाम: x64 emulator 39094623643 और arm64 Redroid 39094624570 — SHIELD_E2E PASS, STARTUP_NETLOG PASS, cases 13/13, device 9/9,
  झूठे दावे 0, leaks 0, crash 0, ANR 0। NTP screenshot: "Can't refresh Discover" गया, doodle/AI Mode/tiles बने रहे।
- सीमा: metrics recorders वाले ListAccounts बदलाव केवल code-स्तर पर सत्यापित; असली फ़ोन NOT RUN।
- प्रमाण: `evidence/c2d-2026-10-18/`।

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

### 3.1 Safety check update-state harness (19-10-2026, next session)

- Handoff §9.2: `scripts/ci/safety_update_e2e.py` adds native Safety check acceptance for a real production signature check, rejected signature with no prior success, genuine recent success, stale success and future-clock timestamp. Only update preferences change temporarily; wrapped OSCrypt key and unrelated prefs are preserved and update entries are restored.
- Both existing x64 emulator/arm64 Redroid workflows support `checks=safety_update` for focused unchanged-APK acceptance; focused jobs cannot dispatch publish. Full release E2E requires `SAFETY_UPDATE_E2E PASS` when both 0005 and 0020 are present.
- First full local run: **2 failed, 197 passed, 8 skipped**. Caught a missing ARM focused-publish guard and an A/B test's stale exact-condition assertion. Both fixed before pushing or dispatching.
- Final local run: **199 passed, 8 skipped in 123.33s**; both workflow YAML parses, shell syntax, `git diff --check`, and pristine @155 patch 0005/0020 dry-runs (fuzz 0) passed. **PASS (static only)**, not Android evidence.
- First focused x64 run **39264127317** (`acf1bf0`): `SAFETY_UPDATE_E2E NOT_RUN cases=0/5 restored=False ParseError (private details withheld)`; failed before any update prefs were changed. The setup result artifact was inspected. Added metadata-only parse diagnostics and Activity backgrounding before force-stop (asynchronous SharedPreferences writes); the precise parse cause is not yet established. This is a harness blocker, not a reproduced app failure. No private prefs were emitted or retained in artifacts.
- Second focused run **39265508902** (`490ea11`) still `NOT_RUN`: metadata identified Expat **code 14** at `(23, 66)` in a 43,894-byte text XML file, with 0 raw forbidden control bytes. AOSP FastXmlSerializer emits numeric control references that XML-1.0 Expat rejects. Backgrounding alone did not fix it; no private content was printed and no prefs were edited in that run.
- Added a lossless Android numeric-control-reference codec, not stripping/sanitizing values. Local codec negative-control assertion first rejected an equally valid `ET.ParseError` refusal (1 failed, 70 passed); corrected the expected refusal class before pushing. All 29 forbidden control values have semantic round-trip/preservation tests.
- Third focused run **39266966087** (`6fd3e52`): the control-reference parser passed initial loading, but an unacknowledged `adb exec-in` fixture write was read back as **0 bytes** at `bad_fresh:prepare`, and restoration failed. `SAFETY_UPDATE_E2E NOT_RUN cases=0/5 restored=False`; this was a disposable no-account emulator, not user data. The artifact was inspected; no private prefs were emitted.
- Replaced `exec-in` writes with `adb shell -T` (stdin/remote exit protocol). Prefs now stage in the private app directory, verify bytes + uid/mode/SELinux context, and atomically rename only after success; dropped stdin or changed metadata leaves the original intact. Added desktop functional negative controls and a hard physical-device refusal. Relevant suite: **78 passed**. Full local suite immediately before this IO correction: **235 passed, 8 skipped in 123.76s**.
- Fourth focused run **39268484164** (`07a332f`): **FAIL, 3/5, restored=True**. All five native states were correct, but both `current` modules were collapsed and hid the required version. Source + real screenshot confirmed upstream behavior. The follow-up taps the native header to expand it; the strict visible-version requirement is retained. JSON/screenshot are archived. This is not recorded as an Android PASS.
- Follow-up also refuses encoded-placeholder collisions and CR-to-LF changes, with all 32 controls + an entire-tree semantic round-trip invariant; two new local negative controls first failed and then drove the fixes. Wrapper support checks require both 0005+0020, including a check against the real tested APK's BUILD_INFO. Physical refusal has no cleanup side effects.
- Pinned `07a332f` CI unit run **39268484362**: **249 passed, 1 skipped in 123.18s**; three desktop chat-component trials each **10/10**, not actual Android/Arena acceptance. Local full suite after the side-effect-free refusal, before the expansion/collision follow-up: **243 passed, 8 skipped in 122.27s**.
- Fifth focused x64 run **39273364869**, driver `ff4944e`: **PASS (Android emulator), 5/5, restored=True**. All five PNG/XML/JSON artifacts inspected; both current cards were expanded and the required exact version was visible. Pre-install APK SHA-256 matched BUILD_INFO. Publish job skipped. Evidence: `evidence/safety-update-2026-10-19/x64-run-39273364869/`.
- CI at that earlier driver: **259 passed, 1 skipped in 124.54s**. ARM source build **39223539138** completed **success**; new signed native arm64 APK SHA-256 is `a3df4cf79519ce8b3cbcda0bdfb54b8bb5e88be0c78c7e309c30254caf248f02`.
- Latest driver `e28192e`: focused **x64 39278995763** and **native arm64 Redroid 39278999766** both **PASS (Android emulator): Safety 5/5, restored=True; then KEYSTORE_E2E PASS on that same profile**, sw1/no plaintext/wrapped pref/restart recovery/Keystore2 all true. Actual downloaded artifacts inspected and publish jobs skipped. Strict postcondition does not trust the legacy exit 0. Actual ABI versionCodes from aapt: x64 **805908008**, arm64 **805908004**.
- Current CI **39278996300: 266 passed, 1 skipped in 111.96s**; full local **259 passed, 8 skipped in 122.51s**, relevant **95 passed in 0.26s**. Local/runtime evidence remain separate. Full ARM Redroid artifact **39274414134** अब मिला और original तथा curated evidence दोनों पर **E2E_GATE PASS** दोबारा चला; device checks **9 passed / 0 failed**, security/feature markers सफल। यह defined gate है, universal no-regression नहीं: अलग-APK 0011 baseline के मुकाबले cold **750 vs 694.5 ms (+7.99%)**, और same-APK first-page LCP/एक bench metric भी धीमे थे। Actual mixed performance data `arm64-full-run-39274414134/performance-caveats.json` में सुरक्षित हैं; केवल Keystore को कारण नहीं ठहराया गया। Physical/account/current-Chrome gates अभी अलग हैं। Summary + required requirement table: `docs/safety-update-milestone-2026-10-19.md`. Research and separate update-button intent risk: `docs/safety-update-e2e.md`.

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


## 20-10-2026: सुरक्षा-समान startup ablation (पहला pass)

- Same installed source APK, सात modes (shipped + छह एकल performance-flag ablations), 4 counterbalanced blocks × 3 cold launches = 12/mode। Keystore/Safe Browsing/ad blocking/TLS/site isolation नहीं बदले जाते। केवल native launcher, about:blank और internal version receipt; कोई cert exception नहीं।
- Pinned CachedFlag source ने next-run Java cache trap बताया: native CLI बदलकर उसी startup को changed Java flag मानना गलत। Warm-up, selected cached booleans और crash/safe-mode counters की पुष्टि के बाद ही sample; private prefs में सीधा edit नहीं।
- Fixed `speed` AOT diagnostic state, installed SHA before/after, process-cold/PID proof; flags original bytes/mode restore, shipped cache re-prime, ART reset। यह TTFD/LCP/current-Chrome/phone acceptance नहीं।
- नया `startup_ablation` workflow mode publish/foreign-APK/A-B-baseline/device-check dispatch से बाहर है; केवल full mode publish कर सकता है। उसी profile पर strict existing Keystore postcondition जोड़ी गई।
- पहले focused local run में **2 failed / 113 passed**: पुराने tests केवल safety_update विकल्प/if-string अपेक्षित करते थे। Full-only mode guards के लिए assertions सुधारी गईं। फिर full collection में snapshot environment का protobuf dependency गायब था; आवश्यक workflow dependencies restore की गईं, test assertions नहीं हटाईं।
- अंतिम local full: **289 passed, 8 skipped in 126.06s**; shell syntax/py_compile/YAML full-only publication checks PASS (static only)। Actual दोनों-ABI Android runs pending हैं; runtime/feature-speed PASS का दावा नहीं। Protocol: `docs/startup-ablation.md`।


### 20-10: API helper exit-status negative control

- Host-only expected HTTP404 under this own repo returned exit **0** before fix: redactor hid curl failure. Added `pipefail` + default `--fail-with-body`; same safe negative control now **22**, authorized own-repo read **0**. Token/header never printed or put in argv. Hermetic no-network NON-credential tests **3 passed**. Scope: API adapter only, not Android product acceptance.
- Added host control proving startup activation repeats an unmeasured launch until the next-run Java cache actually matches; native CLI receipt alone is deliberately insufficient. Actual Android runs retain the pinned earlier driver; no product flags promoted yet.


### AOT Android outcomes + verify confirmation queued next (20-10)

- Driver `18b60ad`: x64 run **39387937370**, ARM64 **39387941069** दोनों completed success। Actual artifacts में 28 blocks/modes और **84/84 valid cold samples per ABI**, flags original bytes/mode restored, shipped cache re-primed, identical installed SHA before/after, post-Keystore PASS sw1/no plaintext/wrapped/restart/Keystore2। यह protocol execution MEASURED है, speedup PASS नहीं।
- सभी छह ablations के block-bootstrap intervals दोनों ABI पर zero काटते हैं। किसी product flag को नहीं हटाया/promote किया गया। Per-mode raw medians और block-normalized deltas अलग रखे हैं; एक point estimate का उपयोग नहीं किया गया।
- Pinned AOT driver CI **39387937287**, unit job **118512225309**: **296 passed, 1 skipped in 125.47s**। बाद के helper/control/compile-selection changes का full local **293 passed, 8 skipped in 128.40s**; relevant **121 passed**।
- अब `ablation_compilation=verify` वाला अगला Android pass तैयार है: वही APK/सुरक्षा/cached-flag receipts, लेकिन install-like reset state; AOT data को sideload-default signal का निष्कर्ष नहीं बनाया गया। Actual verify outcomes अभी NOT RUN हैं।


## 20-10: native update Intent source fix (runtime not claimed)

- Official Android API docs + pinned155 provider confirmed inherited REQUIRE_NON_BROWSER rejects browser-only handlers. New 0020 hunk routes the already verified project HTTPS URL to own package instead; no TLS/Download Shield/installer bypass, NEW_TASK/catch preserved.
- Pristine155 fuzz=0 dry-run PASS, source guard test PASS; full local **294 passed, 8 skipped in 125.74s**. A new unified-diff context blank line was caught by whitespace check, then the new hunk was narrowed (n=1) and fuzz=0 rechecked; no whitespace rule was disabled.
- Menu/badge/Safety history is not retroactively download PASS. New builds and actual tap/download both ABI pending. Native offers compare signed published_ms against lastUpdateTime, NOT versionCode; no guessed version-code policy change was made.


### Native update download acceptance, no visibility-only release proof

- Added `update_download_e2e.py`: untrusted manifest must not expose an offer; trusted existing public fixture opens the actual native menu item, taps it and waits for a newly downloaded own-repo APK whose complete SHA matches the signed entry. Never installs payload; no post-navigation screenshots/XML artifacts, only allowlisted file metadata. Original command-line restored.
- Existing `update_e2e.run_case` optional good-offer callback leaves default visibility-only behavior intact. New focused `update_download` mode never publishes; new full source regressions also run it. Release gate now requires **UPDATE_DOWNLOAD_E2E PASS** for 0020, so an item/badge alone cannot promote the changed source APK.
- Host tests cover URL/ABI/hash allowlist, exact native item bounds, missing/partial/wrong-hash result refusal, private/unrelated download exclusion and no install/post-tap capture. Full local **299 passed, 8 skipped in 126.05s**; this remains static/host evidence, actual tap/download NOT RUN until new source APKs exist.
