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
- `components/sync/service/sync_session_durations_metrics_recorder.cc` (constructor) और
  `components/signin/core/browser/account_investigator.cc` (`TryPeriodicReport`): दोनों केवल metrics के लिए Google cookie jar
  पढ़ते थे, जो हर cold start पर ListAccounts fetch करता था; Swiftra metrics upload ही नहीं करता। list किसी और कारण से आए तो
  report उसी से बनती है (fetch नहीं)।
- `autofill_crowdsourcing_manager.cc` `IsEnabled()`: API key (या `--autofill-api-key`/`--autofill-server-url`) के बिना
  content-autofill.googleapis.com को form signatures नहीं (server हर बार reject करता, फिर भी 5 बार तक भेजा जाता)।
जानबूझकर रखा: doodle image (`ddljson`), AI Mode eligibility (`folae`, AI Mode button काम करता है), omnibox suggestions/preconnect
("Autocomplete searches and URLs" setting से नियंत्रित), component updater (CRLSet आदि सुरक्षा data)।
संदर्भ (code नहीं लिया): Bare browser (BSD-3) docs/patches.md 0006/0093/0193/0194 में यही call sites दर्ज हैं।
E2E gate: `quiet_violations()` — startup NetLog या Standard NetLog window (अब address form page सहित) में इनमें से कोई request = FAIL।

## सत्यता scan (harness)
`scripts/ci/branding_scan.py` `FALSE_CLAIMS`/`EXPECTED` + `scan_claims()`; `scripts/ui_capture.py` हर capture xml पर चलाकर
meta `false_claims`/`expected_texts_found` + `truth_scan.json` लिखता है। 1f2788f artifacts पर (fix से पहले): x64 4, arm64 6 hits।
