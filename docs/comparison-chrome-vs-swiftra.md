# असली Chrome बनाम मौजूदा Swiftra बनाम Perfect Swiftra (17-10-2026)

स्थिति के शब्द (master prompt): **PASS (emulator)** = x64 Android emulator, **PASS (Redroid)** = arm64 Redroid,
**static** = केवल स्रोत/कोड, **NOT RUN** = जाँचा नहीं, **कमी** = मौजूद नहीं/गलत।
Chrome reference: इस परियोजना के पास केवल emulator image वाला Chrome 133 (proxy) है, असली फ़ोन पर Chrome 155 नहीं।
Swiftra = commit a58f8ec (Chromium 155.0.8059.80 source build, patches 0001–0007)।

| # | क्षेत्र | असली Chrome (Android) | मौजूदा Swiftra (प्रमाण) | Perfect Swiftra (लक्ष्य) | मौजूदा स्थिति |
|---|---|---|---|---|---|
| 1 | Engine / version | Chrome 155, Play Store | Chromium 155.0.8059.80 source build, x64 + arm64, अपना signing key | हर stable release के बाद जल्दी rebuild + reproducible build | PASS (build) |
| 2 | नाम / branding | Google Chrome | Swiftra नाम, icon, strings; settings crawl में leaks 0; interstitial और Enhanced banner ठीक | 100% Swiftra, Google trademark कहीं नहीं | PASS (emulator + Redroid); G1 कानूनी gate BLOCKED |
| 3 | UI ढाँचा | Chrome UI | Chromium का वही UI (NTP, omnibox, menu, tabs, settings) capture हुआ | Chrome जैसा हूबहू UI (कानूनी सीमा में) | आंशिक: Chrome reference से screen-match अभी "mismatch" |
| 4 | Start समय (cold / warm) | Chrome 133, x64 emulator: 824–1263 / 511.5–779 ms | x64 emulator: 827–1270 / 597–976 ms; arm64 Redroid: 704–711 / 247–254 ms | असली फ़ोन पर Chrome से मापने योग्य रूप से तेज़ | emulator only; असली फ़ोन NOT RUN |
| 5 | Safe Browsing: Standard | Google की सूची + privacy server से real-time hash check | Swiftra Shield: 908k entries, signed list; phishing मज़बूत; malware कमज़ोर; unwanted software (UwS) सूची नहीं | Shield + malware/UwS स्रोत + heuristics, Google Standard के बराबर या बेहतर | PASS (13/13 E2E, दोनों); कमी: malware/UwS |
| 6 | Safe Browsing: Enhanced | Google real-time + AI | Google real-time काम करता है (unwanted page block) + Shield भी; हर warning की report Google को | दोनों स्रोत मिलाकर, कानूनी मंज़ूरी के साथ | PASS (दोनों); G1 BLOCKED |
| 7 | Warning page की सच्चाई | Chrome के लिए सच | "Google Safe Browsing ने पाया" जैसे झूठ हटे; Swiftra नाम | झूठ 0 | PASS (दोनों) |
| 8 | Settings की सच्चाई | — | 5 झूठे दावे ठीक (FRE UMA, metrics toggle, "up to date", "Google LLC", dead Play button); Standard का विवरण अब भी गलत (API key नहीं, model नहीं) | झूठ 0 | open (अगला काम) |
| 9 | Sign-in / Sync | Google account sync | काम नहीं करता: Google API key नहीं, और Sync API Chromium-आधारित browsers के लिए प्रतिबंधित | अपना encrypted sync, या साफ़ "उपलब्ध नहीं" | कमी; पूरा flow device पर NOT RUN |
| 10 | Password manager | Google Password Manager (cloud) | local save अपेक्षित | local + encrypted export/import, leak-check विकल्प | NOT RUN |
| 11 | Translate | Google Translate | API key के बिना शायद नहीं चलेगा | on-device या दूसरा provider | NOT RUN |
| 12 | Voice, Lens, Discover, Gemini | हाँ | Google के private backend; NTP का ✦ button क्या करता है, जाँचना बाकी | या तो काम करे या UI से हटे (कोई dead button नहीं) | NOT RUN |
| 13 | Updates | Play Store auto-update | कोई update channel नहीं; Safety check सच बताता है ("version जाँच नहीं सकता") | अपना signed in-app update channel | कमी |
| 14 | Push notifications (FCM) | हाँ | Google sender चाहिए | काम करे या साफ़ बताया जाए | NOT RUN |
| 15 | Privacy / telemetry | usage stats और crash reports Google को (opt-in) | metrics और crash upload code स्तर पर बंद (non-official build) | वही; Standard mode में Google से कोई संपर्क नहीं | static |
| 16 | App की सुरक्षा | Play-signed | non-debuggable; अपना key; दूसरे key का update reject; same-key update | + reproducible build | PASS (device checks 9/9, दोनों) |
| 17 | Stability | — | E2E में crash 0, ANR 0 | असली फ़ोन पर भी 0 | PASS (emulator + Redroid) |
| 18 | Arena लंबी chat | सामान्य | test fixture 10/10 (emulator + desktop) | तेज़ खुलना, draft/scroll बना रहे, दोहरा send नहीं; user के फ़ोन पर साबित | आंशिक; असली Arena पर NOT RUN |

Standard protection के विवरण वाली पंक्ति (#8) का आधार:
- `components/optimization_guide/core/delivery/prediction_model_fetcher_impl.cc` @155 models को `google_apis::GetAPIKey()` से लाता है।
- `patches/args.gn` में कोई key नहीं है।
- E2E 39027179286 / 39027175601 में `chrome://optimization-guide-internals` पर "Downloaded models:" के नीचे कुछ नहीं था।
- इसलिए client-side phishing detection नहीं चलता, और "If a page does something suspicious, URLs and bits of page content are sent to Google Safe Browsing" Swiftra के व्यवहार से मेल नहीं खाता।
