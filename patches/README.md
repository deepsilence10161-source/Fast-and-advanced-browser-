# Chromium source patches (इस परियोजना के बदलाव)

Staged source build (`scripts/ci/chromium_stage.sh`) हर stage में **pristine** Chromium src restore करता है और फिर यहाँ के patches लगाता है (`scripts/ci/patches.py`)।

| फ़ाइल | काम |
|---|---|
| `series` | patches के नाम, क्रम से (`#` टिप्पणी)। खाली = baseline |
| `*.patch` | unified diff, `src/` के सापेक्ष (`git diff` जैसा `a/` `b/` prefix, `patch -p1`) |
| `args.gn` (वैकल्पिक) | base args.gn में जोड़ी जाने वाली पंक्तियाँ, जैसे `chrome_public_manifest_package = "..."` |
| `overlay/<src-path>` (वैकल्पिक) | binary assets (icon PNG) — src की **पहले से मौजूद** उसी फ़ाइल की जगह कॉपी। न हो तो त्रुटि। hash में शामिल; patches से पहले |
| `signing_cert_sha256.txt` (वैकल्पिक) | release cert का SHA-256 (public)। हो तो release signing अनिवार्य (`scripts/ci/finalize_apk.sh`) |

## सही incremental build कैसे
- series + patches + args.gn का hash पिछले stage के `progress.json` (`patches` key, out state के साथ परमाणु) से मिलाया जाता है।
- **वही hash** → patched फ़ाइलों की mtime पहली बार वाले स्थिर epoch पर → कोई अनावश्यक rebuild नहीं।
- **hash बदला** → epoch = अभी; नई **और हटाई गई** patches की फ़ाइलें touch → केवल प्रभावित हिस्से दोबारा बनते हैं, हटाए गए patch का पुराना output नहीं बचता।
- प्रमाण: `tests/test_scripts.py::TestPatches` — ninja के साथ असली multi-stage अनुकरण, साथ में negative control (सीधा `patch` यही stale output छोड़ता है)।
- APK gate: `aapt2 badging` में package = `chrome_public_manifest_package` (न हो तो `org.chromium.chrome`)। `DONE` में build key (patch hash + args) — patches बदलें तो वही state incremental आगे बढ़ती है।

## Variant (baseline अछूता रखना)
`chromium-source-build` को `variant=b1 seed=a1` से चलाएँ: src और शुरुआती out baseline (`a1`) से, नई state `crstate-<tag>-<cpu>-b1` में। UI capture: `source_variant=b1`।

**नियम:** baseline APK (a1) सत्यापित होने से पहले कोई patched build नहीं।

## Swiftra branding (variant b1)
| क्या | कहाँ |
|---|---|
| App नाम "Swiftra" (launcher label + 3 widget titles) | `0001-swiftra-app-name.patch` → `res_chromium_base/values/channel_constants.xml` |
| Package `com.swiftra.app`, `debuggable_apks = false` | `args.gn` |
| Launcher icon (legacy + adaptive fg/bg + themed monochrome) | `overlay/chrome/android/java/res_chromium_base/` — `scripts/make_brand_icons.py` से बना (मौलिक geometric artwork, कोई font/तीसरे पक्ष की image नहीं) |
| Release signing | `signing_cert_sha256.txt` + repo secrets `SWIFTRA_KS_B64`/`SWIFTRA_KS_PASS` |

### Release signing — सुरक्षा ढाँचा
- Build step (Chromium के हज़ारों scripts/hooks) को secrets **नहीं** मिलते। वह build पूरा करके unsigned `presign-*.apk` सुरक्षित रखता है और `sign=true` देता है।
- अलग workflow step "Release signing" (केवल उसी के env में secrets) `finalize_apk.sh` चलाता है: keystore 700-dir में decode → `apksigner sign` (password `file:` से, कभी argv/log में नहीं; `--alignment-preserved true` ताकि 16 KB lib alignment बनी रहे) → keystore तुरंत मिटाया → cert SHA-256 का मिलान **upload से पहले** (गलत key = FAIL, APK upload नहीं) → badging gates (package, non-debuggable) → DONE।
- Keystore का password args.gn / BUILD_INFO / state tar / logs में नहीं जाता (gn के `android_keystore_*` args इसी कारण उपयोग नहीं किए)।
- Keystore की मूल प्रति: maintainer के पास (offline backup ज़रूरी — key खोने पर उसी package पर update असंभव)।

