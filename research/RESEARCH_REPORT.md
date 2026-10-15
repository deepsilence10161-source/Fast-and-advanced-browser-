# शोध रिपोर्ट — Android Chrome क्लोन (चरण 1)

- **जाँच की तारीख:** 15 अक्टूबर 2026 (Asia/Calcutta; सिस्टम द्वारा पुष्ट)
- **Repository:** `deepsilence10161-source/Fast-and-advanced-browser-`
- **वर्गीकरण-कुंजी:** **[P]** प्राथमिक/आधिकारिक स्रोत · **[M]** आज इस परियोजना में मापा/देखा गया · **[U]** उपयोगकर्ता द्वारा दिया तथ्य · **[I]** अनुमान · **[?]** अज्ञात/अपरीक्षित

---

## 1. लक्ष्य-संस्करण (reference) तय करना

| तथ्य | मान | वर्ग | स्रोत |
|---|---|---|---|
| Chrome Android Stable (आज serving) | `155.0.8059.39 / .41 / .79 / .80` + `156.0.8078.39` का 0.25% early-stable rollout | [P][M] | Google VersionHistory API `https://versionhistory.googleapis.com/v1/chrome/platforms/android/channels/stable/versions/all/releases?filter=endtime=none` (15-10-2026 को query किया) |
| Stable 155 का Chromium source commit | `155.0.8059.80` → `43a195105613ac83c21d3f14de279f4a045c7da0`; `155.0.8059.79` → `a49e2e3d4addfd84e765b52afe230bedb81096db`; main-branch position `1697595` | [P][M] | Chromium Dash `https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Android` |
| Chrome 155 Android release नोट | 155.0.8059.39 (6 अक्टूबर 2026), 155.0.8059.79 सुरक्षा अद्यतन (13 अक्टूबर 2026) | [P] | `https://chromereleases.googleblog.com/2026/10/chrome-for-android-update_01835271525.html` |
| **इस परियोजना का UI reference लक्ष्य** | **Google Chrome Stable 155.0.8059.x, phone form-factor** | निर्णय | ऊपर के आधार पर |

**महत्त्वपूर्ण भेद:** Chromium snapshot ≠ Google Chrome Stable। Stable में Google का branding, Google services, Play Services पर निर्भरताएँ और server-side **field trials/variations** होते हैं, जिनसे UI बदल सकता है। Chromium snapshot में ये नहीं होते [I — Chromium का variations seed public build में नहीं आता; इसे अलग से सत्यापित करना है, देखें §8]।

## 2. Upstream source और artifact

| तथ्य | मान | वर्ग |
|---|---|---|
| Official public prebuilt bucket | `gs://chromium-browser-snapshots`, prefixes: `Android/`, `Android_Arm64/`, `AndroidDesktop_x64/`, `AndroidDesktop_arm64/` (`Android_x64/` मौजूद **नहीं**) | [P][M] |
| M155 branch point के सबसे पास का snapshot | `Android_Arm64/1697603` और `AndroidDesktop_x64/1697602` | [M] |
| Snapshot के अंदर APK | `ChromePublic.apk`, `ContentShell.apk`, `SystemWebView.apk` (+ desktop में `SystemWebViewShell.apk`) | [M] |
| Installed version | `org.chromium.chrome` **155.0.8059.0** (versionCode 805900004 arm64; 805900079 desktop x64) | [M] |
| सत्यापन | GCS metadata के MD5 और CRC32C से पूरी zip जाँची जाती है, फिर `zipfile.testzip()`; हर APK का SHA-256 `provenance.json` में दर्ज होता है | [M] `scripts/fetch_snapshot.py` |

## 3. Build क्षमता (पूरा Chromium source build)

