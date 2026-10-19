# -*- coding: utf-8 -*-
"""Chrome (Android 155) vs Swiftra comparison data, 19-10-2026.

Single source for docs/comparison-chrome-vs-swiftra.{md,xlsx}.
Winner values: Chrome | Swiftra | बराबर | अनिर्णीत | लागू नहीं
"""

DATE = "19-10-2026"
SWIFTRA_BUILD = ("Swiftra = Chromium 155.0.8059.80 source build (b1/a1) + patch 0000 (.84 के सभी security fixes), "
                 "patches 0000-0013, 0015-0017 (APK 2bd84b64, build 39145132480); x64 emulator E2E 39185114548 / 39202833756; "
                 "arm64 Redroid पर पिछला E2E 0011 APK का।")
CHROME_REF = ("असली Chrome = Chrome 155.0.8059.84 for Android (15-10-2026)। "
              "Chrome पर हमारे अपने माप केवल Chrome 133 (emulator image) से हैं; बाकी तथ्य Google के आधिकारिक स्रोतों से।")

COLUMNS = ["#", "क्षेत्र", "सुविधा / मापदंड", "असली Chrome 155 (Android)", "Swiftra अभी",
           "प्रमाण (test type + स्रोत)", "Swiftra स्थिति", "विजेता", "कारण", "महत्व",
           "user पर असर", "Chrome को हराने का अगला कदम", "मेहनत", "अंक (Chrome:Swiftra)"]

R = []
def row(*a):
    assert len(a) == 9, a
    R.append(a)

# ---------- A. आधार और सुरक्षा अपडेट ----------
A = "A. आधार / अपडेट"
row(A, "Engine version",
    "155.0.8059.84 (Android stable, 15-10-2026)",
    "code में .84 के सभी security fixes (patch 0000: Chromium 10 + V8 3 fixes); version label 155.0.8059.80 ही (जानबूझकर)",
    "static: साफ़ .80 files पर patch → 33 files .84 tag से byte-identical; builds 39103667941 (x64) / 39103669428 (arm64); "
    "emulator + arm64 Redroid E2E सारे gates PASS (39119631793, 39118129068); S1",
    "PASS (build + E2E)", "बराबर",
    "security code .84 के बराबर; केवल version label .80 दिखता है (VERSION/v8-version.h बदलने से लगभग पूरा rebuild होता)",
    "अगले Chrome stable पर 48 घंटे में delta patch; tag-आधारित पूरा rebuild (version label सहित) अलग से")
row(A, "Security update पहुँचना",
    "Play Store से अपने-आप, हर 1-2 हफ़्ते",
    "स्थायी link (releases/latest/download/Swiftra-<abi>.apk) पर केवल E2E-PASS + audit वाला APK (publish-latest.yml, "
    "LIVE: x64); patch 0020: signed manifest से app में upstream \"Update Swiftra\" menu/badge (24 घंटे में 1 बार); "
    "install खुद user करता है (Android installer वही Swiftra certificate माँगता है)",
    "x64 link: public download का SHA-256 = 2bd84b64 (मिलान); manifest: app का Java code + असली key से verify=true, "
    "1 byte बदलने पर false (javac 11 + org.json); 0020 वाला APK build queued, UPDATE_E2E NOT RUN",
    "आंशिक (link LIVE; 0020 static/unit PASS, device NOT RUN)", "Chrome",
    "Chrome Play Store से अपने-आप install करता है; Swiftra बताता है पर install user के tap से होता है",
    "0020 वाला APK + UPDATE_E2E (x64 + arm64); हर Chrome stable पर जल्दी rebuild")
row(A, "Build पारदर्शिता",
    "बंद (closed) build; Google की internal सेटिंग्स",
    "हर बदलाव खुला patch (0001-0009), BUILD_INFO में patch hash, signer cert प्रकाशित",
    "static: patches/, evidence/*/BUILD_INFO.txt",
    "PASS (static)", "Swiftra",
    "कोई भी जाँच सकता है कि Swiftra में क्या बदला गया",
    "reproducible build साबित करना (दो runners पर एक जैसा APK hash)")
row(A, "App की अपनी सुरक्षा",
    "Play-signed, Play Protect",
    "non-debuggable, अपना release key, दूसरे key वाला update reject, same-key update सफल",
    "PASS: device checks 9/9 (emulator + Redroid)",
    "PASS (emulator + Redroid)", "बराबर",
    "तकनीकी सुरक्षा दोनों में; Play वितरण का भरोसा Chrome के पास",
    "release APK का SHA-256 + signer cert हर release पर प्रकाशित")
row(A, "Stability",
    "करोड़ों users पर परखा हुआ",
    "E2E runs में crash 0, ANR 0",
    "emulator + Redroid (c2d runs 39094623643 / 39094624570)",
    "PASS (emulator + Redroid)", "अनिर्णीत",
    "Swiftra असली फ़ोन पर नहीं चला; Chrome का पैमाना बहुत बड़ा",
    "असली फ़ोन पर लंबा soak test")

# ---------- B. सुरक्षा ----------
B = "B. सुरक्षा"
row(B, "Safe Browsing Standard: खतरे पकड़ने की क्षमता",
    "local सूची (30-60 मिनट में update) + real-time hash-prefix जाँच Google के server-side सूची से",
    "Swiftra Shield: ~908k signed entries (Phishing.Database MIT + TweetFeed CC0); phishing मज़बूत, malware कमज़ोर, UwS सूची नहीं",
    "PASS: Shield E2E 13/13 (emulator + Redroid); S3",
    "आंशिक", "Chrome",
    "Google की सूची बहुत बड़ी, malware/UwS भी, और real-time",
    "licence-साफ़ malware/UwS स्रोत + पेज-heuristics + बार-बार signed update")
