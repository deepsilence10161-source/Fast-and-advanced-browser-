# c2c प्रमाण (17-10-2026): Settings की सच्चाई + variations + NetLog audit

| चीज़ | मान |
|---|---|
| Commit (patch/build) | d66e49f (0008 standard-local-and-esb-honest, `disable_fieldtrial_testing_config = true`) |
| Commit (E2E script) | f359f3d (NetLog: असली URL request बनाम केवल ज़िक्र) |
| Builds | x64 39051530292, arm64 39051531779 |
| APK sha256 x64 | 8221cc8c65a916eb0361ffd339f0ae7cc9724b5bf09013e0827d0dddbbbce988 |
| APK sha256 arm64 | 6e6d72e623017b3b42deb506804ea838d71eb2d7085f02b8ed91d7d7f12e413c |
| E2E दौर 1 (d66e49f) | ui-capture x64 39053115486, arm64 Redroid 39053116960: SHIELD_E2E PASS |
| E2E दौर 2 (f359f3d) | ui-capture x64 39055927613, arm64 Redroid 39055928718: SHIELD_E2E PASS |

## परिणाम (दोनों architecture, दौर 2)
- Standard cases 8/8, Enhanced cases 5/5 PASS।
- Safe Browsing page: Standard = "Protects you from sites, downloads, and extensions that are known to be dangerous"; Enhanced = "Real-time, proactive protection by sending more information to Google Safe Browsing"। झूठे दावे 0।
- Enhanced विवरण page: "In-depth scans for suspicious downloads", "signed in…Google services" और "Learn more" अब नहीं दिखते (screenshot देखा गया)।
- chrome://version: variations source = "default seed" (कोई server seed नहीं, testing config नहीं)।
- NetLog, Standard mode, 61 s window (local page, example.com, local phishing canary, 30 s idle): Google को URL request **0**, Safe Browsing host **0**। कुल URL requests 4 (सब test के अपने)। Google host केवल connection-pool/server-properties events में ज़िक्र के रूप में आते हैं (x64: HTTP_STREAM_JOB_CONTROLLER 5, QUIC reuse 5, prefs 1)।
- NetLog, Enhanced mode (positive control): `POST safebrowsing.google.com/safebrowsing/clientreport/realtime` ×3, `/clientreport/malware` ×4: audit सही से देखता है।
- Start (median, cold/warm): x64 emulator 1158.5 / 834.5 ms; arm64 Redroid 682 / 185.5 ms। Device checks 9/9, crash 0, ANR 0, branding leaks 0।

## सीमाएँ (ईमानदार)
- NetLog trace browser के चालू होने के बाद शुरू होता है; पहले start का traffic इस window में नहीं है।
- HTTP_STREAM_JOB_CONTROLLER events संभवतः DSE (www.google.com) preconnect हैं: URL request नहीं, पर connection बन सकता है। इसे हटाने का काम खुला है।
- असली फ़ोन पर NOT RUN।