| तथ्य | मान | वर्ग | स्रोत |
|---|---|---|---|
| Android build की न्यूनतम आवश्यकता | x86-64 Linux, ≥8 GB RAM (16 GB से अधिक की सलाह), ≥100 GB खाली disk | [P] | `https://chromium.googlesource.com/chromium/src/+/main/docs/android_build_instructions.md` |
| GitHub standard runner (public repo) | 4 CPU, 16 GB RAM, **14 GB SSD (गारंटी)**, public repo में मुफ़्त | [P] | `https://docs.github.com/en/actions/reference/runners/github-hosted-runners` |
| वास्तविक runner पर मापा गया | 4 CPU, 15 GiB RAM, `/` पर 86 GB खाली, `/dev/kvm` मौजूद | [M] run 38691453072 |
| Agent sandbox | 2 CPU, ~1.9 GiB RAM, 25 GB disk, KVM नहीं | [M] |
| ~~पुराना निष्कर्ष (सत्र 1)~~ | ~~standard runner पर BLOCKED~~ — यह [I] अनुमान था; सत्र 2 के शोध और माप से **गलत सिद्ध** (नीचे §3b) | सुधार |

## 3b. सुधार (सत्र 2, 15-10-2026): मुफ़्त standard runners पर staged source build

| तथ्य | मान | वर्ग | स्रोत |
|---|---|---|---|
| GitHub-hosted job की अधिकतम अवधि | 6 घंटे प्रति job; workflow run 35 दिन तक | [P] | https://docs.github.com/en/actions/reference/limits |
| Public repo में standard runners | "free and unlimited"; Linux 4 CPU / 16 GB | [P] | https://docs.github.com/en/actions/reference/runners/github-hosted-runners |
| यही समस्या दूसरे projects ने कैसे हल की | build को chained ~5–6 घंटे के stages में बाँटना; हर stage के बाद अधूरी build-state सहेजकर अगला stage वहीं से आगे। ungoogled-chromium-windows (8-stage chain), Project Mu (4-core पर 12–20 घंटे, 8 stages), Android ARMv7 Chromium fork (bounded slices) | [P: उनके public repos] | https://github.com/monkeylab/ungoogled-chromium-windows · https://github.com/krishivvyas/project-mu · https://github.com/zftsh2035-boop/Chrome-extensions |
| Chromium का build tool | Siso default है, पर `use_siso = false` से ninja चलता है (`build/toolchain/siso.gni` @155.0.8059.80) | [P] | https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/build/toolchain/siso.gni |
| Runner पर disk, cleanup के बाद | `/` पर 111 GB खाली (cleanup से पहले 86 GB) — official 100 GB न्यूनतम से ऊपर | [M] | run 38751068356 |
| Source (tag 155.0.8059.80, बिना history, android deps) | commit `43a195105613ac83c21d3f14de279f4a045c7da0` (Chromium Dash से मेल); zstd-3 pack ≈ 13.4 GB (8 भाग) | [M] | run 38745313869, state release |
| `chrome_public_apk` (x64, release, non-component, symbol_level 0) | gn: 63,340 targets; ninja: **57,552 edges** | [M] | run 38751068356 |
| Restore (src 13.4 GB download + extract) | 514 s; restore के बाद gn + `ninja -n` सफल | [M] | run 38751068356 |
| Resume की शुद्धता | PAX tar nanosecond mtime रखता है → restore के बाद बचा काम उतना ही; seconds-only/नई mtime पर पूरा rebuild (watchdog इसी को पकड़ता है) | [M] | `tests/test_scripts.py::TestStagedBuildResume` |
| कुल build समय | **अभी अज्ञात [?]**: stage 0 की compile दर से पता चलेगा | [?] | runs 38745313869 (x64), 38750988168 (arm64) |

**नया निष्कर्ष:** पूरा source build मुफ़्त standard runners पर **संभव** है (कई घंटे, कई stages)। Paid runner की आवश्यकता नहीं। Pipeline: `.github/workflows/chromium-source-build.yml` → `chromium-stage.yml` → `scripts/ci/chromium_stage.sh`। Build-state इसी repo के draft release `crstate-<tag>-<cpu>-a1` में रहती है। APK सत्यापित होने के बाद उसे हटाया जा सकता है।

