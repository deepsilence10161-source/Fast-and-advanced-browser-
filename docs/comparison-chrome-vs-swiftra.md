# असली Chrome बनाम Swiftra: विस्तृत तुलना (18-10-2026)

- असली Chrome = Chrome 155.0.8059.84 for Android (15-10-2026)। Chrome पर हमारे अपने माप केवल Chrome 133 (emulator image) से हैं; बाकी तथ्य Google के आधिकारिक स्रोतों से।
- Swiftra = Chromium 155.0.8059.80 source build (b1/a1), patches 0001-0009, commit b139e3b; x64 emulator + arm64 Redroid पर E2E।

- स्थिति के शब्द: **PASS (emulator)** = x64 Android emulator, **PASS (Redroid)** = arm64 Redroid, **static** = केवल स्रोत/कोड पढ़कर, **NOT RUN** = जाँचा नहीं, **कमी** = मौजूद नहीं।

- विजेता: **Swiftra** / **Chrome** / **बराबर** / **अनिर्णीत** (माप या test नहीं) / **लागू नहीं** (कानूनी विषय)।

- यही data रंगीन Excel रूप में: `docs/comparison-chrome-vs-swiftra.xlsx` (स्रोत: `tools/comparison/rows.py`)।


## तुलना तालिका

| # | क्षेत्र | सुविधा / मापदंड | असली Chrome 155 (Android) | Swiftra अभी | प्रमाण (test type + स्रोत) | Swiftra स्थिति | विजेता | कारण | Chrome को हराने का अगला कदम |
|---|---|---|---|---|---|---|---|---|---|
| 1 | A. आधार / अपडेट | Engine version | 155.0.8059.84 (Android stable, 15-10-2026) | 155.0.8059.80 (source build, x64 + arm64) | static: BUILD_INFO; S1 | PASS (build) | **Chrome** | .84 में 10 security fixes (1 critical: Prerender use-after-free CVE-2026-110922) जो .80 में नहीं | tag 155.0.8059.84 पर rebuild + पूरा E2E (tag मौजूद, HTTP 200 जाँचा) |
| 2 | A. आधार / अपडेट | Security update पहुँचना | Play Store से अपने-आप, हर 1-2 हफ़्ते | कोई update channel नहीं; Safety check सच बताता है कि version जाँच नहीं सकता | static + emulator (Safety check text); S1 | कमी | **Chrome** | Swiftra user को नया security fix अपने-आप नहीं मिलता | अपना signed in-app update channel (APK signature + version pin) + हर Chrome stable पर 48 घंटे में rebuild |
| 3 | A. आधार / अपडेट | Build पारदर्शिता | बंद (closed) build; Google की internal सेटिंग्स | हर बदलाव खुला patch (0001-0009), BUILD_INFO में patch hash, signer cert प्रकाशित | static: patches/, evidence/*/BUILD_INFO.txt | PASS (static) | **Swiftra** | कोई भी जाँच सकता है कि Swiftra में क्या बदला गया | reproducible build साबित करना (दो runners पर एक जैसा APK hash) |
| 4 | A. आधार / अपडेट | App की अपनी सुरक्षा | Play-signed, Play Protect | non-debuggable, अपना release key, दूसरे key वाला update reject, same-key update सफल | PASS: device checks 9/9 (emulator + Redroid) | PASS (emulator + Redroid) | **बराबर** | तकनीकी सुरक्षा दोनों में; Play वितरण का भरोसा Chrome के पास | release APK का SHA-256 + signer cert हर release पर प्रकाशित |
| 5 | A. आधार / अपडेट | Stability | करोड़ों users पर परखा हुआ | E2E runs में crash 0, ANR 0 | emulator + Redroid (c2d runs 39094623643 / 39094624570) | PASS (emulator + Redroid) | **अनिर्णीत** | Swiftra असली फ़ोन पर नहीं चला; Chrome का पैमाना बहुत बड़ा | असली फ़ोन पर लंबा soak test |
| 6 | B. सुरक्षा | Safe Browsing Standard: खतरे पकड़ने की क्षमता | local सूची (30-60 मिनट में update) + real-time hash-prefix जाँच Google के server-side सूची से | Swiftra Shield: ~908k signed entries (Phishing.Database MIT + TweetFeed CC0); phishing मज़बूत, malware कमज़ोर, UwS सूची नहीं | PASS: Shield E2E 13/13 (emulator + Redroid); S3 | आंशिक | **Chrome** | Google की सूची बहुत बड़ी, malware/UwS भी, और real-time | licence-साफ़ malware/UwS स्रोत + पेज-heuristics + बार-बार signed update |
| 7 | B. सुरक्षा | Safe Browsing Standard: privacy | safe-cache में न मिले URL का 4-byte encrypted hash-prefix Fastly OHTTP relay से Google को जाता है (IP छिपता है) | Standard में Google को URL/hash कुछ नहीं जाता; जाँच पूरी तरह फ़ोन पर | PASS: NetLog, 61 s window में Safe Browsing संपर्क 0 (c2c, c2d); S3, S4 | PASS (emulator + Redroid) | **Swiftra** | शून्य डेटा बाहर जाना hash-prefix भेजने से ज़्यादा निजी | यही privacy रखते हुए coverage बढ़ाना (ऊपर वाली पंक्ति) |
| 8 | B. सुरक्षा | Enhanced protection | real-time URL जाँच, AI classification, deep download scan, account से जुड़ी सुरक्षा | Google real-time URL जाँच काम करती है + Shield भी; AI/deep scan नहीं (झूठा दावा UI से हटाया) | PASS: ESB E2E (unwanted page block), c2b/c2c | आंशिक | **Chrome** | AI और deep scan Google के private backend पर | on-device model से page-heuristics (licence-साफ़), download hash जाँच Shield में |
| 9 | B. सुरक्षा | HTTPS-by-default (Always use secure connections, public sites) | Google ने Chrome 154/155 में सभी users के लिए default चालू किया (server rollout) | HTTPS-Upgrades चालू; पर Balanced HTTPS-First का auto-enable code में default बंद, इसलिए केवल Enhanced के साथ चालू | static: chrome_features.cc @155 में kHttpsFirstBalancedModeAutoEnable = DISABLED_BY_DEFAULT; Swiftra में Finch नहीं; S5 | कमी (static) | **Chrome** | HTTP site पर Chrome पहले चेतावनी देता है, Swiftra Standard में नहीं | patch: kHttpsFirstBalancedModeAutoEnable default चालू + E2E (http://example.com पर interstitial) |
| 10 | B. सुरक्षा | Warning page की सच्चाई | Chrome के लिए सही | "Google Safe Browsing ने पाया" जैसे झूठे दावे हटे; स्रोत सच-सच बताया जाता है | PASS: 0007 E2E (emulator + Redroid) | PASS | **बराबर** | दोनों अपने product के बारे में सच बोलते हैं | — |
| 11 | B. सुरक्षा | Site isolation (password sites) | Android पर default चालू | वही code, Android पर default चालू (kSiteIsolationForPasswordSites); Finch न होने से कोई कमी नहीं | static: components/site_isolation/features.cc @155 | PASS (static) | **बराबर** | एक ही engine और default | ज़्यादा RAM वाले फ़ोन पर full site-per-process विकल्प |
| 12 | B. सुरक्षा | Secure DNS (DoH) | automatic mode | automatic mode; Redroid NetLog में DoH upgrade दिखा | Redroid NetLog (c2d) | PASS (Redroid) | **बराबर** | एक ही व्यवहार | privacy-first DoH provider चुनने का साफ़ विकल्प पहली बार में |
| 13 | B. सुरक्षा | Post-quantum TLS + PQ WebCrypto (ML-KEM, ML-DSA, X-Wing) | Chrome 155 में | वही Chromium 155 engine | static; S7 | static | **बराबर** | एक ही engine | — |
| 14 | B. सुरक्षा | Password leak check | हाँ (Google account के साथ) | toggle दिखता है पर बिना sign-in के काम नहीं करता (settings fix बाकी) | static; device पर NOT RUN | कमी | **Chrome** | Google का leak database चाहिए | k-anonymity वाला licence-साफ़ विकल्प या toggle को सच-सच छिपाना |
| 15 | C. Privacy | Usage stats / crash reports | opt-in; चालू करने पर Google को जाते हैं | code स्तर पर बंद (non-official build, crash upload URL null) | static @155 + FRE में झूठा UMA checkbox हटाया (emulator) | PASS | **Swiftra** | कोई telemetry नहीं | — |
| 16 | C. Privacy | Server experiments (Finch / variations) | Google server से features चालू/बंद करता है | कोई server experiment नहीं; testing config भी बंद (disable_fieldtrial_testing_config) | static: patches/args.gn; chrome://version "default seed" | PASS (static) | **Swiftra** | व्यवहार अनुमानित और निजी; (कमी: Google के server-rollout वाले सुधार अपने-आप नहीं आते, देखें HTTPS पंक्ति) | ज़रूरी rollout features को patch से default चालू करना |
| 17 | C. Privacy | Startup पर background requests | Discover feed, doodle impression ping आदि (Chromium में मापा) | 0009 के बाद: Discover 2→0, doodle ping 2→0; doodle, AI Mode जाँच (+1 ListAccounts), suggestions, component update रखे | PASS: startup NetLog before/after (c2d), x64 + arm64 | PASS (emulator + Redroid) | **Swiftra** | कम requests = कम डेटा, कम tracking | Translate/optimization-guide/component updater की और छँटाई |
| 18 | C. Privacy | Form data Google को (Autofill crowdsourcing) | form signatures Google को भेजकर बेहतर prediction | बिना key के बंद (0009) | PASS: NetLog में content-autofill 0 | PASS | **Swiftra** | privacy में बेहतर (सटीकता अलग पंक्ति में) | — |
| 19 | C. Privacy | Third-party cookies | default में चालू (Privacy Sandbox 17-10-2025 को बंद; केवल Incognito में block) | वही default | static; S9 | static | **बराबर** | एक ही default | default में third-party cookies block (+ site-wise अपवाद) — इससे सीधे Chrome से आगे |
| 20 | C. Privacy | Ad / tracker blocking | केवल intrusive-ads filter (Better Ads) | वही engine; filter सूची component updater से आती है या नहीं — NOT RUN | NOT RUN | NOT RUN | **अनिर्णीत** | जाँचा नहीं | built-in blocker, licence-साफ़ सूची (EasyList GPLv3/CC BY-SA पर कानूनी gate) |
| 21 | D. सेवाएँ / features | Sign-in और Sync | पूरा Google account sync | काम नहीं करता: API key नहीं, Sync API Chromium-आधारित browsers के लिए प्रतिबंधित | static; पूरा flow NOT RUN | कमी | **Chrome** | Google की सेवा केवल Chrome के लिए | अपना end-to-end encrypted sync (बिना Google) |
| 22 | D. सेवाएँ / features | Password manager | Google Password Manager (cloud, passkeys, checkup) | local save अपेक्षित; बिना GMS के — NOT RUN | NOT RUN | NOT RUN | **Chrome** | Chrome का पूरा cloud ecosystem; Swiftra अभी साबित नहीं | local encrypted vault + export/import + E2E test |
| 23 | D. सेवाएँ / features | Autofill सटीकता | Google server predictions | केवल local heuristics (server बंद) | NOT RUN (form.html पर network जाँचा, भराई नहीं) | NOT RUN | **Chrome** | server predictions के बिना कुछ forms कम सटीक | on-device heuristics सुधारना + E2E भराई test |
| 24 | D. सेवाएँ / features | Translate | Google Translate | API key के बिना शायद नहीं चलेगा | NOT RUN | NOT RUN | **Chrome** | जाँच बाकी; Google backend | on-device translation (licence-साफ़ model) |
| 25 | D. सेवाएँ / features | Voice search / Lens | हाँ | Google backend; NOT RUN | NOT RUN | NOT RUN | **Chrome** | Google की private सेवाएँ | on-device speech/OCR विकल्प या सच-सच छिपाना |
| 26 | D. सेवाएँ / features | Gemini in Chrome | India में Android पर 7-10-2026 से; auto browse केवल AI Pro/Ultra (20/200 काम प्रतिदिन); Android पर अभी केवल US/UK English | नहीं | S6 | कमी | **Chrome** | Google का private AI | user की अपनी चुनी AI (Arena सहित) से page summary — privacy नियंत्रण के साथ |
| 27 | D. सेवाएँ / features | AI Mode button | हाँ | button दिखता है, eligibility request चलती है; खोलकर काम करना — NOT RUN | emulator (button + NetLog folae) | आंशिक | **अनिर्णीत** | E2E बाकी | AI Mode E2E test |
| 28 | D. सेवाएँ / features | Discover feed | personalised feed | हटाया (key बिना कभी load नहीं होता था) | PASS: NTP screenshot + NetLog (c2d) | जानबूझकर हटाया | **Chrome** | feature Chrome में है; Swiftra NTP साफ़ और तेज़ | बिना tracking वाला news/RSS विकल्प (opt-in) |
| 29 | D. सेवाएँ / features | Doodle | हाँ + impression ping | हाँ, impression ping नहीं | PASS: NetLog ddllog 2→0 | PASS | **Swiftra** | वही feature, कम tracking (थोड़ा फ़ायदा) | — |
| 30 | D. सेवाएँ / features | Push notifications (FCM) | हाँ | Google sender ID चाहिए — NOT RUN | NOT RUN | NOT RUN | **Chrome** | जाँच बाकी; GMS-निर्भर | UnifiedPush जैसा खुला विकल्प या सच-सच बताना |
| 31 | D. सेवाएँ / features | Safety check | update, passwords, Safe Browsing, permissions | सच बताता है पर version/password जाँच नहीं कर सकता | emulator | आंशिक | **Chrome** | update/leak backend नहीं | update channel के साथ version जाँच जोड़ना |
| 32 | D. सेवाएँ / features | Extensions | Android phone पर नहीं | नहीं | S8 | — | **बराबर** | दोनों में नहीं (Vivaldi 8.2 सितंबर 2026 से देता है) | Chromium desktop-android extensions phone पर — इससे सीधे Chrome से आगे |
| 33 | D. सेवाएँ / features | Incognito lock | हाँ | वही code अपेक्षित — NOT RUN | NOT RUN | NOT RUN | **अनिर्णीत** | जाँचा नहीं | E2E test |
| 34 | D. सेवाएँ / features | JPEG XL, नए web features | Chrome 155 में (jxl-rs Rust decoder) | वही Chromium 155 engine | static; S7 | static | **बराबर** | एक ही engine | — |
| 35 | E. UI / सच्चाई / कानूनी | UI ढाँचा | Chrome UI | Chromium का वही UI (NTP, omnibox, menu, tabs, settings) | emulator screenshots; Chrome 133 reference से screen-match "mismatch" | आंशिक | **Chrome** | Chrome reference से अभी पूरा मेल नहीं | screen-by-screen diff और सुधार |
| 36 | E. UI / सच्चाई / कानूनी | Settings की सच्चाई | Chrome के लिए सही | 8 झूठे दावे ठीक; 2 बाकी (Sign-in row, leak-check toggle) | PASS: settings crawl (emulator + Redroid) | आंशिक | **बराबर** | दोनों लगभग सच; Swiftra में 2 सुधार बाकी | बाकी 2 सुधार + crawl gate |
| 37 | E. UI / सच्चाई / कानूनी | Branding / trademark | Google Chrome | Swiftra नाम/icon; पर "Google" वाले कुछ strings बाकी (G1 कानूनी gate) | PASS: crawl leaks 0 (मुख्य screens); G1 BLOCKED | BLOCKED (G1) | **लागू नहीं** | तुलना का विषय नहीं, कानूनी शर्त | बाकी Google strings हटाना/कानूनी अनुमति |
| 38 | E. UI / सच्चाई / कानूनी | Copyright / licence | Google का अपना | Chromium BSD notice रखा; Shield डेटा MIT + CC0; non-commercial सूचियाँ बाहर | static | PASS (static) | **लागू नहीं** | कानूनी पालन | हर नए स्रोत पर licence gate |
| 39 | F. Performance | Cold start (median) | Chrome 133, x64 emulator: 824-1263 ms | x64 emulator: 1157 ms; arm64 Redroid: 698.5 ms (Chrome arm64 reference नहीं) | emulator + Redroid (c2d); chrome_ref runs 38701948978 / 38704128045 | मापा | **Chrome** | केवल x64 emulator पर, अलग version (133 बनाम 155); असली फ़ोन पर अनिर्णीत | एक ही फ़ोन पर Chrome 155 बनाम Swiftra माप; startup trace से धीमे हिस्से हटाना |
| 40 | F. Performance | Warm start (median) | Chrome 133, x64 emulator: 511.5-779 ms | x64 emulator: 777.5 ms; arm64 Redroid: 184 ms | emulator + Redroid (c2d) | मापा | **Chrome** | x64 emulator पर Chrome तेज़ या बराबर; अलग version | वही |
| 41 | F. Performance | Memory (PSS, example.com के बाद) | Chrome 133, x64 emulator: 129.9-132.1 MB | x64 emulator: 147.7 MB; arm64 Redroid: 275.0 MB | emulator + Redroid | मापा | **Chrome** | x64 पर Swiftra ~12% ज़्यादा; version अलग | बराबर version पर माप, memory trace, बेकार services बंद |
| 42 | F. Performance | Page load / JS speed (Speedometer आदि) | — | — | NOT RUN | NOT RUN | **अनिर्णीत** | किसी का माप नहीं | एक ही फ़ोन पर benchmark suite |
| 43 | F. Performance | Data / battery (background) | ज़्यादा background requests | startup पर कम requests | आंशिक: केवल request गिनती (c2d), battery NOT RUN | आंशिक | **अनिर्णीत** | कम requests का फ़ायदा अपेक्षित, मापा नहीं | battery-historian माप |
| 44 | G. Arena लंबी chat | लंबी chat fixture (300 संदेश, streaming, draft, scroll) | Chrome 133: 10/10 | 10/10 (emulator + desktop) | emulator fixture | PASS (fixture) | **बराबर** | दोनों पास; first-render समय बहुत अस्थिर (Chrome 58-505 ms) | fixture में दोहराकर median तुलना |
| 45 | G. Arena लंबी chat | असली Arena पर लंबी chat | — | NOT RUN (user के अपने फ़ोन पर ही) | NOT RUN | NOT RUN | **अनिर्णीत** | जाँचा नहीं | user के फ़ोन पर test |

## अंतिम सारांश

कुल **45** पंक्तियाँ। Swiftra **7**, Chrome **19**, बराबर **10**, अनिर्णीत **7**, लागू नहीं **2**।

| क्षेत्र | Swiftra | Chrome | बराबर | अनिर्णीत | लागू नहीं |
|---|---|---|---|---|---|
| A. आधार / अपडेट | 1 | 2 | 1 | 1 | 0 |
| B. सुरक्षा | 1 | 4 | 4 | 0 | 0 |
| C. Privacy | 4 | 0 | 1 | 1 | 0 |
| D. सेवाएँ / features | 1 | 9 | 2 | 2 | 0 |
| E. UI / सच्चाई / कानूनी | 0 | 1 | 1 | 0 | 2 |
| F. Performance | 0 | 3 | 0 | 2 | 0 |
| G. Arena लंबी chat | 0 | 0 | 1 | 1 | 0 |
| **कुल** | **7** | **19** | **10** | **7** | **2** |

**ईमानदार फ़ैसला:** आज कुल मिलाकर **असली Chrome आगे है**। Swiftra अभी हर चीज़ में Chrome से आगे नहीं है।

- **Swiftra कहाँ जीतता है:** privacy और पारदर्शिता में। Standard Safe Browsing में शून्य डेटा बाहर जाता है, telemetry नहीं, server experiments नहीं, startup पर कम requests, doodle ping नहीं, और हर बदलाव खुले patch में।
- **Chrome कहाँ जीतता है:** security patch level (.84 बनाम .80), अपने-आप update, Safe Browsing coverage और Enhanced AI, HTTPS-by-default, Google की सेवाएँ (Sync, Password Manager, Translate, Gemini, Discover), और emulator पर start-समय/memory (अलग version पर मापा गया, असली फ़ोन पर नहीं)।
- **बराबर:** एक ही Chromium 155 engine वाली चीज़ें (site isolation, DoH, PQ crypto, JPEG XL, extensions का न होना, cookies default)।
- **अनिर्णीत:** असली फ़ोन पर speed, Speedometer, battery, AI Mode, Incognito lock, ad filter, असली Arena — यहाँ बिना माप के कोई दावा नहीं।

### Chrome को हराने का क्रम (प्राथमिकता अनुसार)

| क्रम | काम | असर | संबंधित पंक्ति |
|---|---|---|---|
| 1 | 155.0.8059.84 पर rebuild + पूरा E2E | security fixes में Chrome के बराबर | Engine version |
| 2 | HTTPS-First Balanced default चालू (patch) | HTTPS-by-default में बराबर | HTTPS पंक्ति |
| 3 | third-party cookies default block + built-in tracker blocker (licence-साफ़) | privacy में Chrome से साफ़ आगे | cookies, ad-block |
| 4 | Shield में malware/UwS स्रोत + on-device heuristics | Standard coverage में बराबरी, privacy में आगे | Safe Browsing |
| 5 | signed in-app update channel | update में बराबर | Security update |
| 6 | phone पर extensions (desktop-android) | Chrome Android से सीधे आगे | Extensions |
| 7 | एक ही असली फ़ोन पर Chrome 155 बनाम Swiftra: start, memory, Speedometer | speed का सच्चा फ़ैसला | Performance |
| 8 | बाकी NOT RUN: Translate, password manager, Incognito lock, AI Mode, असली Arena | अनिर्णीत पंक्तियाँ निपटाना | D, G |

क्रम 1-3 पूरे होने पर Chrome की 2 बढ़त (patch level, HTTPS) बराबर होंगी और cookies/tracker blocking से 2 नई Swiftra जीत बनेंगी; हर दावा फिर से E2E से साबित किया जाएगा।


## स्रोत

- **S1** — Chrome for Android Update 155.0.8059.84 (15-10-2026): https://chromereleases.googleblog.com/2026/10/chrome-for-android-update_01464551208.html
- **S2** — Stable Channel Update 155.0.8059.84/.85: 10 security fixes: https://chromereleases.googleblog.com/2026/10/stable-channel-update-for-desktop_01886704284.html
- **S3** — Google Security Blog: real-time, privacy-preserving URL protection (OHTTP): https://security.googleblog.com/2024/03/blog-post.html
- **S4** — Enterprise policy SafeBrowsingProxiedRealTimeChecksAllowed: https://chromeenterprise.google/intl/en_ca/policies/safe-browsing-proxied-real-time-checks-allowed/
- **S5** — Google: HTTPS by default (Chrome 154): https://blog.google/security/https-by-defau/
- **S6** — Google India: Gemini in Chrome with auto browse: https://blog.google/intl/en-in/products/bringing-gemini-in-chrome-with-auto-browse-to-india/
- **S7** — Chrome 155 release notes (JPEG XL, PQ WebCrypto): https://chromestatus.com/release-notes/155
- **S8** — Vivaldi 8.2: extensions on Android: https://vivaldi.com/blog/releases/
- **S9** — Privacy Sandbox: Update on plans (17-10-2025): https://privacysandbox.google.com/blog/update-on-plans-for-privacy-sandbox-technologies
- **S10** — Chromium @155: chrome/common/chrome_features.cc (HTTPS-First flags): https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/common/chrome_features.cc
- **S11** — Chromium @155: components/site_isolation/features.cc: https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/site_isolation/features.cc
- **S12** — Repo प्रमाण: evidence/c2d-2026-10-18, evidence/c2c-2026-10-17, evidence/shield-c2*, evidence/ui-capture-run-*/chrome_ref: https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/tree/main/evidence
