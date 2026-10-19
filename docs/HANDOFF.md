# Swiftra: पूरी स्थिति और अगले session के लिए handoff (2026-10-19, 13:30 UTC)

> यह फ़ाइल सार्वजनिक है, इसमें कोई secret नहीं है। Secrets केवल user के दिए handoff prompt में हैं और `~/.secrets/` में रहते हैं।
> Repo: https://github.com/deepsilence10161-source/Fast-and-advanced-browser-  (branch `main`)
> मूल निर्देश: `docs/MASTER_PROMPT.md`; नियम: `PROJECT_RULES.md`; दायरा: `native-app/SCOPE_AND_ADVANCED_CAPABILITIES.md`; विफलताओं का इतिहास: `TESTING.md`

## 1. परियोजना एक नज़र में

- **Swiftra** = Android Chrome-clone browser। Package `com.swiftra.app`। Chromium tag **155.0.8059.80** + patch `0000` (= .84 security code, Critical CVE-2026-110922 सहित)। Variant **b1**, seed **a1**।
- Build: GitHub Actions के मुफ़्त standard runners पर chained stages (`chromium-source-build.yml` → `chromium-stage.yml`, हर stage ~6 घंटे की सीमा; state draft releases `crstate-155.0.8059.80-{x64,arm64}-b1` में)।
- Signer certificate SHA-256: `029de0fab8f35ee0990ced814d38ab47d6a1be9bc49ffea9bbf4dc190010fe06` (`patches/signing_cert_sha256.txt`)। Keystore कभी दोबारा न बनाएँ।
- **Fixed download links (rolling release `swiftra`, latest):**
  - https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/releases/latest/download/Swiftra-arm64.apk
  - https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/releases/latest/download/Swiftra-x64.apk
  - SHA256SUMS.txt, `swiftra-update.json(.sig)`, `swiftra-update-e2e.json(.sig)` भी उसी release में।

## 2. अभी published (2026-10-19 13:25 UTC)

| ABI | SHA-256 | Build/commit | E2E run | पैच |
|---|---|---|---|---|
| arm64 | `046550e9555890d44f35ce3956d5a866c4bdfb3256c5028246bc89055b004da9` (367,006,403 bytes) | 39185097028 (aea2608, PGO + orderfile) | 39240241640 (Redroid arm64) PASS | 0019/0020/0021 **नहीं** |
| x64 | `b1ea03ea9e77da9573ef5ad96c2078135acfe678c7ad1abee6feb4fddcaa11ff` | 39223536200 (9d2446f) | 39249911374 PASS (UPDATE_E2E + KEYSTORE_E2E PASS) | 0005 v2 + 0020 + 0021 सहित |

arm64 link उसी URL से पूरा download करके जाँचा: SHA मिलान, package `com.swiftra.app`, minSdk 29, signer ऊपर वाला, केवल `arm64-v8a`।

## 3. चल रहे runs (देखने के लिए; poll-loop नहीं, बीच-बीच में एक बार)

- **arm64 build 39223539138** (9d2446f: 0005 v2 + 0020 + 0021), s0 10:49 UTC से। पूरा होने पर: `after-build.yml` (अब ABI fallback ठीक) → `arm64-device-e2e.yml` → उसका नया `publish` job → `publish-latest.yml` (e2e_run input, run पूरा होने तक इंतज़ार) → gate PASS पर arm64 APK बदलेगा।
- अगर 39223539138 के बाद कोई कड़ी न चले: `after-build.yml` को `workflow_dispatch` (`cpu=arm64`) से, या `publish-latest.yml` को `e2e_run=<id>`, `e2e_wf=arm64-device-e2e.yml` से हाथ से चलाएँ।
- arm64 पर देखना: `UPDATE_E2E PASS`, `KEYSTORE_E2E PASS` (Redroid में `keystore2=True` पहले से पुष्ट), बाकी सभी `_E2E PASS`, `DEVICE_CHECKS 9/0`।

## 4. Release chain (सब अपने-आप)

