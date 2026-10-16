# Chromium source patches (इस परियोजना के बदलाव)

Staged source build (`scripts/ci/chromium_stage.sh`) हर stage में **pristine** Chromium src restore करता है और फिर यहाँ के patches लगाता है (`scripts/ci/patches.py`)।

| फ़ाइल | काम |
|---|---|
| `series` | patches के नाम, क्रम से (`#` टिप्पणी)। खाली = baseline |
| `*.patch` | unified diff, `src/` के सापेक्ष (`git diff` जैसा `a/` `b/` prefix, `patch -p1`) |
| `args.gn` (वैकल्पिक) | base args.gn में जोड़ी जाने वाली पंक्तियाँ, जैसे `chrome_public_manifest_package = "..."` |

## सही incremental build कैसे
- series + patches + args.gn का hash पिछले stage के `progress.json` (`patches` key, out state के साथ परमाणु) से मिलाया जाता है।
- **वही hash** → patched फ़ाइलों की mtime पहली बार वाले स्थिर epoch पर → कोई अनावश्यक rebuild नहीं।
- **hash बदला** → epoch = अभी; नई **और हटाई गई** patches की फ़ाइलें touch → केवल प्रभावित हिस्से दोबारा बनते हैं, हटाए गए patch का पुराना output नहीं बचता।
- प्रमाण: `tests/test_scripts.py::TestPatches` — ninja के साथ असली multi-stage अनुकरण, साथ में negative control (सीधा `patch` यही stale output छोड़ता है)।
- APK gate: `aapt2 badging` में package = `chrome_public_manifest_package` (न हो तो `org.chromium.chrome`)। `DONE` में build key (patch hash + args) — patches बदलें तो वही state incremental आगे बढ़ती है।

## Variant (baseline अछूता रखना)
`chromium-source-build` को `variant=b1 seed=a1` से चलाएँ: src और शुरुआती out baseline (`a1`) से, नई state `crstate-<tag>-<cpu>-b1` में। UI capture: `source_variant=b1`।

**नियम:** baseline APK (a1) सत्यापित होने से पहले कोई patched build नहीं।