**Stable की स्थिति (15-10-2026, Chrome Releases blog feed):** 14-10-2026 को Chrome 156 (156.0.8078.39) Android पर "small percentage of users" के लिए early-stable रूप में जारी हुआ। अधिकांश उपयोगकर्ता अभी 155.0.8059.79/.80 पर हैं। इसलिए build लक्ष्य 155.0.8059.80 ही रखा गया। 156 पूरी तरह rollout होने पर tag बदलना है। स्रोत: https://chromereleases.googleblog.com/feeds/posts/default/-/Chrome%20for%20Android

## 4. Android परीक्षण क्षमता (E2E)

| तथ्य | वर्ग | स्रोत |
|---|---|---|
| GitHub-hosted Linux runners Android emulator का hardware acceleration देते हैं | [P] | GitHub runners reference (ऊपर) |
| KVM के लिए udev rule आवश्यक; `reactivecircus/android-emulator-runner` v2.38.0 (commit `a421e43…` pin किया) | [P][M] | `https://github.com/ReactiveCircus/android-emulator-runner` |
| ARM runners (`ubuntu-24.04-arm`) पर `/dev/kvm` नहीं होता | [I] — कई द्वितीयक स्रोतों में; आधिकारिक पुष्टि नहीं मिली | — |
| Emulator images (google_apis, x86_64) में `abilist = x86_64,arm64-v8a`, native bridge `libndk_translation.so` | [M] API 34/35/36 |
| Emulator 30.0.0 नोट: Android 11+ x86_64 images ARM binaries चला सकती हैं | [P] | `https://developer.android.com/studio/releases/emulator` |
| **ARM64 `ChromePublic.apk` 155.0.8059.0 API 36 emulator पर translation से install, launch, first-run और page load सफल** | [M] | runs 38697226252, 38698517502, 38699920976 (21/21 screens, 0 ANR) |
| **वही ARM64 build translation में अस्थिर:** 5 ARM64 runs में से 2 में "Chromium isn't responding" ANR आया (run 38697226252 में FRE पर अटका; run 38701948978 में 37 ANR dialogs, 7 screens)। x86_64 build और Chrome 133 में 0 ANR | [M] | `evidence/ui-capture-run-38701948978/chromium_arm64_FAILED_ANR/` |
| ARM64 build के sandboxed renderer processes translation में `SIGSEGV` (`libndk_translation.so`, `berberis::RunGuestCall`) से बार-बार crash होते हैं (runs 38699920976, 38701948978, 38704128045)। Run 38704128045 में fixture page पर "Aw, Snap!"। x86_64/Chrome 133: 0 | [M] | `evidence/ui-capture-run-38704128045/chromium_arm64_renderer_SIGSEGV/logcat_tail.txt` |
| **निष्कर्ष:** ARM64 build का web-rendering/performance परीक्षण x86_64 emulator पर विश्वसनीय नहीं है; असली ARM64 फ़ोन अनिवार्य है | [M]+[I] | — |
| Emulator image पर Google Chrome: API34 → **113.0.5672.136**, API35 → **124.0.6367.219**, API36 → **133.0.6943.137** | [M] |
| **निष्कर्ष:** emulator पर Chrome Stable 155 का reference **उपलब्ध नहीं** है। Play Store से update के लिए Google account चाहिए, और third-party APK mirror का उपयोग नहीं किया जाएगा (provenance/ToS जोखिम)। इसलिए Stable 155 का UI reference उपयोगकर्ता के अपने फ़ोन के गैर-निजी screenshots से ही आ सकता है। | [M]+निर्णय |

## 5. Google login, OAuth, Sync, private APIs