row(B, "Safe Browsing Standard: privacy",
    "safe-cache में न मिले URL का 4-byte encrypted hash-prefix Fastly OHTTP relay से Google को जाता है (IP छिपता है)",
    "Standard में Google को URL/hash कुछ नहीं जाता; जाँच पूरी तरह फ़ोन पर",
    "PASS: NetLog, 61 s window में Safe Browsing संपर्क 0 (c2c, c2d); S3, S4",
    "PASS (emulator + Redroid)", "Swiftra",
    "शून्य डेटा बाहर जाना hash-prefix भेजने से ज़्यादा निजी",
    "यही privacy रखते हुए coverage बढ़ाना (ऊपर वाली पंक्ति)")
row(B, "Enhanced protection",
    "real-time URL जाँच, AI classification, deep download scan, account से जुड़ी सुरक्षा",
    "Google real-time URL जाँच काम करती है + Shield भी; AI/deep scan नहीं (झूठा दावा UI से हटाया)",
    "PASS: ESB E2E (unwanted page block), c2b/c2c",
    "आंशिक", "Chrome",
    "AI और deep scan Google के private backend पर",
    "on-device model से page-heuristics (licence-साफ़), download hash जाँच Shield में")
row(B, "HTTPS-by-default (Always use secure connections, public sites)",
    "Google ने Chrome 154/155 में सभी users के लिए default चालू किया (server rollout)",
    "patch 0010: Balanced HTTPS-First default चालू — HTTPS न देने वाली public site पर native चेतावनी "
    "(\"This site doesn't support a secure connection\"), HTTP page बिना अनुमति fetch नहीं होता",
    "emulator x64 (39119631793) + arm64 Redroid (39118129068): ADVANCED_E2E PASS (warning_dialog, HTTP hits 0); "
    "पहले (0009): HTTP चुपचाप खुला (39103561212/39103562181); desktop Chromium 156 पर तरीका सत्यापित; S5",
    "PASS (emulator + arm64)", "बराबर",
    "Chrome यही server rollout (Finch) से देता है; Swiftra में code default, किसी server पर निर्भर नहीं",
    "Settings में strict HTTPS-only विकल्प (private network सहित) + उसका E2E")
row(B, "Warning page की सच्चाई",
    "Chrome के लिए सही",
    "\"Google Safe Browsing ने पाया\" जैसे झूठे दावे हटे; स्रोत सच-सच बताया जाता है",
    "PASS: 0007 E2E (emulator + Redroid)",
    "PASS", "बराबर",
    "दोनों अपने product के बारे में सच बोलते हैं",
    "—")
row(B, "Site isolation (password sites)",
    "Android पर default चालू",
    "वही code, Android पर default चालू (kSiteIsolationForPasswordSites); Finch न होने से कोई कमी नहीं",
    "static: components/site_isolation/features.cc @155",
    "PASS (static)", "बराबर",
    "एक ही engine और default",
    "ज़्यादा RAM वाले फ़ोन पर full site-per-process विकल्प")
row(B, "Secure DNS (DoH)",
    "automatic mode",
    "automatic mode; Redroid NetLog में DoH upgrade दिखा",
    "Redroid NetLog (c2d)",
    "PASS (Redroid)", "बराबर",
    "एक ही व्यवहार",
    "privacy-first DoH provider चुनने का साफ़ विकल्प पहली बार में")
row(B, "Post-quantum TLS + PQ WebCrypto (ML-KEM, ML-DSA, X-Wing)",
    "Chrome 155 में",
    "वही Chromium 155 engine",
    "static; S7",
    "static", "बराबर",
    "एक ही engine",
    "—")
row(B, "Password leak check",
    "हाँ (Google account के साथ)",
    "toggle दिखता है पर बिना sign-in के काम नहीं करता (settings fix बाकी)",
    "static; device पर NOT RUN",
    "कमी", "Chrome",
    "Google का leak database चाहिए",
    "k-anonymity वाला licence-साफ़ विकल्प या toggle को सच-सच छिपाना")

# ---------- C. Privacy ----------
C = "C. Privacy"
row(C, "Usage stats / crash reports",
    "opt-in; चालू करने पर Google को जाते हैं",
    "code स्तर पर बंद (non-official build, crash upload URL null)",
    "static @155 + FRE में झूठा UMA checkbox हटाया (emulator)",
    "PASS", "Swiftra",
    "कोई telemetry नहीं",
    "—")
row(C, "Server experiments (Finch / variations)",
    "Google server से features चालू/बंद करता है",
    "कोई server experiment नहीं; testing config भी बंद (disable_fieldtrial_testing_config)",
    "static: patches/args.gn; chrome://version \"default seed\"",
    "PASS (static)", "Swiftra",
    "व्यवहार अनुमानित और निजी; (कमी: Google के server-rollout वाले सुधार अपने-आप नहीं आते, देखें HTTPS पंक्ति)",
    "ज़रूरी rollout features को patch से default चालू करना")