1. `chromium-source-build.yml` (dispatch inputs: `tag=155.0.8059.80`, `cpu=x64|arm64`, `variant=b1`, `seed=a1`)। Concurrency: नया pending run पुराने pending को cancel करता है। Dispatch के समय का commit pin होता है।
2. `after-build.yml` (workflow_run): ABI run-name से, वरना crstate में सबसे नया `BUILD_INFO.txt` (T0 के बाद)। `contents: write` ज़रूरी (draft releases केवल write token को दिखते हैं)। Dry-run: `workflow_dispatch` inputs `cpu=""`, `t0=<ISO>`, `dry_run=true`।
3. E2E: x64 → `ui-capture.yml` (targets `["chromium_source_x64"]`, `source_variant=b1`); arm64 → `arm64-device-e2e.yml` (`source_tag`, `source_variant`, `redroid_image`, `ab_baseline_release=apk-b1-0011-arm64`)। दोनों `scripts/ci/run_capture.sh` चलाते हैं और अंत में `publish` job से `publish-latest.yml` dispatch करते हैं (GITHUB_TOKEN से शुरू हुए runs `workflow_run` नहीं चलाते; यह 2026-10-19 को पकड़ा गया)।
4. `publish-latest.yml`: हर ABI के लिए (a) `scripts/release/e2e_gate.py`: tested APK SHA = publish होने वाला, सभी REQUIRED marker PASS, कोई FAIL line नहीं, DEVICE_CHECKS साफ़; BY_PATCH: build में 0020 हो तो `UPDATE_E2E`, 0021 हो तो `KEYSTORE_E2E` भी ज़रूरी। (b) apksigner cert = signing_cert_sha256। (c) `scripts/release/release_gate.py` (`release/required_patches.txt`: 0000, 0006, 0010–0013, 0015–0017, **0019, 0020, 0021**; package; apk_audit 7/7)। विफल ABI पुराना APK रखता है। Release notes केवल मौजूद APK दिखाते हैं। फिर signed update manifest (`scripts/release/update_manifest.py`, secret `SWIFTRA_SHIELD_KEY`) और E2E manifest (केवल न हो तो)।

## 5. Patches (`patches/series` क्रम में; ASCII only; overlay से नई files नहीं, nested classes; `is_official_build=true` कभी नहीं)

| Patch | क्या | Status |
|---|---|---|
| 0000 | .80→.84 upstream security delta | PASS static; दोनों ABI में |
| 0005 v2 | Safety check: "up to date" केवल पिछले 48 घंटे में verified manifest पर (`UpdateStatusProvider.swiftraCheckedRecently()`), Update बटन → signed channel link | static APPLY-OK; build में है; device पर अलग से जाँचा नहीं (NOT RUN) |
| 0006 | Swiftra Shield (local list, ECDSA-signed shield-db) | PASS emulator + Redroid |
| 0010 | HTTPS-First balanced + 3P cookies block | ADVANCED_E2E PASS (`hfm=warning_dialog tpc=third_party_blocked`) |
| 0011 | Fingerprint shield | PASS |
| 0012/0013 | Ad/tracker blocker (EasyList/EasyPrivacy CC BY-SA 3.0, AdAway CC BY 3.0) | ADBLOCK_E2E PASS |
| 0015 | Download Shield | PASS (`canary=blocked_dialog redirect=blocked_dialog clean=downloaded`) |
| 0016 | Speed Pack (80 field-trial features + parallel downloading) | SPEED_E2E measured |
| 0017 | Turbo download (SocketTag) | built |
| 0018 | webview PGO off (PGO build assert fix) | built |
| 0019 | Shield feed credits (Phishing.Database MIT, TweetFeed CC0) | CREDITS_E2E PASS (771 entries) |
| 0020 | Update channel: 24 घंटे में एक बार `releases/latest/download/swiftra-update.json(.sig)`, ECDSA P-256 over `"swiftra-update-v1\n"+json`, UPDATE_AVAILABLE → upstream "Update Swiftra" menu item + badge; test switch `--swiftra-update-manifest-url` (https या `http://127.0.0.1:`) | **UPDATE_E2E PASS x64 emulator** (39249911374); arm64 बाकी |
| 0021 | OSCrypt key Android Keystore से (tag `sw1`, AES-256-GCM, precedence 10 > v10 का 5; `PlayServicesVersionInfo.swiftraOsCryptKey()` JNI + `SwiftraKeystoreKeyProvider` in `browser_process_impl.cc`); cookies + card/IBAN data | **KEYSTORE_E2E PASS x64 emulator** (prefix=sw1, कोई plaintext नहीं, restart के बाद cookie भेजी); upstream v10 Redroid पर पुष्ट; arm64 बाकी |
| 0014 | Search choice (series में commented) | बाकी |