## 0002-swiftra-strings.py (b2 — in-app strings)
Deterministic transform (diff से संभव नहीं क्योंकि English text बदलते ही grit fingerprint ID बदलते हैं)।
4 grd (chromium_strings, components_chromium_strings, android_chrome_strings, browser_ui_strings) में
Google Chrome / Chromium / Chrome -> Swiftra (केवल `<ph>` के बाहर का text; desc नहीं)। सभी xtb के translation ID नए
fingerprint पर remap; translations में भी नाम बदला (विभक्ति/उपसर्ग सहित)। सुरक्षित (नहीं बदलते): The Chromium Authors /
open source project, ChromeOS/ChromiumOS, Chrome Web Store, Chromebook/cast/box, Chrome Remote Desktop/Enterprise, और
Google के कानूनी दस्तावेज़ों के नाम (ऐसे messages के translations भी नहीं छूते)।
+ `ui/android/java/strings/android_ui_strings.grd` (menu button "Customize and control Google Chrome") और scoped
`components/components_strings.grd` -> केवल `new_or_sad_tab_strings.grdp` (Incognito "Chromium won't save", "Restart Chromium");
scoped grd में translations केवल बदले messages के। Chrome/Chromium variants एक ही नए ID में merge (xtb में duplicate नहीं)।
लिप्यंतरित नाम भी: hi/ne "क्रोमियम"/"क्रोम", ur "کروم" -> Swiftra (Chromebook/Web Store/OS रूप सुरक्षित)।
Self-check: हर xtb में (नए-ID अर्थ में) translation coverage पहले = बाद, वरना build विफल। Tests: tests/test_strings_rebrand.py (असली grit)।
सीमा: कुछ विभक्ति-प्रधान भाषाओं (hr, hu…) में "Swiftrau"/"Swiftraot" जैसे रूप — native review आवश्यक।

## overlay: Swiftra product logo (b2)
`components/browser_ui/styles/android/java/res_chromium/` — `drawable-*/fre_product_logo.png` (FRE, payments, custom tabs,
HaTS, touch-to-fill, omnibox default action), `drawable-*/product_logo_name.png` (logo + "swiftra" wordmark, DejaVu Sans),
`raw/signin_spin.json` (sign-in Lottie: Chromium 155 मूल जैसा frame/timing — पहले chevrons फिर गोला सिकुड़ता)।
Generator: `python3 tools/brand/swiftra_logo.py patches/overlay` (deterministic)। Tests: `tests/test_brand_logo.py`।
Lottie python-lottie 0.7.2 + cairosvg से render करके जाँचा (frame 0 = static logo, 2% pixels केवल किनारों पर भिन्न)।

