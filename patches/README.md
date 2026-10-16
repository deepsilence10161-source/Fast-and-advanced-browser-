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