row(C, "Startup पर background requests",
    "Discover feed, doodle impression ping आदि (Chromium में मापा)",
    "0009 के बाद: Discover 2→0, doodle ping 2→0; doodle, AI Mode जाँच (+1 ListAccounts), suggestions, component update रखे",
    "PASS: startup NetLog before/after (c2d), x64 + arm64",
    "PASS (emulator + Redroid)", "Swiftra",
    "कम requests = कम डेटा, कम tracking",
    "Translate/optimization-guide/component updater की और छँटाई")
row(C, "Form data Google को (Autofill crowdsourcing)",
    "form signatures Google को भेजकर बेहतर prediction",
    "बिना key के बंद (0009)",
    "PASS: NetLog में content-autofill 0",
    "PASS", "Swiftra",
    "privacy में बेहतर (सटीकता अलग पंक्ति में)",
    "—")
row(C, "Third-party cookies",
    "default में चालू (Privacy Sandbox 17-10-2025 को बंद; केवल Incognito में block)",
    "patch 0010: default में third-party cookies block (Settings/site-wise अपवाद संभव); first-party cookies (login) चालू",
    "emulator x64 (39119631793) + arm64 Redroid (39118129068): cross-site iframe का s3p cookie दोनों loads में नहीं, "
    "first-party fp=1 control मौजूद → PASS; पहले (0009): s3p=1 दिखा; S9",
    "PASS (emulator + arm64)", "Swiftra",
    "Chrome सामान्य tab में cross-site tracking cookies allow करता है; Swiftra default में रोकता है",
    "site टूटने पर 'इस site के लिए अनुमति' flow का E2E; storage partitioning audit")
row(C, "Ad / tracker blocking",
    "केवल intrusive-ads filter (Better Ads)",
    "patches 0012/0013: Swiftra Ad & Tracker Blocker (subresource_filter सभी sites पर, bundled ruleset "
    "swiftra.bbc65e3afc380c8e; EasyList/EasyPrivacy GPLv3/CC BY-SA + AdAway CC BY 3.0)",
    "emulator x64: ADBLOCK_E2E PASS verdict=blocked (runs 39185114548, 39202833756, APK 2bd84b64); speed test page पर "
    "ad requests 15 -> 0 (chromium_defaults बनाम swiftra); desktop component भी PASS (evidence/adblock-2026-10-18)",
    "PASS (emulator x64); arm64 NOT RUN", "Swiftra",
    "Chrome में सामान्य ad/tracker blocker नहीं (केवल Better Ads filter); Swiftra हर site पर रोकता है (device पर साबित)",
    "arm64 (नया build) पर ADBLOCK_E2E; site टूटने पर 'इस site पर अनुमति' flow")

# ---------- D. Google सेवाएँ और features ----------
D = "D. सेवाएँ / features"
row(D, "Sign-in और Sync",
    "पूरा Google account sync",
    "काम नहीं करता: API key नहीं, Sync API Chromium-आधारित browsers के लिए प्रतिबंधित",
    "static; पूरा flow NOT RUN",
    "कमी", "Chrome",
    "Google की सेवा केवल Chrome के लिए",
    "अपना end-to-end encrypted sync (बिना Google)")
row(D, "Password manager",
    "Google Password Manager (cloud, passkeys, checkup)",
    "local save अपेक्षित; बिना GMS के — NOT RUN",
    "NOT RUN",
    "NOT RUN", "Chrome",
    "Chrome का पूरा cloud ecosystem; Swiftra अभी साबित नहीं",
    "local encrypted vault + export/import + E2E test")
row(D, "Autofill सटीकता",
    "Google server predictions",
    "केवल local heuristics (server बंद)",
    "NOT RUN (form.html पर network जाँचा, भराई नहीं)",
    "NOT RUN", "Chrome",
    "server predictions के बिना कुछ forms कम सटीक",
    "on-device heuristics सुधारना + E2E भराई test")
row(D, "Translate",
    "Google Translate",
    "API key के बिना शायद नहीं चलेगा",
    "NOT RUN",
    "NOT RUN", "Chrome",
    "जाँच बाकी; Google backend",
    "on-device translation (licence-साफ़ model)")
row(D, "Voice search / Lens",
    "हाँ",
    "Google backend; NOT RUN",
    "NOT RUN",
    "NOT RUN", "Chrome",
    "Google की private सेवाएँ",
    "on-device speech/OCR विकल्प या सच-सच छिपाना")
row(D, "Gemini in Chrome",
    "India में Android पर 7-10-2026 से; auto browse केवल AI Pro/Ultra (20/200 काम प्रतिदिन); Android पर अभी केवल US/UK English",
    "नहीं",
    "S6",
    "कमी", "Chrome",
    "Google का private AI",
    "user की अपनी चुनी AI (Arena सहित) से page summary — privacy नियंत्रण के साथ")
row(D, "AI Mode button",
    "हाँ",
    "button दिखता है, eligibility request चलती है; खोलकर काम करना — NOT RUN",
    "emulator (button + NetLog folae)",
    "आंशिक", "अनिर्णीत",
    "E2E बाकी",
    "AI Mode E2E test")
row(D, "Discover feed",
    "personalised feed",
    "हटाया (key बिना कभी load नहीं होता था)",
    "PASS: NTP screenshot + NetLog (c2d)",
    "जानबूझकर हटाया", "Chrome",
    "feature Chrome में है; Swiftra NTP साफ़ और तेज़",
    "बिना tracking वाला news/RSS विकल्प (opt-in)")