## overlay: NTP popular-sites fallback (b2)
`components/ntp_tiles/resources/default_popular_sites.json` — non-Google-branded Android build का bundled fallback
(Chromium-dev सूची: chromium.org, codereview, freenode, chrome://flags) पहली NTP पर दिखता था (b1 capture 02_ntp.xml);
अब gstatic `chrome/ntp/suggested_sites_DEFAULT_7.json` (वही सूची जो fetch के बाद आती है; देश-विशिष्ट सूची बाद में आती है)।

## 0003-fre-no-false-uma-claim.patch (b2 — privacy text सत्यता)
FRE footer की "To help improve the app, Swiftra sends usage and crash data to Google" पंक्ति इस build के लिए झूठी थी:
Chromium 155 `components/metrics/metrics_service_accessor.cc` — non-Google-branded build में metrics reporting पूरी तरह बंद।
`FullscreenSigninMediator` में `!BuildConfig.IS_CHROME_BRANDED` होने पर footer केवल ToS पंक्ति (upstream का policy-disabled रास्ता)।
बाकी (legal gate G1): ToS link अभी Google Terms of Service पर जाता है — Swiftra की अपनी ToS/Privacy चाहिए।

## 0002 FACT_FIXES: About → Legal information copyright (c1 — सत्यता)
`IDS_LEGAL_INFORMATION_SUMMARY` (android_chrome_strings.grd) upstream में "Copyright %1$d Google LLC. All rights reserved." —
Swiftra Google LLC का उत्पाद नहीं, अतः असत्य। अब "Copyright %1$d The Chromium Authors. All rights reserved." — वही wording जो
Chromium (non-Google) desktop About दिखाता है (`chromium_strings.grd` `IDS_ABOUT_VERSION_COPYRIGHT` की `not _google_chrome` शाखा)
और जो Chromium BSD license notice है। 81/81 भाषाओं के अनुवाद उसी desktop message के पेशेवर अनुवाद से (regex-अनुवाद नहीं);
xtb का मेल file-suffix से (lang "iw"/"he")। upstream fr-CA स्रोत में "Les auteurs de Chrome" भूल → `tr_fix` से "Chromium"।
किसी भाषा का स्रोत-अनुवाद न मिले या message ठीक 1 बार न मिले तो build रुकता है। अंतिम legal wording: G1 review।

## 0004-google-services-no-false-metrics-toggle.patch (c1 — सत्यता)
Settings → Google services का switch "Help improve Swiftra's features and performance — Automatically sends usage statistics and
crash reports to Google" ON दिखता था, पर इस build में: (1) UMA पूरी तरह बंद (`metrics_service_accessor.cc`, non-official);
(2) crash dumps का upload URL `null` (`MinidumpUploader.sCrashUrlString` = केवल `IS_CHROME_BRANDED` में clients2.google.com) —
upload "Crash upload URL is not configured" पर बिना network के रुकता है। यानी दावा असत्य और switch निष्क्रिय।
`!BuildConfig.IS_CHROME_BRANDED` में switch छिपा (upstream का `shouldUseMetricsChoiceRestructure` वाला रास्ता) + settings search से हटाया।
नहीं छुआ: "Make searches and browsing better" (url-keyed consent — omnibox zero-suggest इसी consent पर पेज URL default search
engine को भेज सकता है, अतः दावा असत्य सिद्ध नहीं; default OFF) और "Improve search suggestions" (असली)।

## 0005-safety-hub-no-false-up-to-date.patch (c1 — सत्यता)
Settings → Safety check (Safety Hub) "Swiftra is up to date" दिखाता था बिना कोई जाँच किए: Omaha `RequestGenerator` केवल
Google internal build में (`OmahaService.createRequestGenerator()` → `ServiceLoaderUtil.maybeCreate`), Chromium में `null` →
update check कभी नहीं चलता → `UpdateStatusProvider` `UpdateState.NONE` → "up to date"। अब `!IS_CHROME_BRANDED` में upstream की
मौजूदा "unavailable" शाखा: शीर्षक "Can’t check Swiftra version", summary "Version <installed>" ("Try again later" भ्रामक होता)।
उसी card का "Go to Google Play" button भी छिपा: upstream `SafetyHubModuleDelegateImpl.openGooglePlayStore()` non-branded में no-op
(dead button) — ae8c946 के arm64 screenshot में दिखा, अगले commit में ठीक। पुराना SafetyCheck रास्ता पहले से ERROR ("can’t check for updates") दिखाता है — अपरिवर्तित।

## 0006-swiftra-shield.patch (c2)
`python3 shield/make_patch.py` से बनता है (हाथ से edit नहीं)। विवरण: `docs/swiftra-shield.md`।

## 0007-swiftra-shield-honest-interstitial.patch (c2b — सत्यता + सुरक्षा)
- `safe_browsing_loud_error_ui.cc`: non-branded में explanation paragraph ("Google Safe Browsing recently found …" + transparencyreport/report-error links) खाली। finalParagraph (risk + proceed link) अपरिवर्तित।
- `url_realtime_mechanism.cc`: non-branded में ताज़ा SAFE real-time verdict पर भी hash DB (Swiftra Shield) जाँचा जाता है। पहले Enhanced protection Shield-listed URL को non-async रास्ते में छोड़ देता।
- दोनों BUILD.gn में `//build:branding_buildflags` dep।
- साथ में (c2b): 0002 scope में `generated_resources.grd`; overlay `chrome/android/java/res/drawable/blue_google_shield.xml` (Google "G" की जगह ✓)। विवरण: `docs/swiftra-shield.md` § Enhanced protection।

## 0008-swiftra-standard-local-and-esb-honest.patch + args.gn + 0002 (c2c — सत्यता + privacy)
शोध (Chromium 155.0.8059.80 source):
- `args.gn` में `is_official_build=false` + unbranded → `fieldtrial_testing_enabled=true` (components/variations/service/BUILD.gn) और
  `ShouldUseFieldTrialTestingConfig()` default true → `testing/variations/fieldtrial_testing_config.json` के ~1128 प्रयोग हर
  Swiftra पर चालू थे। इनमें `MaliciousApkDownloadCheck` (Standard में भी APK download ping → androidchromeprotect.pa.googleapis.com,
  `X-Goog-Api-Key: dummytoken`), `SkipImageClassificationScoringForNonPageLoadTriggers`, `ClientSideDetectionCreditCardForm`,
  `ProactivePasswordProtection`। Chromium का अपना testing/variations/README.md: non-Chrome browsers testing config बंद करें।
  → `disable_fieldtrial_testing_config = true` (ungoogled-chromium/Thorium जैसा)।
- `chrome_password_protection_service.cc` `IsPingingEnabled()`: Android पर saved-password reuse / OTP-field ping Standard में
  भी `true` (Google को URL + page data)। non-branded में अब केवल `extended_reporting_enabled` (= Enhanced या "Help improve
  security" opt-in, दोनों Google को भेजना स्पष्ट बताते हैं)।
- CSD model: `prediction_model_fetcher_impl.cc` key= `google_apis::GetAPIKey()` — हमारे build में `dummytoken` → model नहीं
  (E2E: "Downloaded models:" खाली) → CLASSIFIER_NOT_READY → CSD ping नहीं।
- इसलिए Standard का दावा "If a page does something suspicious, URLs and bits of page content are sent to Google Safe Browsing"
  Swiftra के लिए असत्य → 0002 FACT_FIXES: Chrome का desktop Standard subtitle ("Protects you from sites, downloads, and
  extensions that are known to be dangerous", 81 पेशेवर अनुवाद generated_resources से)।
- Enhanced "Real-time, AI-powered protection …": Swiftra में कोई AI model नहीं चलता (model fetch key-रहित) → Chrome का desktop
  Enhanced subtitle "Real-time, proactive protection by sending more information to Google Safe Browsing" (81 अनुवाद)।
- Enhanced details page (`EnhancedProtectionSettingsFragment`): non-branded में छिपे — bullet_two "In-depth scans for suspicious
  downloads" (APK scan बंद/key-रहित), bullet_three "When you're signed in, protects you across Google services" (Google sign-in
  उपलब्ध नहीं), learn_more ("how <app> keeps your data private" → Google Chrome help)। data disclosures bullet_six/seven बने रहते।
- E2E (`shield_e2e.py`): chrome://version variations source ≠ field-trial-config; Safe Browsing page के दोनों summaries; Enhanced
  details page; browser-process NetLog trace (CDP Tracing) — Standard window में Safe Browsing endpoint 0, Enhanced window positive control।

## 0009-swiftra-quiet-start.patch (c2d — बेकार और केवल-logging requests हटाना)
प्रमाण (startup NetLog, `scripts/ci/startup_netlog.py`, runs 39084556269 x64 / 39084557684 arm64; cold start → NTP, कोई user
action नहीं): `discover-pa.googleapis.com/v1:queryInteractiveFeed` ×2, `www.google.com/async/ddllog` ×2,
`accounts.google.com/ListAccounts` ×1–2, `async/ddljson`, `async/folae` ×2, `complete/search`, `update.googleapis.com`; Safe Browsing 0।
- `components/feed/core/shared_prefs/pref_names.cc`: `ntp_snippets.enable` का default = `google_apis::HasAPIKeyConfigured()`।
  Discover feed API key के बिना कभी नहीं चल सकता; NTP पर हमेशा "Can't refresh Discover / Check back later" दिखता था (झूठा वादा)।
  policy/pref से अब भी चालू हो सकता है। BUILD.gn में `//google_apis` dep।
- `chrome/browser/ui/android/logo/logo_bridge.cc` `RecordImpression()`: doodle दिखता रहता है; केवल impression ping
  (`doodle_impression_android`, logging) नहीं भेजा जाता।
- ListAccounts (Google cookies के साथ POST, NetLog traffic annotation hash 35565745 = `gaia_auth_list_accounts`): तीन जगह
  `GetAccountsInCookieJar()` (cache stale हो तो fetch) की जगह `GetCachedAccountsInCookieJar()` (fetch नहीं, @155 public API):
  `sync_session_durations_metrics_recorder.cc` constructor, `account_investigator.cc` `TryPeriodicReport` (दोनों केवल metrics) और
  `chrome_autocomplete_provider_client.cc` `IsAuthenticated()` (केवल Drive document suggestions की पात्रता)। यह code-स्तर पर
  सत्यापित है; मापन में इनका अलग असर सिद्ध नहीं हुआ।
  बचा हुआ 1 ListAccounts (दोनों arch, cold start पर `async/folae` से 1–16 ms पहले) AI Mode का है: `AimEligibilityService`
  stale cookie jar पर eligibility request छोड़ देता है (`drop_request_if_cookies_stale=true`, `kAimServerEligibilityEnabled`
  default on) → AI Mode button इसी पर निर्भर; जानबूझकर रखा। Gate: folae से 2 s के भीतर न हो तो FAIL।
- `autofill_crowdsourcing_manager.cc` `IsEnabled()`: API key (या `--autofill-api-key`/`--autofill-server-url`) के बिना
  content-autofill.googleapis.com को form signatures नहीं (server हर बार reject करता, फिर भी 5 बार तक भेजा जाता)।
जानबूझकर रखा: doodle image (`ddljson`), AI Mode eligibility (`folae` + उसका 1 ListAccounts), omnibox suggestions/preconnect
("Autocomplete searches and URLs" setting से नियंत्रित), component updater (CRLSet आदि सुरक्षा data)।
संदर्भ (code नहीं लिया): Bare browser (BSD-3) docs/patches.md 0006/0093/0193/0194 में यही call sites दर्ज हैं।
E2E gate: `quiet_violations()` — startup NetLog या Standard NetLog window (अब address form page सहित) में इनमें से कोई request = FAIL।

## 0000-upstream-155.0.8059.84.patch (2026-10-18 — engine security बराबर Chrome stable)
Google ने Android पर 155.0.8059.84 जारी किया (security fixes)। tag बदलने का मतलब नया STATE और पूरा fresh build (घंटों),
इसलिए .80 → .84 का source delta (gitiles `+log/refs/tags/155.0.8059.80..refs/tags/155.0.8059.84`, 63 commits) patch के रूप में:
- Chromium 10 fixes: cc/paint (paint_op reader/writer, paint_shader, transfer cache), gpu raster_decoder/service_transfer_cache,
  chrome_content_renderer_client, soda_util, navigation_request, text_input_manager, worker_host (dedicated/shared/fetcher),
  content/common/features, blink element.cc / svg_resource.cc।
- V8 3 [M155] fixes (d89479ac..712e1808): compiler (JSCreateGeneratorObject lowering), maglev graph builder, code serializer।
- जानबूझकर **नहीं** लिया: `chrome/VERSION` और `v8/include/v8-version.h` (लगभग हर file इन्हें include करती है → लगभग पूरा
  rebuild), xtb अनुवाद (security नहीं; 0002 से टकराव), devtools UI commit। इसलिए **version label 155.0.8059.80 / V8 15.5.35.23
  ही दिखता है, जबकि code में .84 के सभी security fixes हैं।** यह बात README/BUILD_INFO/report में स्पष्ट लिखी जाती है।
- सत्यापन: साफ़ .80 files पर `patch -p1` (fuzz/offset 0) → सभी 33 files .84 tag की files से byte-identical।
- series में सबसे पहले (pristine upstream code पर); हमारे 0001–0010 में से कोई इन files को नहीं छूता।

## 0010-swiftra-advanced-defaults.patch (2026-10-18 — Chrome से कड़े privacy/security defaults)
- `chrome/common/chrome_features.cc`: `kHttpsFirstBalancedModeAutoEnable` = ENABLED_BY_DEFAULT। Chrome में यह server-side
  field trial से चालू होता है (`testing/variations/fieldtrial_testing_config.json` @155: `HttpsFirstBalancedModeAutoEnableAndroid`
  Enabled); Swiftra में `disable_fieldtrial_testing_config = true` और कोई Finch नहीं → अब तक बंद था। असर: public site HTTPS
  पर न खुले तो चुपचाप HTTP पर जाने के बजाय "connection is not secure" चेतावनी (private IP/single-label host छूट)। Settings से बंद हो सकता है।
- `components/content_settings/core/browser/cookie_settings.cc`: `prefs::kCookieControlsMode` default
  kIncognitoOnly → **kBlockThirdParty** (Chrome में third-party cookies सामान्य tab में allowed)। pref को startup पर कोई नहीं
  लिखता (code search: केवल enterprise policy handler और desktop settings UI) → user/policy अब भी बदल सकते हैं।
- E2E (`scripts/ci/advanced_e2e.py`, `run_capture.sh` से): `--host-resolver-rules` से `httponly.example.com`,
  `top.example.com`, `cookie3p.example.org` runner के local servers पर (HTTP 8770; HTTPS 8771 self-signed +
  `--ignore-certificate-errors` केवल इस run में)। HTTPS: चेतावनी/HTTP page कभी fetch न हो = PASS; चुपचाप HTTP = FAIL।
  Cookies: cross-site iframe का `s3p=1; SameSite=None; Secure` cookie दो loads में न दिखे = PASS, first-party `fp=1` control ज़रूरी।
  Desktop Chromium 156 पर तरीका सत्यापित: AutoEnable off → HTTP silently (server hits 2), on → blocked (hits 0);
  3PC default → allowed, CDP restriction → blocked।
- Fingerprinting protection: @155 में कोई तैयार flag नहीं (press में बताया canvas-readback flag इस tree में नहीं) → अगले चरण में अपना implementation।

## 0011-swiftra-fingerprint-shield.patch (2026-10-18 — Fingerprint Shield, Chrome में नहीं)
नई file `third_party/blink/renderer/core/frame/swiftra_fingerprint_shield.{h,cc}` (core/frame/build.gni में जोड़ी) +
5 call sites। Feature `SwiftraFingerprintShield` (ENABLED_BY_DEFAULT; `--disable-features=SwiftraFingerprintShield` से बंद)।
- Key = hash(renderer-session random salt, **top-level** site का scheme + registrable domain)। Top-level इसलिए कि एक ही
  tracker iframe दो अलग sites पर अलग fingerprint पाए। Worker: `top_level_frame_security_origin()`।
- Pixels (8-bit RGBA/BGRA, केवल alpha=255): लगभग 1/16 pixels के एक colour channel का सबसे निचला bit, pixel की position और
  उसके बाकी bits के hash से तय → अदृश्य (अधिकतम ±1), एक site पर स्थिर, sub-rect पढ़ने पर भी समान, और idempotent
  (getImageData → putImageData → getImageData से हटाया नहीं जा सकता; मूल LSB वापस नहीं मिलता)।
- जगहें: `BaseRenderingContext2D::getImageDataInternal` (readPixels के बाद), `HTMLCanvasElement::ToDataURLInternal` और
  `toBlob`, `OffscreenCanvas::convertToBlob` (snapshot की noised RGBA copy), `WebGLRenderingContextBase::ReadPixelsHelper`
  (RGBA/UNSIGNED_BYTE, PACK_ALIGNMENT rows; helper हर write `buffer_size` के भीतर जाँचता है),
  `OfflineAudioContext::FireCompletionEvent` (per-site gain < 2^-16 + per-sample jitter 2^-18, लगभग -100 dB)।
- सीमाएँ (अगला चरण): float16 ImageData/canvas, realtime AnalyserNode, WebGL PIXEL_PACK_BUFFER reads, WebGL renderer string,
  fonts/hardwareConcurrency।
- Logic test (sandbox, g++): `tools/fingerprint/noise_logic_test.cc` — changed 215/6000 px, max diff 1, semi-transparent 0,
  अलग key → अलग, idempotent 0, sub-rect 0, capacity guard; audio max relative 7.8e-6।
- Licence: अपना code (BSD-style header); Brave "farbling" का केवल विचार सार्वजनिक है, code नहीं लिया।

## 0012-swiftra-adblock.patch + 0013-swiftra-adblock-ruleset.py (2026-10-18 — Ad & Tracker Blocker)
- Chromium का अपना subresource_filter, सभी sites पर: preset `swiftra_adblock_on_all_sites` (ALL_SITES, priority 900),
  feature `kSwiftraAdBlock` (ENABLED_BY_DEFAULT)।
- Ruleset APK में grit resource `IDR_SWIFTRA_ADBLOCK_RULESET` (gzip) के रूप में; `BrowserProcessImpl` इसे startup के बाद
  background में index करके publish करता है। Version `swiftra.<sha256[:16]>`, जिसे 0013 तय करता है।
- Google का "Subresource Filter Rules" component register नहीं होता, ताकि वह Swiftra ruleset को बदल न सके और Google को
  request भी न जाए।
- हर page पर दिखने वाला Android "Ads blocked" message बंद है; Page Info में ads की स्थिति और हर site का switch बने रहते हैं।
- 0013 (transform): `adblock/swiftra-ruleset.pb.gz` को `src/chrome/browser/resources/swiftra/adblock_ruleset.pb` में रखता है।
  Ruleset का SHA-256 script में pinned है, इसलिए mismatch होने पर build रुक जाता है।
- Lists: EasyList/EasyPrivacy (CC BY-SA 3.0) और AdAway hosts (CC BY 3.0); attribution `adblock/README.md` में है।
- `ruleset_service.cc`: feature चालू होने पर indexing USER_VISIBLE priority पर चलती है (पहले BEST_EFFORT थी), ताकि पहली launch
  पर ad blocking जल्दी शुरू हो। `FinishInitialization` अब भी UI BestEffort runner पर है, इसलिए यह देरी घटती है, खत्म नहीं होती।
- Licence notices: पहले के सभी non-official builds में `chrome://credits` पर Chromium का `sample_credits.html` दिखता था,
  असली third-party notices नहीं। अब `args.gn` में `generate_about_credits = true` है, और 0013
  `third_party/swiftra_adblock/{README.chromium,LICENSE}` जोड़ता है, जिससे list attribution भी app के अंदर दिखता है।
  इसकी device जाँच `CREDITS_E2E` करता है।
- Design और सत्यापन: `docs/adblock-design.md`। Desktop Chromium 156 matcher: PASS। Device E2E: NOT RUN।

## 0014-swiftra-search-choice.patch (2026-10-18 — हर user के लिए search engine चुनाव; series में अभी comment)
- सिर्फ़ Java में बदलाव (`LocaleManagerDelegate`)। Chromium का पहले से मौजूद First Run page "Choose your search engine" और dialog
  अब हर region में एक बार दिखते हैं। Engines देश के prepopulated engines होते हैं, जिन्हें upstream code shuffle करता है।
  पहले से कुछ भी चुना हुआ नहीं होता।
- Harness इसके लिए `handle_search_choice()` इस्तेमाल करता है (`SWIFTRA_SEARCH_PICK`, default Google)। Design: `docs/search-choice-design.md`।
- Build: NOT RUN (0012 build dispatch होने के बाद series में चालू होगा)।

## सत्यता scan (harness)
`scripts/ci/branding_scan.py` `FALSE_CLAIMS`/`EXPECTED` + `scan_claims()`; `scripts/ui_capture.py` हर capture xml पर चलाकर
meta `false_claims`/`expected_texts_found` + `truth_scan.json` लिखता है। 1f2788f artifacts पर (fix से पहले): x64 4, arm64 6 hits।

## 0016-swiftra-speedpack.py (2026-10-18 — Swiftra Speed Pack)
- Transform: `src/testing/variations/fieldtrial_testing_config.json` में सिर्फ़ 80 audited performance studies
  (Google/तीसरे पक्ष से कोई संपर्क नहीं, UI में कोई बदलाव नहीं; हर study का नाम और features pin) और
  `SwiftraParallelDownloading` (5 connections, 512 KiB slices) बचते हैं।
- `args.gn`: `disable_fieldtrial_testing_config = false`। Config binary में compile होता है और startup पर लागू होता है;
  कुछ भी download नहीं होता।
- Device पर जाँच: shield_e2e का variations step (`speedpack_check.py`, नतीजा `speedpack_only`) और network audit।
  Speed का माप: `scripts/ci/speed_e2e.py`। विवरण: `docs/speed-pack.md`।

## 0015-swiftra-download-shield.patch (2026-10-18 — Swiftra Download Shield)
- Gap @155: Android पर download URL check कभी नहीं चलता (`ShouldCheckDownloadUrl` को `kMaliciousApkDownloadCheck` चाहिए,
  जो default बंद है; `RemoteSafeBrowsingDatabaseManager::CheckDownloadUrl` हमेशा safe लौटाता था)। इसलिए `<a download>`,
  JS से शुरू downloads और उनकी redirect chain Shield सूची से नहीं जाँची जाती थीं।
- तीन files: `components/safe_browsing/android/remote_database_manager.cc` (chain का हर URL local Shield lookup से),
  `chrome/browser/safe_browsing/download_protection/download_protection_delegate_android.cc` (Safe Browsing चालू हो तो
  URL check; Google को ClientDownloadRequest ping नहीं), `chrome/browser/download/chrome_download_manager_delegate.cc`
  (Android पर content check केवल `kMaliciousApkDownloadCheck` के साथ, ताकि safe URL `NOT_DANGEROUS` रहे)।
- सूचीबद्ध URL → `DANGEROUS_URL` → "File might be harmful" dialog। कोई नया network request नहीं।
- Device E2E: `shield_e2e.py` की `DOWNLOAD_SHIELD_E2E` पंक्ति (canary / redirect / clean)। विवरण: `docs/swiftra-shield.md`।

## 0017-swiftra-turbo-download.patch (2026-10-18 — Swiftra Turbo Download)
- Gap @155: parallel download HTTP/2 और QUIC पर भी चालू है (`kUseParallelRequestsForHTTP2/QUIC` default ENABLED), पर सभी
  slices **एक ही connection** पर streams बनते हैं (`SpdySessionKey`/`QuicSessionKey` एक जैसे)। Per-connection सीमा
  (server limit, या lossy/high-RTT mobile link पर एक flow की congestion-control सीमा) पूरे download को रोक देती है।
- बदलाव (Android, feature `SwiftraSliceConnections`, default चालू): हर parallel slice को अलग `net::SocketTag`
  (`UNSET_UID` = अपना uid, कोई permission नहीं; केवल traffic-accounting label)। Tag HTTP/1.1 socket-pool group, HTTP/2
  session key और QUIC session key का हिस्सा है, इसलिए हर slice अपना connection लेता है। पहला request default tag पर।
- Files: `download_features.{h,cc}` (feature), `download_url_parameters.h` (`socket_tag`), `download_utils.cc`
  (`CreateResourceRequest` → `ResourceRequest::socket_tag`), `parallel_download_job.cc` (`CreateRequest` में tag)।
- सुरक्षा जाँच @155: `HttpStreamKey` में `CHECK(socket_tag_ == SocketTag())` है, पर tag वाला request HappyEyeballsV3
  stream pool में जाता ही नहीं (`http_stream_factory_job_controller.cc`: `request_info_.socket_tag == SocketTag()` शर्त),
  और HEv3 @155 default बंद है। Server पर भार Chromium के HTTP/1.1 व्यवहार जितना (उतने ही connections)।
- Device E2E: `speed_e2e.py` का HTTP/2-only server (`scripts/ci/h2_dl_server.py`, 1 MiB/s प्रति connection):
  `h2_download_s` और `h2_conns` (chromium_defaults में feature बंद)। Desktop पर `SocketTag` no-op है, इसलिए प्रमाण केवल device।

## 0018-swiftra-no-webview-pgo-toolchain.patch (2026-10-18 — arm64 PGO build fix)
- @155 पर arm64 + `chrome_pgo_phase = 2` होने पर `android_webview/variables.gni` standalone WebView के लिए अलग toolchain
  (`android_clang_arm64_webview`) जोड़ता है। Non-official build में secondary ABI नहीं होता, इसलिए उस toolchain में
  `components/policy` → `build/timestamp.gni` का default-toolchain assert `gn gen` रोक देता है (run 39146588456)।
  केवल arg `chrome_pgo_phase_default_toolchain = 0` से `system_webview_apk_tmpl.gni` में `webview_toolchain` undefined
  रह जाता है (run 39148004780)।
- बदलाव: `use_webview_pgo_profile` और `use_webview_pgo_profile_default_toolchain` = false। WebView default toolchain में
  रहता है, जैसा PGO के बिना। Swiftra WebView ship नहीं करता; x64 और non-PGO builds में दोनों पहले से false थे (no-op)।

## 0019-swiftra-shield-feeds-credits.py (2026-10-19, Shield feed licences)
- कमी: Shield list (shield-db release, जिसे app download करता है) Phishing.Database (MIT) और TweetFeed (CC0) से बनती है।
  MIT notice न app में था, न release में।
- Transform: `third_party/swiftra_shield_feeds/{README.chromium,LICENSE}` लिखता है, जिससे chrome://credits में entry
  बनती है (0013 वाला तरीका)। वही text `scripts/shield/build_shield_db.py` `NOTICE.txt` के रूप में release में डालता है।
- Gate: `tests/test_licences.py`। Status: WRITTEN; build और CREDITS E2E बाकी। Tranco केवल build-time guard है, बाँटा नहीं जाता।

## 0020 — Swiftra update channel (`0020-swiftra-update-channel.patch`)

Chromium's own update UI (menu badge + "Update Swiftra" item, `UpdateMenuItemHelper`) is driven by
`UpdateStatusProvider.getRealStatus()`, which upstream asks Omaha/Play Store (internal in public builds; never fires).
0020 replaces only that source: `SwiftraUpdate` fetches `swiftra-update.json` + `.sig` from the rolling public
release (`releases/latest/download/`), at most once per 24 h (1 h after a failure), plain HTTPS GET without cookies.
It accepts the manifest only if the ECDSA P-256 signature over `"swiftra-update-v1\n" + bytes` verifies with the
embedded public key (Shield list key; domain prefix keeps shield.swz signatures from passing as manifests), the URL
is inside this project's GitHub releases, and the entry for the device ABI was published after this APK was
installed. Tapping the item opens the fixed download link; Android's installer only accepts an APK with the same
Swiftra signing certificate. The manifest is written and signed by `.github/workflows/publish-latest.yml`
(`scripts/release/update_manifest.py`) only for APKs that passed the E2E + audit gates.
Tests: `tests/test_update_channel.py`; Java logic compiled with javac 11 against stubs + real org.json and checked
with a manifest signed by the real key (10/10, 2026-10-19). Safety check (0005, updated): "up to date" only after a signed manifest was verified in the last 48 h (`swiftraCheckedRecently()`), "update available" with an Update button that opens the same signed-channel link; otherwise the existing "can't check version" state.

Note (2026-10-19): the upstream study `HttpsFirstModeV2ForTypicallySecureUsers` (fieldtrial_testing_config @155:
`Enabled` -> feature of the same name) auto-enables HTTPS-First only for users who rarely visit HTTP sites. 0010 already
turns HTTPS-First balanced on for every user (ADVANCED_E2E PASS hfm=warning_dialog, emulator x64 + arm64 Redroid), so the study is a subset of
Swiftra's default; it stays out of the Speed Pack (tests/test_speedpack.py `banned`).