| तथ्य | वर्ग | स्रोत |
|---|---|---|
| "A developer must not direct a Google OAuth 2.0 authorization request to an embedded user-agent under the developer's control … All browsing environments must allow the user to verify the current connection … including the requested URI and connection security information." (अंतिम संशोधन 5 अगस्त 2026) | [P] | `https://developers.google.com/identity/protocols/oauth2/policies#browsers` |
| WebView cookies/login मुख्य browser से साझा नहीं करता; Custom Tabs default browser का session साझा करता है और UI पर नियंत्रण सीमित है | [P] | `https://developer.android.com/develop/ui/views/layout/webapps/in-app-browsing-embedded-web` |
| Custom Tab embedder को cookies, passwords, पूरा DOM, script injection या network interception नहीं मिलता | [P] | Chromium Custom Tabs Security FAQ |
| Chromium में sign-in प्रतिबंधित है: OAuth token generation restricted है, केवल test-account group को छूट; अपनी keys से वितरण संभव है पर keys साझा नहीं की जा सकतीं, और कई APIs का quota नहीं होता | [P] | `https://www.chromium.org/developers/how-tos/api-keys/` |
| **निष्कर्ष:** (1) WebView-आधारित ऐप Google login/Arena का पूर्ण समाधान नहीं है। (2) पूरे Chromium browser में Google **website** login और Chrome **browser-level Sync** अलग चीज़ें हैं; Sync हमारे build में Google की अनुमति के बिना उपलब्ध नहीं होगा। (3) website login को वास्तविक उपयोगकर्ता-साक्षी परीक्षण से सत्यापित करना होगा। | [P]+[I] |

## 6. Branding / trademark / license

| तथ्य | वर्ग | स्रोत |
|---|---|---|
| Google trademarks या उनसे भ्रमित करने वाले नाम/logo लिखित अनुमति के बिना उपयोग न करें (Chrome Web Store branding guideline) | [P] | `https://developer.chrome.com/docs/webstore/branding` |
| Chromium source BSD-style और अन्य open-source licenses में है; "Google Chrome" नाम/logo और Google services के अधिकार अलग हैं | [P]/[I] | Chromium `LICENSE`, `about:credits` |
| Snapshot के resource strings में "Customize and control **Google Chrome**" और "Ask **Gemini**" दिखे | [M] | ui-capture `02_ntp.json` |
| **Engineering/legal gate:** UI layout, व्यवहार और interaction की हूबहू parity (मूल आवश्यकता) बनी रहेगी। लेकिन वितरित build में "Google Chrome" नाम/logo तभी रहेगा जब उपयोगकर्ता के पास अधिकार हो; अन्यथा अलग नाम/logo रखा जाएगा। यह दायरे में कटौती नहीं, बल्कि वितरण से पहले का एक स्पष्ट legal gate है। | निर्णय |

## 7. Arena / लंबी चैट समस्या

| तथ्य | वर्ग | स्रोत |
|---|---|---|
| उपयोगकर्ता Google खाते से Arena में login करता है; लंबी chat देर से खुलती है, नए उत्तर के लिए hard refresh करना पड़ता है | [U] | hand-off निर्देश |
| `content-visibility` off-screen rendering work कम करता है, पर server latency या टूटी stream ठीक नहीं करता | [P] | `https://web.dev/articles/content-visibility` |
| SSE में `Last-Event-ID` से reconnect/replay होता है, बशर्ते server इसका समर्थन करे | [P] | `https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events` |
| Arena का वास्तविक transport (SSE, WebSocket या polling), event IDs और reconnect व्यवहार | [?] — अनिरीक्षित; केवल उपयोगकर्ता की अनुमति और उसके अपने session में, privacy-safe तरीके से ही जाँचा जाएगा |

## 8. नए खुले प्रश्न (आज के परीक्षण से उठे)