row(D, "Doodle",
    "हाँ + impression ping",
    "हाँ, impression ping नहीं",
    "PASS: NetLog ddllog 2→0",
    "PASS", "Swiftra",
    "वही feature, कम tracking (थोड़ा फ़ायदा)",
    "—")
row(D, "Push notifications (FCM)",
    "हाँ",
    "Google sender ID चाहिए — NOT RUN",
    "NOT RUN",
    "NOT RUN", "Chrome",
    "जाँच बाकी; GMS-निर्भर",
    "UnifiedPush जैसा खुला विकल्प या सच-सच बताना")
row(D, "Safety check",
    "update, passwords, Safe Browsing, permissions",
    "सच बताता है; version जाँच अब हस्ताक्षरित update channel से (0005 v2 + 0020, device NOT RUN); password leak जाँच नहीं",
    "emulator (पुराना व्यवहार); version जाँच static/unit",
    "आंशिक", "Chrome",
    "leak backend नहीं; version जाँच का device E2E बाकी",
    "0020 build पर UPDATE_E2E; leak जाँच का निजी विकल्प")
row(D, "Extensions",
    "Android phone पर नहीं",
    "नहीं",
    "S8",
    "—", "बराबर",
    "दोनों में नहीं (Vivaldi 8.2 सितंबर 2026 से देता है)",
    "Chromium desktop-android extensions phone पर — इससे सीधे Chrome से आगे")
row(D, "Incognito lock",
    "हाँ",
    "वही code अपेक्षित — NOT RUN",
    "NOT RUN",
    "NOT RUN", "अनिर्णीत",
    "जाँचा नहीं",
    "E2E test")
row(D, "JPEG XL, नए web features",
    "Chrome 155 में (jxl-rs Rust decoder)",
    "वही Chromium 155 engine",
    "static; S7",
    "static", "बराबर",
    "एक ही engine",
    "—")

# ---------- E. UI / सच्चाई / कानूनी ----------
E = "E. UI / सच्चाई / कानूनी"
row(E, "UI ढाँचा",
    "Chrome UI",
    "Chromium का वही UI (NTP, omnibox, menu, tabs, settings)",
    "emulator screenshots; Chrome 133 reference से screen-match \"mismatch\"",
    "आंशिक", "Chrome",
    "Chrome reference से अभी पूरा मेल नहीं",
    "screen-by-screen diff और सुधार")
row(E, "Settings की सच्चाई",
    "Chrome के लिए सही",
    "8 झूठे दावे ठीक; 2 बाकी (Sign-in row, leak-check toggle)",
    "PASS: settings crawl (emulator + Redroid)",
    "आंशिक", "बराबर",
    "दोनों लगभग सच; Swiftra में 2 सुधार बाकी",
    "बाकी 2 सुधार + crawl gate")
row(E, "Branding / trademark",
    "Google Chrome",
    "Swiftra नाम/icon; पर \"Google\" वाले कुछ strings बाकी (G1 कानूनी gate)",
    "PASS: crawl leaks 0 (मुख्य screens); G1 BLOCKED",
    "BLOCKED (G1)", "लागू नहीं",
    "तुलना का विषय नहीं, कानूनी शर्त",
    "बाकी Google strings हटाना/कानूनी अनुमति")
row(E, "Copyright / licence",
    "Google का अपना",
    "Chromium BSD notice रखा; Shield डेटा MIT + CC0; non-commercial सूचियाँ बाहर; ad-block सूचियों के licence "
    "notices (ff35d89)। ff35d89 से पहले के APKs में credits page अधूरा था (sample_credits.html)",
    "static (ff35d89); नए APK में credits page की जाँच NOT RUN",
    "PASS (static)", "लागू नहीं",
    "कानूनी पालन",
    "हर नए स्रोत पर licence gate")

# ---------- F. Performance ----------
F = "F. Performance"
row(F, "Cold start (median)",
    "Chrome 133, x64 emulator: 824-1263 ms",
    "x64 emulator: 1157 ms; arm64 Redroid: 698.5 ms (Chrome arm64 reference नहीं)",
    "emulator + Redroid (c2d); chrome_ref runs 38701948978 / 38704128045",
    "मापा", "Chrome",
    "केवल x64 emulator पर, अलग version (133 बनाम 155); असली फ़ोन पर अनिर्णीत",
    "एक ही फ़ोन पर Chrome 155 बनाम Swiftra माप; startup trace से धीमे हिस्से हटाना")
row(F, "Warm start (median)",
    "Chrome 133, x64 emulator: 511.5-779 ms",
    "x64 emulator: 777.5 ms; arm64 Redroid: 184 ms",
    "emulator + Redroid (c2d)",
    "मापा", "Chrome",
    "x64 emulator पर Chrome तेज़ या बराबर; अलग version",
    "वही")
row(F, "Memory (PSS, example.com के बाद)",
    "Chrome 133, x64 emulator: 129.9-132.1 MB",
    "x64 emulator: 147.7 MB; arm64 Redroid: 275.0 MB",
    "emulator + Redroid",
    "मापा", "Chrome",
    "x64 पर Swiftra ~12% ज़्यादा; version अलग",
    "बराबर version पर माप, memory trace, बेकार services बंद")
