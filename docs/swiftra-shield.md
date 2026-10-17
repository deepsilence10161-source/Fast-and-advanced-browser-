# Swiftra Shield — Safe Browsing का on-device विकल्प

## समस्या (स्रोत से सत्यापित, Chromium 155.0.8059.80)
- Android पर Chromium URL जाँच `RemoteSafeBrowsingDatabaseManager` → `SafeBrowsingApiHandlerBridge` → Java `SafeBrowsingApiBridge` से करता है।
- Google का handler (GMS) केवल Google-branded builds में होता है। Non-branded build में handler `null` रहता है।
- `null` handler → `FAILURE_HANDLER_NULL`, जो non-recoverable है। इससे API बंद हो जाती है और **हर URL "safe" मान लिया जाता है** (fail-open)।
- फिर भी Settings में "Standard protection: चालू" दिखता है। यानी upstream non-branded build में सुरक्षा का दावा झूठा होता है।
- Hash real-time lookup के लिए `HasGoogleChromeBranding()` ज़रूरी है। URL real-time lookup केवल MBB या Enhanced mode में चलता है।

## हल (patches/0006-swiftra-shield.patch)
- `startUriLookupBySafeBrowsingApi` में, जब handler `null` हो **और** `!BuildConfig.IS_CHROME_BRANDED`, तब `SwiftraShieldApiHandler` लगाया जाता है।
  - Branded build का व्यवहार अपरिवर्तित रहता है।
- Handler एक signed, on-device सूची से उत्तर देता है:
  - सूची मिले → `SUCCESS` + threat type (malware > phishing > unwanted, जो माँगा गया हो)। Response status = `SUCCESS_WITH_LOCAL_BLOCKLIST`।
  - सूची न हो → `FAILURE` + `BLOCK_LIST_UNAVAILABLE`। यह recoverable है, इसलिए सूची आते ही अगली जाँच से सुरक्षा शुरू हो जाती है।
- URL canonicalization और host/path expressions Safe Browsing v4/v5 नियमों के अनुसार हैं।
  - Python (`scripts/shield/sbcanon.py`) और Java (`SwiftraShield.java`) दोनों 37 मानक vectors पर byte-for-byte एक जैसे हैं (`tests/test_shield.py`)।
- Lookup में 64-bit SHA-256 prefix पर binary search होता है। सूची `mmap` (read-only) से पढ़ी जाती है, पूरी heap में नहीं।
- **Network पर कोई browsing data नहीं जाता।** केवल सूची download होती है: Google या किसी तीसरे पक्ष को URL नहीं भेजे जाते।

## सूची का स्रोत और लाइसेंस
| Feed | उपयोग | लाइसेंस |
|---|---|---|
| Phishing.Database (links + domains) | phishing | MIT |
| TweetFeed blocklist (urls + domains) | malware | CC0 1.0 |
| Tranco top-100k | केवल build-time guard (वितरित नहीं) | MIT |

- **बाहर रखे गए:**
  - abuse.ch URLhaus/ThreatFox (ToU: केवल not-for-profit, derivative नहीं);
  - OpenPhish (non-commercial);
  - Block List Project (hpHosts provenance जोखिम);
  - CERT.PL (लाइसेंस अस्पष्ट);
  - phishing.army (NC) और अन्य NC/GPL feeds।
- **False positive guard** (केवल पूरे host वाली प्रविष्टियों पर लागू):
  - FIRST_PARTY suffix (google.com, microsoft.com, …);
  - shared-hosting apex;
  - Tranco top-100k।
  - किसी विशेष URL की प्रविष्टि फिर भी रहती है।
- Host प्रविष्टि से पहले से ढकी URL प्रविष्टियाँ हटाई जाती हैं। 20,000 से कम प्रविष्टियाँ हों तो build रुक जाता है (exit 2)।

## वितरण और सुरक्षा
- `.github/workflows/shield-db.yml` हर 6 घंटे चलता है:
  1. tests;
  2. build;
  3. ECDSA P-256 signature (key केवल secret `SWIFTRA_SHIELD_KEY` में);
  4. embedded public key से self-verify;
  5. prerelease `shield-db` पर publish।
- Format `SWSHZ001`: gzip(created u64, सूची-गिनती, varint delta hashes)।
  - Device पर क्रम: signature पहले, फिर decode (अधिकतम 8M प्रविष्टियाँ)। Decode के बाद क्रम और duplicate की जाँच होती है।
