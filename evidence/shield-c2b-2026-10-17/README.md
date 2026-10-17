# c2b — सच्चा Safe Browsing interstitial + Enhanced protection (17-10-2026)

## Round 1: commit 4935b29 (0007 + 0002 में security_interstitials/autofill grdp)
- APK: x64 `ca70c628…7625b`, arm64 `c6505236…52ae8`।
- E2E runs: x64 39022805609, arm64 39023099504। दोनों 13/13 PASS।
- Honesty checks साफ़। leaks 0 (c2 में 8 थे), false_claims 0, device checks 9/9।
- Visual जाँच में एक leak मिला जिसे automated check नहीं पकड़ पाया: Enhanced protection चालू होने के बाद का banner "You have Chrome’s strongest security…" और Google "G" वाला shield icon (`round1_x64_leak_found.jpg`)।

## Round 2: commit a58f8ec (generated_resources.grd scope + blue_google_shield.xml overlay), harness ad4c462
- APK: x64 `20e288a58e0dbfdecd603deedb0d46de6fa0437056f7dcf3b5ecc7230e23b8e6`, arm64 `f861a40204cdba3f92863e57c74c1c70ff152abcf6b7312eab489f65ebc81e68`।
- Builds: 39025744172 / 39025748557। E2E: x64 39027175601, arm64 39027179286।
- दोनों 13/13 PASS:
  - हर blocked page की honesty check साफ़: "Chrome" नहीं, "Google Safe Browsing" नहीं, diagnostic/report-error links नहीं, risk paragraph मौजूद।
  - native UI में "Chrome" 0।
- leaks 0, false_claims 0, crash/ANR 0, device checks 9/9 (दोनों)।
- Cold/warm median: x64 1270/976 ms, arm64 711/254 ms। x64 पहले से धीमा रहा। यह emulator का उतार-चढ़ाव हो सकता है, पर अभी जाँचा नहीं गया।

## मुख्य माप
- Standard protection = केवल Shield: public canary block होता है, Google का `/s/unwanted.html` **खुल जाता है** (Shield में UwS सूची नहीं)।
- Enhanced protection (असली Settings UI से चालू):
  - `/s/unwanted.html` → harmful interstitial। यानी Google real-time सुरक्षा Swiftra में सच में काम करती है।
  - public Shield canary (Google के हिसाब से SAFE) फिर भी block होता है।
- `chrome://components`: "Real Time Url Checks Allowlist 151.0.7900.0" मौजूद।
- `chrome://safe-browsing`: Enhanced में हर warning पर `ClientSafeBrowsingReportRequest` (`WARNING_SHOWN`) Google को जाता है, Shield verdict पर भी (`url_api_type: ANDROID_SAFEBROWSING`, `is_async_check: false`)।
  - इसका मतलब public canary को async navigation के sync (local DB) checker ने पकड़ा।
  - 0007 का real-time fallback fix इस test में नहीं चला। वह non-async रास्ते के लिए defense-in-depth है (static only)।
- `chrome://optimization-guide-internals`: "Downloaded models:" के नीचे कोई model नहीं दिखा। इसके आधार पर Standard का दावा ("suspicious page → URLs/page content Google को") संदिग्ध है। अभी open।