row(F, "Page load / JS speed (Speedometer आदि)",
    "असली Chrome नहीं मापा; Chrome-जैसा proxy (उसी APK में Chromium defaults: field-trial config + Swiftra features बंद): "
    "load 2102 ms, LCP 1010 ms, 887.1 KiB, 47 requests",
    "x64 emulator, उसी run में A/B (6/6 loads): load 1203.5 ms (1.75x), LCP 964 ms (1.05x), 609.4 KiB (1.46x कम), "
    "32 requests; JS bench 354.4 ms (proxy का bench budget में नहीं चला)",
    "emulator x64 run 39202833756 (SPEED_E2E PARTIAL, evidence/speed-after-2026-10-19); बड़ा लाभ मुख्यतः ad blocking से",
    "मापा (emulator, proxy baseline)", "अनिर्णीत",
    "proxy असली Chrome नहीं (असली Chrome को Google के Finch studies मिलते हैं); असली फ़ोन पर माप नहीं",
    "arm64 PGO build पर A/B; असली फ़ोन पर Chrome 155 बनाम Swiftra")
row(F, "Data / battery (background)",
    "ज़्यादा background requests",
    "startup पर कम requests",
    "आंशिक: केवल request गिनती (c2d), battery NOT RUN",
    "आंशिक", "अनिर्णीत",
    "कम requests का फ़ायदा अपेक्षित, मापा नहीं",
    "battery-historian माप")

# ---------- G. Arena लंबी chat ----------
G = "G. Arena लंबी chat"
row(G, "लंबी chat fixture (300 संदेश, streaming, draft, scroll)",
    "Chrome 133: 10/10",
    "10/10 (emulator + desktop)",
    "emulator fixture",
    "PASS (fixture)", "बराबर",
    "दोनों पास; first-render समय बहुत अस्थिर (Chrome 58-505 ms)",
    "fixture में दोहराकर median तुलना")
row(G, "असली Arena पर लंबी chat",
    "—",
    "NOT RUN (user के अपने फ़ोन पर ही)",
    "NOT RUN",
    "NOT RUN", "अनिर्णीत",
    "जाँचा नहीं",
    "user के फ़ोन पर test")

# ---------- v3: नई पंक्तियाँ (18-10-2026 का अतिरिक्त शोध) ----------
row(B, "Fingerprinting से सुरक्षा",
    "built-in सुरक्षा नहीं: Incognito Script Blocking \"Do not launch\"; canvas-readback block केवल Canary flag",
    "patch 0011 (SwiftraFingerprintShield: canvas, WebGL readPixels, OfflineAudioContext पर site-आधारित noise), "
    "default चालू; builds 39127524068 / 39127525981",
    "before (0010 APK): FINGERPRINT_E2E FAIL no_shield (दो sites पर एक ही canvas/WebGL hash); after (0011 APK): "
    "FINGERPRINT_E2E PASS shielded — arm64 Redroid 39144748799 + x64 emulator 39144742833 (हर site पर अलग canvas/WebGL/audio "
    "मान, एक site के अंदर स्थिर); evidence/fingerprint-2026-10-18; S13",
    "PASS (actual device arm64 Redroid + emulator x64)", "Swiftra",
    "Chrome में built-in सुरक्षा नहीं",
    "canvas/WebGL/audio readback सुरक्षा default चालू — सीधे Chrome से आगे")
row(B, "Spam notification चेतावनी (on-device ML)",
    "Chrome Android का on-device model संदिग्ध site notifications पर चेतावनी देता है",
    "model नहीं आता (optimization-guide models को API key चाहिए; c2b में models 0)",
    "static + emulator (optimization-guide-internals खाली); S15",
    "कमी", "Chrome",
    "Google का model केवल Chrome को",
    "Shield सूची + notification दर-सीमा heuristics से चेतावनी")
row(B, "Screen-share में password/payment छिपाना (Android 15+)",
    "अक्टूबर 2026 से Chrome और WebView में",
    "NOT RUN (Chromium code + OS पर निर्भर)",
    "NOT RUN; S19",
    "NOT RUN", "अनिर्णीत",
    "जाँचा नहीं",
    "Android 15 emulator पर screen-share E2E")
row(C, "Default search engine",
    "Google (EU में choice screen)",
    "Chromium default (Google); पहली बार कोई चुनाव screen नहीं। patch 0014 (हर user को चुनाव, क्रम shuffle, "
    "कोई पहले से चुना नहीं) लिखा, series में अभी बंद",
    "emulator (omnibox); 0014: static tests, device NOT RUN",
    "PASS", "बराबर",
    "एक जैसा default",
    "पहली बार search engine चुनाव (privacy engines सहित) — Chrome से आगे")
row(D, "Listen to this page (पढ़कर सुनाना)",
    "हाँ, background playback के साथ (Google आवाज़ें)",
    "नहीं: public code में ReadAloudPlaybackHooks.createPlayback खाली (Google-internal)",
    "static: chrome/android/modules/readaloud @155",
    "कमी (static)", "Chrome",
    "backend केवल Google build में",
    "Android के on-device TextToSpeech से पढ़ना (offline, निजी) — privacy में आगे")
row(D, "PWA / web app install (WebAPK)",
    "असली WebAPK (app drawer में अलग app) Google server से बनता है",
    "WebAPK नहीं: AppHooks.getGooglePlayWebApkInstallDelegate() = null, server URL खाली; केवल home-screen shortcut अपेक्षित",
    "static: AppHooks.java, WebApkInstaller.java @155; device NOT RUN",
    "कमी (static)", "Chrome",
    "WebAPK बनाने की सेवा Google की",
    "फ़ोन पर ही signed WebAPK बनाना (शोध) या shortcut अनुभव सुधारना")