## 6. मापे गए नतीजे (same-APK A/B: chromium_defaults बनाम swiftra)

- x64 emulator (39249911374): load 2093→1144 ms (1.83x), LCP 960→926, data 887→609 KiB, requests 47→32, ads 15→0, HTTP/1.1 download 9.4→6.3 s (1.49x), HTTP/2 download 24.1→5.1 s (4.73x), JS bench 355→370 (0.96x, noise)।
- arm64 Redroid (39240241640): load 1413→680 ms (2.08x), LCP 548→550, HTTP/2 download 4.92x; AB_BENCH बनाम पुराना 0011 APK: load 860→674 ms (1.28x), JS bench 379→345 (1.10x), cold start 671→684 (बराबर)।
- REPEAT_E2E noisy (±15%), इसलिए अब `--cycles 4`। Startup: x64 am_start 966 ms (पिछला 819), पर उसी run में emulator का "install" baseline भी 21% धीमा था, इसलिए 0021 से गिरावट साबित नहीं; निगरानी जारी।
- "100x तेज़" का दावा सच नहीं; ईमानदार अनुपात ऊपर हैं।

## 7. Comparison doc

`tools/comparison/{rows,build}.py` → `docs/comparison-chrome-vs-swiftra.{md,html,xlsx}`। अभी 58 पंक्तियाँ: Chrome 21, Swiftra 11, बराबर 15, अनिर्णीत 9, लागू नहीं 2; weighted 83:61।

## 8. Code से पक्की जानकारियाँ (दोबारा research न करें)

- Android @155 पर password manager केवल Google internal backend + GMS के साथ; Swiftra में `PasswordStoreEmptyBackend` (कुछ save नहीं होता)। LoginDatabase Android पर compile नहीं होता। योजना: `docs/plans/password-vault.md` (0022: Android पर `PasswordStoreBuiltInBackend` + 0021 वाली Keystore key + native settings UI)।
- Upstream Read Aloud का synthesizer server-side है (`ExecuteModel(kReadAloudSynthesize)`)। योजना: `docs/plans/read-aloud.md` (DOM Distiller + Android `TextToSpeech`)। **Java `WebContents.evaluateJavaScript()` आम page पर CHECK-crash करता है** (`CanExecuteJavaScript`)।
- HttpsFirstModeV2ForTypicallySecureUsers 0010 का subset है, इसलिए नहीं जोड़ा।
- Speed levers जो ख़ारिज हो चुके हैं: `docs/speed-pack.md` और session नोट देखें (optimize_for_size पहले से speed; ThinLTO असंभव; ART baseline profile फ़ायदा नहीं; HTTP cache 400% पहले से; IncreaseHttp3Usage, PreconnectFromKeyedService, DsePreload2, ChromeEnableDnsPlatform, JavalessRenderer, LCPP धीमा; 5 से ज़्यादा download connections केवल synthetic फ़ायदा)।

## 9. अगले कदम (क्रम में)

1. arm64 build 39223539138 → E2E → publish पर नज़र (ऊपर §3)। arm64 पर UPDATE_E2E/KEYSTORE_E2E PASS हों तो comparison की पंक्तियों में "arm64 बाकी" हटाएँ।
2. 0005 v2 का device E2E (Safety check पेज: verified manifest के बाद "up to date", tampered पर "can't check")।
3. 0021 का startup असर: अगले 2-3 x64/arm64 runs में am_start और STARTUP_TRACE की तुलना, emulator baseline के अनुपात में।
4. 0022 local password vault (योजना के अनुसार), फिर PLAN 9 read aloud (on-device), PLAN 10 extensions, PLAN 11 असली फ़ोन, PLAN 12 NOT RUN पंक्तियाँ, 0014 search choice, sign-in/leak-check, AI Mode E2E।
5. Speed हमेशा सर्वोच्च प्राथमिकता: हर नए lever को same-APK A/B से मापें, केवल मापे गए फ़ायदे पर ही रखें।
6. GitHub token **2026-11-14** को expire होता है। उससे पहले user से नया token माँगना (user action)।

## 10. Gates (master prompt §15)

G1 BLOCKED (Google trademark की लिखित अनुमति, legal gate) · G2 NOT FINISHED · G3 NOT STARTED · G4 PARTIAL · G5 NOT RUN। "पूरा हुआ" तभी कहें जब §15 के सभी criteria पूरे हों।
