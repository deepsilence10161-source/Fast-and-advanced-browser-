# Native update-button routing — 20-10-2026

## पुष्ट स्रोत और अलग वास्तविक सीमा

Android API reference: `FLAG_ACTIVITY_REQUIRE_NON_BROWSER` (API 30, 0x400) browser handler को स्वीकार नहीं करता; non-browser handler न होने पर ActivityNotFoundException। Official source: https://developer.android.com/reference/android/content/Intent#FLAG_ACTIVITY_REQUIRE_NON_BROWSER । Exact extracted reference `evidence/update-intent-2026-10-20/android-reference.txt` में है।

Pinned Chromium `155.0.8059.80` `UpdateStatusProvider.startIntentUpdate()` upstream Play Store path से यह flag रखता है। Swiftra 0020 URI को verified in-project HTTPS APK बदलता है, इसलिए केवल browser वाले device पर offer दिखना download button के काम करने का प्रमाण नहीं। पहले के menu/badge/Safety tests ने download item नहीं टैप किया था; वे इतिहासतः वही सीमित PASS हैं।

## न्यूनतम source change

0020 अब non-browser-only flag हटाकर Intent को `context.getPackageName()` पर सीमित करता है। इससे signed offer की HTTPS URL **इसी browser के सामान्य navigation/download security path** में जाती है, third-party chooser/app interception नहीं। NEW_TASK handling और ActivityNotFound catch वैसे ही हैं। कोई Safe Browsing/Download Shield/TLS/installer check नहीं हटाया गया।

Manifest ECDSA/domain separation/ABI/URL allowlist नहीं बदले। महत्वपूर्ण तथ्य: native offer `published_ms > PackageInfo.lastUpdateTime` देखता है; इसे versionCode-only comparator न समझें। इस बदलाव के लिए signing key दोबारा नहीं बनती।

## Acceptance, अभी परिणाम नहीं

- Pristine pinned provider पर old/new 0020 fuzz=0 apply/dry-run; targeted source regression test। यह static-only प्रमाण है।
- दोनों ABI का नया genuine Chromium source APK build; existing release certificate match, no relabel/re-sign shortcut।
- Actual Android signed good fixture में native Update Swiftra item टैप → सामान्य in-browser download path। Bad signature में item नहीं। केवल menu visibility को tap/download PASS न मानें।
- अपने public repo के वास्तविक APK को डाउनलोड करने पर matching published SHA/complete bytes, no install of another/untrusted package; no account/login/secret capture। Post-tap raw webpage screenshot/URL content capture नहीं; पहले safe blank/native menu और केवल allowlisted download metadata।
- Full x64 emulator/native ARM64 Redroid regression, Safety/Keystore/Shield; physical/account/Google legal gates अलग।

स्थिति: source fix तैयार; नए source builds और वास्तविक tap/download runtime validation अभी NOT RUN। इस दस्तावेज़ से working download या पूरा browser दावा नहीं किया जा रहा।