row(D, "Price tracking / shopping",
    "India में उपलब्ध; sign-in + sync ज़रूरी",
    "नहीं (sign-in नहीं)",
    "S16",
    "कमी", "Chrome",
    "Google account और server ज़रूरी",
    "बिना account local price watch (निजी)")
row(D, "Tabs: groups, pinned tabs, tab search",
    "हाँ (pinned tabs Chrome 144)",
    "वही engine; NOT RUN",
    "static अपेक्षित; S18",
    "NOT RUN", "बराबर",
    "एक ही code (device पर अभी जाँचना बाकी)",
    "E2E test; tab group sync अपने encrypted sync से")
row(D, "Layout: bottom address bar, bookmarks bar",
    "हाँ (bottom bar 2025, bookmarks bar 146); नया Gemini bottom-bar redesign (Sept 2026)",
    "वही engine; नया bottom-bar redesign code में default बंद (kAndroidBottomBar)",
    "static: chrome_feature_list.cc @155; S17",
    "NOT RUN", "बराबर",
    "मूल विकल्प एक जैसे; Gemini button केवल Chrome में",
    "E2E test")
row(D, "दूसरे password manager से autofill",
    "Chrome 135 से \"Autofill using another service\"",
    "वही engine; NOT RUN",
    "static अपेक्षित; S14",
    "NOT RUN", "बराबर",
    "एक ही code — Swiftra users के लिए Google PM का विकल्प",
    "Bitwarden-जैसे app के साथ E2E")

row(B, "Download की सुरक्षा (<a download>, JS downloads, redirect chain)",
    "Safe Browsing download check (ClientDownloadRequest Google को; Android पर MaliciousApkDownloadCheck Finch से)",
    "patch 0015 (Swiftra Download Shield): download URL और पूरी redirect chain local Shield सूची से; खतरा → "
    "\"File might be harmful\" dialog; Google को कोई ping नहीं",
    "emulator x64: DOWNLOAD_SHIELD_E2E PASS canary=blocked_dialog redirect=blocked_dialog clean=downloaded "
    "(runs 39185114548, 39202833756); static 6 tests",
    "PASS (emulator x64); arm64 NOT RUN", "अनिर्णीत",
    "Chrome की cloud जाँच ज़्यादा व्यापक (नए खतरे तुरंत), Swiftra की जाँच local और बिना Google ping: अलग trade-off",
    "arm64 पर DOWNLOAD_SHIELD_E2E; hash आधारित जाँच")
row(F, "बड़ी file download की गति",
    "Chromium parallel download (default 3 connections, Finch पर निर्भर)",
    "patch 0016 Speed Pack: 5 connections, 512 KiB slices (SwiftraParallelDownloading), HTTP/2 पर भी 5 अलग connections",
    "emulator x64 run 39202833756 (24 MiB, प्रति connection सीमित server): HTTP/1.1 9.4 s / 3 conns -> 6.4 s / 5 conns "
    "(1.47x); HTTP/2 24.1 s / 1 conn -> 5.3 s / 5 conns (4.55x); baseline = Chrome-जैसा proxy; desktop component 1.65x",
    "मापा (emulator, proxy baseline)", "अनिर्णीत",
    "server हर connection को सीमित करे तो लाभ; असली Chrome Android पर तुलना नहीं हुई",
    "0016 वाला APK + speed_e2e (chromium_defaults बनाम swiftra) + असली फ़ोन")