- Device पर ये सुरक्षा उपाय लागू हैं:
  - केवल HTTPS redirects।
  - 48 MB सीमा, 15/60 s timeouts।
  - tmp → rename (atomic)।
  - **Rollback रोक:** `created ≤ मौजूदा` या `created > अब + 2 दिन` वाली सूची अस्वीकार।
- Update अंतराल:
  - Wi-Fi/unmetered पर 24 घंटे;
  - metered पर 72 घंटे;
  - विफलता पर 1 घंटे बाद।
  - Download का आकार लगभग 5.7 MB (2026-10-17 को 908,341 प्रविष्टियाँ)।

## सीमाएँ (ईमानदारी से)
- पहली सूची download होने से पहले कोई सुरक्षा नहीं है (`BLOCK_LIST_UNAVAILABLE`)।
- यह Google की पूरी सूची के बराबर नहीं है।
  - फ़ायदा: phishing feed हर घंटे अपडेट होता है।
  - कमी: malware coverage कम है। Licence-clean malware URL स्रोत की खोज जारी है।
- Unwanted-software (UwS) की कोई सूची Shield में नहीं है। Standard protection में Google का `/s/unwanted.html` test page खुलता है (E2E में यही अपेक्षा दर्ज है)।

## Enhanced protection (c2b, patches/0007)
- **मापा गया तथ्य (2026-10-17, `tools/sb_rt_probe.py`):** Enhanced protection जिस URL real-time endpoint (`safebrowsing.google.com/safebrowsing/clientreport/realtime`, `UrlRealTimeMechanism`) को पूछता है, वह बिना key या login के भी उत्तर देता है।
  - `testsafebrowsing …/s/phishing.html` → SOCIAL_ENGINEERING / DANGEROUS
  - `…/s/unwanted.html` → UNWANTED_SOFTWARE / DANGEROUS
  - `…/s/swiftra_shield_canary.html` → SAFE
  - इसलिए Swiftra में Enhanced protection = Shield + Google real-time। Settings में Google को URL भेजे जाने की upstream सूचना सच है।
- **Defect (स्रोत @155):** `UrlRealTimeMechanism::OnLookupResponse` ताज़ा SAFE verdict पर hash DB (= Shield) नहीं देखता।
  - Async navigation check में अलग sync checker Shield देखता है।
  - पर non-async रास्ते (prefetch, async tracker न हो) में Google को अज्ञात और Shield में सूचीबद्ध URL Enhanced में खुल जाता, जबकि Standard में block होता।
  - **Fix:** non-branded build में हर SAFE verdict पर भी Shield देखा जाता है। नियम: कोई भी एक स्रोत खतरा बताए तो block। लागत: एक local lookup।
- **Interstitial की सत्यता:**
  - upstream explanation paragraph कहता है "Google Safe Browsing recently found …" और Google transparency report / error-report links देता है।
  - Shield verdict पर यह झूठ होता। non-branded build में यह paragraph खाली है।
  - Details में upstream का अनूदित risk paragraph और proceed link बने रहते हैं, इसलिए हर भाषा में पेशेवर अनुवाद सुरक्षित रहता है।
  - "Chrome strongly recommends…" अब "Swiftra …" है: patches/0002 scope में `security_interstitials_strings.grdp`।
- **कानूनी जोखिम (G1):** Google के internal Safe Browsing endpoint का fork में उपयोग Google की शर्तों के अधीन है। यह legal gate में दर्ज है।
- **E2E:** Settings UI से Enhanced चालू करके जाँच होती है। Public canary block होना चाहिए, `unwanted.html` block होना चाहिए, example.com खुलना चाहिए। `chrome://safe-browsing` के RT pings और `chrome://components` informational रूप में दर्ज होते हैं।

## सत्यापन
- `tests/test_shield.py`:
  - canonicalization parity;
  - builder guards;
  - Java twin (`javac -Werror`);
  - signature और tamper जाँच;
  - patch-sync।
- Chromium की errorprone + NullAway (JSpecify mode) configuration (`build/android/gyp/errorprone.py` @155) से दोनों Java files की local जाँच: 0 चेतावनी।
- E2E (emulator): canary URL → interstitial। परिणाम `TESTING.md` में।