1. Chromium 155 snapshot में **bottom toolbar** (Home, Ask Gemini, New tab, Tabs, Menu) और NTP पर "AI Mode" और "Incognito" chips हैं। Stable 155 में ये सभी उपयोगकर्ताओं को दिखते हैं या field trial से नियंत्रित हैं **[?]**। इसके लिए उपयोगकर्ता के फ़ोन का screenshot चाहिए।
2. Chromium FRE "Make Chrome your own → Stay signed out" दिखाता है, जबकि emulator का Chrome 113/124 "Welcome to Chrome → Use without an account" दिखाता है। Stable 155 का FRE **[?]** है।
3. emulator पर `https://example.org` के लिए omnibox में "Connection is not secure" दिखा **[M]**। कारण (emulator network/proxy/HTTP-only redirect) की जाँच बाकी है।

4. **[M] Chromium 155 snapshot में omnibox पर security/status icon नहीं है** (`location_bar_status_icon` accessibility tree में नहीं)। Page info केवल app menu → "Site controls" से खुला (runs 38699920976, 38701948978)। Chrome 133 में icon "Connection is secure" मौजूद है। Stable 155 में **[?]**।
5. **[M] Long-chat synthetic fixture (10 cases)** desktop Chrome 155 headless (3×10/10, run 38699618638), Android emulator पर Chrome 133 (10/10) और Chromium 155 x86_64 (10/10) में पास (run 38701948978)। यह केवल rendering-रणनीति (sequence-id dedupe/gap-resync, anchor-आधारित scroll restore, `content-visibility`) की पुष्टि है; **असली Arena का transport, latency या login इससे सिद्ध नहीं होता।**

## 8b. Performance (केवल emulator; वास्तविक फ़ोन का प्रतिनिधि नहीं)

`am start -W` TotalTime, 10 cold (force-stop) + 10 warm (HOME के बाद), run 38701948978 (ARM64: run 38699920976), API 36 x86_64 emulator, swiftshader GPU:

| Target | cold median / p95 (ms) | warm median / p95 (ms) | PSS (example.com के बाद) |
|---|---|---|---|
| Chrome 133 (emulator image) | 824 / 957 | 511.5 / 699 | 132,082 KB |
| Chromium 155 x86_64 | 721.5 / 819 | 626.5 / 693 | 156,473 KB |
| Chromium 155 ARM64 (translation; run 38699920976) | 1531.5 / 1685 | 1001 / 5523 (एक trial 5.5 s) | 499,439 KB |

10 trials में p95 व्यवहार में अधिकतम मान है। अलग Chrome versions और emulator GPU के कारण ये आँकड़े **किसी "तेज़" दावे का आधार नहीं** हैं। Same-device ARM64 benchmark आवश्यक है (G section)।

## 8c. CI / runner तथ्य

| तथ्य | वर्ग | स्रोत |
|---|---|---|
| Standard public runner: 4 CPU, 16 GB RAM, 14 GB SSD (दस्तावेज़); वास्तविक `/` पर 86 GB खाली | [P][M] | GitHub runners docs; run 38691453072 |
| `build_chromium_baseline.sh --preflight-only` standard runner पर exit 3 (disk < 100 GB) | [M] | `unit-tests.yml` runs (जैसे 38698511862) |
| emulator-runner `script:` की हर line अलग shell में चलती है, इसलिए logic bash फ़ाइल (`scripts/ci/run_capture.sh`) में रखा | [P][M] | action README; cancelled run 38695330921 |
| Chrome Android का DevTools socket `chrome_devtools_remote` adb forward से उपलब्ध (emulator, USB-debugging) | [M] | run 38701948978 `journey.log` |

## 9. सीमाएँ

- Search snippets का उपयोग केवल दिशा पाने के लिए किया गया; निर्णायक तथ्य ऊपर दिए आधिकारिक पृष्ठों से पढ़े गए।
- ARM64 translation पर मापे गए performance आँकड़े वास्तविक ARM64 फ़ोन के प्रतिनिधि **नहीं** हैं।