META = {
 "Engine version": ("उच्च", "पुराने security छेद खुले रहते हैं", "कम"),
 "Security update पहुँचना": ("उच्च", "नया fix user तक नहीं पहुँचता", "ज़्यादा"),
 "Build पारदर्शिता": ("मध्यम", "भरोसा", "मध्यम"),
 "App की अपनी सुरक्षा": ("उच्च", "नकली update से बचाव", "कम"),
 "Stability": ("उच्च", "crash से काम रुकना", "मध्यम"),
 "Safe Browsing Standard: खतरे पकड़ने की क्षमता": ("उच्च", "phishing/malware से बचाव", "ज़्यादा"),
 "Safe Browsing Standard: privacy": ("उच्च", "browsing निजी रहती है", "—"),
 "Enhanced protection": ("मध्यम", "opt-in users की अतिरिक्त सुरक्षा", "ज़्यादा"),
 "HTTPS-by-default (Always use secure connections, public sites)": ("उच्च", "HTTP पर डेटा चोरी का खतरा", "कम"),
 "Warning page की सच्चाई": ("मध्यम", "भरोसा", "—"),
 "Site isolation (password sites)": ("उच्च", "Spectre-जैसे हमलों से बचाव", "—"),
 "Secure DNS (DoH)": ("मध्यम", "DNS निजी", "कम"),
 "Post-quantum TLS + PQ WebCrypto (ML-KEM, ML-DSA, X-Wing)": ("मध्यम", "भविष्य की सुरक्षा", "—"),
 "Password leak check": ("मध्यम", "चोरी हुए password की चेतावनी", "मध्यम"),
 "Usage stats / crash reports": ("मध्यम", "निजता", "—"),
 "Server experiments (Finch / variations)": ("मध्यम", "निजता, अनुमानित व्यवहार", "—"),
 "Startup पर background requests": ("मध्यम", "कम डेटा, कम tracking", "कम"),
 "Form data Google को (Autofill crowdsourcing)": ("कम", "निजता", "—"),
 "Third-party cookies": ("उच्च", "cross-site tracking", "कम"),
 "Ad / tracker blocking": ("उच्च", "विज्ञापन, गति, निजता", "मध्यम"),
 "Sign-in और Sync": ("उच्च", "devices के बीच data", "ज़्यादा"),
 "Password manager": ("उच्च", "रोज़ का login", "मध्यम"),
 "Autofill सटीकता": ("मध्यम", "form भरना", "मध्यम"),
 "Translate": ("उच्च", "दूसरी भाषा के पेज पढ़ना", "ज़्यादा"),
 "Voice search / Lens": ("मध्यम", "बोलकर/फ़ोटो से खोज", "ज़्यादा"),
 "Gemini in Chrome": ("मध्यम", "AI सहायता", "ज़्यादा"),
 "AI Mode button": ("कम", "AI खोज", "कम"),
 "Discover feed": ("कम", "खबरें", "मध्यम"),
 "Doodle": ("कम", "निजता (थोड़ी)", "—"),
 "Push notifications (FCM)": ("उच्च", "site notifications", "ज़्यादा"),
 "Safety check": ("मध्यम", "एक जगह सुरक्षा जाँच", "मध्यम"),
 "Extensions": ("उच्च", "ad-block और tools", "ज़्यादा"),
 "Incognito lock": ("मध्यम", "निजी tabs की सुरक्षा", "कम"),
 "JPEG XL, नए web features": ("कम", "नई sites का सही दिखना", "—"),
 "UI ढाँचा": ("मध्यम", "Chrome जैसा अनुभव", "मध्यम"),
 "Settings की सच्चाई": ("मध्यम", "भरोसा", "कम"),
 "Branding / trademark": ("उच्च", "कानूनी जोखिम", "मध्यम"),
 "Copyright / licence": ("उच्च", "कानूनी जोखिम", "—"),
 "Cold start (median)": ("उच्च", "हर बार खोलने का इंतज़ार", "मध्यम"),
 "Warm start (median)": ("मध्यम", "app पर लौटना", "मध्यम"),
 "Memory (PSS, example.com के बाद)": ("मध्यम", "कम RAM वाले फ़ोन", "मध्यम"),
 "Page load / JS speed (Speedometer आदि)": ("उच्च", "हर पेज की गति", "मध्यम"),
 "Data / battery (background)": ("मध्यम", "data pack और battery", "मध्यम"),
 "लंबी chat fixture (300 संदेश, streaming, draft, scroll)": ("उच्च", "Arena का रोज़ उपयोग", "कम"),
 "असली Arena पर लंबी chat": ("उच्च", "Arena का रोज़ उपयोग", "कम"),
 "Fingerprinting से सुरक्षा": ("उच्च", "cookies के बिना tracking", "मध्यम"),
 "Spam notification चेतावनी (on-device ML)": ("मध्यम", "notification scam", "मध्यम"),
 "Screen-share में password/payment छिपाना (Android 15+)": ("मध्यम", "screen-share scam", "कम"),
 "Download की सुरक्षा (<a download>, JS downloads, redirect chain)": ("उच्च", "malware file से बचाव", "मध्यम"),
 "बड़ी file download की गति": ("मध्यम", "बड़ी files जल्दी", "कम"),
 "Default search engine": ("मध्यम", "खोज की निजता", "कम"),
 "Listen to this page (पढ़कर सुनाना)": ("मध्यम", "सुनकर पढ़ना, accessibility", "मध्यम"),
 "PWA / web app install (WebAPK)": ("मध्यम", "web apps को app की तरह चलाना", "ज़्यादा"),
 "Price tracking / shopping": ("कम", "खरीदारी में बचत", "ज़्यादा"),
 "Tabs: groups, pinned tabs, tab search": ("मध्यम", "बहुत tabs संभालना", "कम"),
 "Layout: bottom address bar, bookmarks bar": ("मध्यम", "एक हाथ से उपयोग", "कम"),
 "दूसरे password manager से autofill": ("उच्च", "Google PM के बिना login", "कम"),
}
WEIGHT = {"उच्च": 3, "मध्यम": 2, "कम": 1}

