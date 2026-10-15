# native-app: वर्तमान Android artifact

## यह artifact क्या है और क्या नहीं

- **है:** Chromium project का आधिकारिक public **snapshot** build `ChromePublic.apk`, जो source branch position 1697595 (Chrome 155 का branch point) के सबसे पास वाला snapshot है। इसे **बिना किसी बदलाव के** उपयोग किया गया है: package `org.chromium.chrome`, label "Chromium", version `155.0.8059.0`।
- **नहीं है:** Google Chrome Stable 155.0.8059.80। इसमें Google का branding, API keys, Google sign-in/Sync, Safe Browsing की Google-keyed सेवाएँ, Play-आधारित updates और Chrome-only private backends (Discover, Gemini आदि) नहीं हैं, या सीमित हैं।
- यह इस परियोजना का अपना source build भी नहीं है। Full source build मुफ़्त runners पर संभव नहीं (≥100 GB disk चाहिए; standard runner पर preflight exit 3)। विवरण `research/RESEARCH_REPORT.md` में है।

| Variant | Snapshot prefix | versionCode | ABI | आकार |
|---|---|---|---|---|
| Phone (ARM64) | `Android_Arm64` r1697603 | 805900004 | arm64-v8a | 381,736,687 bytes |
| Emulator / x86_64 | `AndroidDesktop_x64` r1697602 | 805900079 | x86_64 | 414,179,322 bytes |

SHA-256 checksums, `apksigner` result, `aapt2 badging` और 16 KB zipalign check `TESTING.md` में और release artifact की `SHA256SUMS.txt` / `APK_INSPECTION.txt` में हैं।

## Download कैसे करें

नवीनतम सत्यापित release: Actions run **38705582126** (commit `31b8091`)।

1. GitHub → **Actions → "Release artifacts (verified upstream APK + source ZIP, with checksums)"**। नवीनतम सफल run खोलें (या "Run workflow" दबाकर नया चलाएँ)।
2. नीचे **Artifacts → `release-artifacts`** download करें (GitHub login आवश्यक; 90 दिन तक उपलब्ध)।
3. जाँचें: `sha256sum -c SHA256SUMS.txt`, सभी पंक्तियाँ `OK` होनी चाहिए।

## Phone पर install (उपयोगकर्ता द्वारा)
```bash
adb install -r ChromePublic-Android_Arm64.apk
```
या फ़ाइल फ़ोन पर कॉपी करके "Install unknown apps" अनुमति से install करें। यह Google Chrome के साथ-साथ अलग app ("Chromium") के रूप में install होता है, Chrome को replace नहीं करता।

## स्वयं-चलाए जाने वाले परीक्षण
- `ui-capture.yml`: Android 16 (API 36) emulator पर पूरा UI journey, startup timings, memory और synthetic chat fixture। Evidence: `evidence/`, `reports/ui-compare/`।
- **अभी नहीं हुआ (आपकी आवश्यकता):** असली ARM64 फ़ोन पर install/launch/performance, और आपके Google खाते से login/Sync/Arena test। इसका protocol `TESTING.md` में है।