SOURCES = [
    ("S1", "Chrome for Android Update 155.0.8059.84 (15-10-2026)",
     "https://chromereleases.googleblog.com/2026/10/chrome-for-android-update_01464551208.html"),
    ("S2", "Stable Channel Update 155.0.8059.84/.85: 10 security fixes",
     "https://chromereleases.googleblog.com/2026/10/stable-channel-update-for-desktop_01886704284.html"),
    ("S3", "Google Security Blog: real-time, privacy-preserving URL protection (OHTTP)",
     "https://security.googleblog.com/2024/03/blog-post.html"),
    ("S4", "Enterprise policy SafeBrowsingProxiedRealTimeChecksAllowed",
     "https://chromeenterprise.google/intl/en_ca/policies/safe-browsing-proxied-real-time-checks-allowed/"),
    ("S5", "Google: HTTPS by default (Chrome 154)",
     "https://blog.google/security/https-by-defau/"),
    ("S6", "Google India: Gemini in Chrome with auto browse",
     "https://blog.google/intl/en-in/products/bringing-gemini-in-chrome-with-auto-browse-to-india/"),
    ("S7", "Chrome 155 release notes (JPEG XL, PQ WebCrypto)",
     "https://chromestatus.com/release-notes/155"),
    ("S8", "Vivaldi 8.2: extensions on Android",
     "https://vivaldi.com/blog/releases/"),
    ("S9", "Privacy Sandbox: Update on plans (17-10-2025)",
     "https://privacysandbox.google.com/blog/update-on-plans-for-privacy-sandbox-technologies"),
    ("S10", "Chromium @155: chrome/common/chrome_features.cc (HTTPS-First flags)",
     "https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/common/chrome_features.cc"),
    ("S11", "Chromium @155: components/site_isolation/features.cc",
     "https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/site_isolation/features.cc"),
    ("S13", "Privacy Sandbox feature status (Script Blocking: Do not launch)",
     "https://privacysandbox.google.com/overview/status"),
    ("S14", "Android Developers Blog: third-party autofill in Chrome 135",
     "https://android-developers.googleblog.com/2025/02/chrome-3p-autofill-services-update.html"),
    ("S15", "Google: AI to combat scams (Chrome Android notification warnings)",
     "https://blog.google/innovation-and-ai/technology/safety-security/how-were-using-ai-to-combat-the-latest-scams/"),
    ("S16", "Chrome Help: price tracking (Android) — देश/sign-in शर्तें",
     "https://support.google.com/chrome/answer/11625545?co=GENIE.Platform%3DAndroid"),
    ("S17", "9to5Google: Chrome Android bottom address bar",
     "https://9to5google.com/2025/06/24/chrome-bottom-address-bar-android/"),
    ("S18", "ZDNET: pinned tabs + tab groups, Chrome 144 Android",
     "https://www.zdnet.com/article/chrome-android-update-pinned-tabs-groups/"),
    ("S19", "Google: new Android scam protections (screen-share privacy in Chrome/WebView)",
     "https://blog.google/security/new-android-scam-protections/"),
    ("S20", "Chromium @155: AppHooks.java (WebAPK delegate null, server URL खाली)",
     "https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/android/java/src/org/chromium/chrome/browser/AppHooks.java"),
    ("S21", "Chromium @155: ReadAloudPlaybackHooks.java (खाली default)",
     "https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/android/modules/readaloud/public/java/src/org/chromium/chrome/modules/readaloud/ReadAloudPlaybackHooks.java"),
    ("S12", "Repo प्रमाण: evidence/c2d-2026-10-18, evidence/c2c-2026-10-17, evidence/shield-c2*, evidence/ui-capture-run-*/chrome_ref",
     "https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/tree/main/evidence"),
]

_ORDER = [A, B, C, D, E, F, G]
R.sort(key=lambda r: _ORDER.index(r[0]))
assert set(META) == {r[1] for r in R}, set(META) ^ {r[1] for r in R}

def points(r):
    w = WEIGHT[META[r[1]][0]]
    return {"Chrome": (w, 0), "Swiftra": (0, w), "बराबर": (w, w)}.get(r[6], (0, 0))

def full_rows():
    out = []
    for i, r in enumerate(R, 1):
        imp, impact, effort = META[r[1]]
        c, sw = points(r)
        out.append([i, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], imp, impact, r[8], effort,
                    f"{c}:{sw}" if r[6] in ("Chrome", "Swiftra", "बराबर") else "—"])
    return out

# Ordered plan to beat Chrome, used in summary.
PLAN = [
    ("1", "पूरा (18-10): .84 security fixes (patch 0000) + पूरा E2E", "security patch level में Chrome के बराबर", "Engine version", "कम"),
    ("2", "पूरा (18-10): HTTPS-First Balanced default चालू (patch 0010) + E2E", "HTTPS-by-default में बराबर", "HTTPS", "कम"),
    ("3", "पूरा (18-10): third-party cookies default block (patch 0010) + E2E", "Chrome से सीधे आगे (privacy)", "Third-party cookies", "कम"),
    ("4", "fingerprinting सुरक्षा (canvas/WebGL/audio) default चालू", "Chrome से सीधे आगे (Chrome में यह launch ही नहीं हुई)", "Fingerprinting", "मध्यम"),
    ("5", "built-in ad/tracker blocker (licence-साफ़ सूची)", "Chrome से सीधे आगे", "Ad / tracker blocking", "मध्यम"),
    ("6", "पहली बार search engine चुनाव screen", "privacy में आगे", "Default search engine", "कम"),
    ("7", "Shield में malware/UwS + heuristics", "Standard coverage में बराबरी, privacy में आगे", "Safe Browsing", "ज़्यादा"),
    ("8", "चल रहा (19-10): स्थायी latest link LIVE (x64) + patch 0020 signed update channel लिखा, build queued", "update में लगभग बराबर", "Security update", "ज़्यादा"),
    ("9", "on-device पढ़कर सुनाना (Android TTS)", "Chrome की कमी पूरी, निजता में आगे", "Listen to this page", "मध्यम"),
    ("10", "phone पर extensions (desktop-android)", "Chrome Android से सीधे आगे", "Extensions", "ज़्यादा"),
    ("11", "एक ही असली फ़ोन पर Chrome 155 बनाम Swiftra: start, memory, Speedometer, battery", "speed का सच्चा फ़ैसला", "Performance", "मध्यम"),
    ("12", "बाकी NOT RUN: Translate, password manager, 3P autofill, tabs, Incognito lock, AI Mode, असली Arena", "अनिर्णीत पंक्तियाँ निपटाना", "D, G", "मध्यम"),
]
