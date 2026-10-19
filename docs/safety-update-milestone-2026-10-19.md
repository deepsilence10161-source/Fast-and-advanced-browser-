# Swiftra: Safety / Keystore सत्यापन पड़ाव — 19-10-2026

**यह पूरे प्रोजेक्ट के पूरा होने का दावा नहीं है।** `MASTER_PROMPT.md` §15 का पूरा मूल दायरा अपरिवर्तित है। Current installed Chrome/physical phone तुलना, user-owned Google/Arena खाते, read-aloud, extensions और शेष parity/security gates अलग रहते हैं।

Publication अलग जाँची गई: public `Swiftra-arm64.apk` asset **656808306**, updated **16:37:12 UTC**, अब परीक्षण वाले `a3df4cf7…248f02` digest से मेल खाता है; x64 public digest `b1ea03ea…aa11ff` अपरिवर्तित है। उस निरीक्षण में publisher workflow **39284394628** अभी चल रहा था—APK की उपलब्धता को अंतिम signed-manifest/workflow completion न कहें। `publication-observed.json` में snapshot है। Rolling `--clobber` uploads atomic नहीं हैं; transient availability की अलग policy improvement शेष है।

## अब वास्तविक दोनों-ABI प्रमाण

| वातावरण | source APK SHA-256 | native Safety | fixtures के बाद उसी profile पर Keystore cookie | प्रमाण |
|---|---|---|---|---|
| Android API 36 / x86_64 emulator, Pixel 6 **profile**, भौतिक Pixel नहीं | `b1ea03ea9e77da9573ef5ad96c2078135acfe678c7ad1abee6feb4fddcaa11ff` | **5/5 PASS, restored=True** | **PASS** | [39278995763](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39278995763) |
| Android 14 / native ARM64 Redroid container, CPU translation नहीं, भौतिक फ़ोन नहीं | `a3df4cf79519ce8b3cbcda0bdfb54b8bb5e88be0c78c7e309c30254caf248f02` | **5/5 PASS, restored=True** | **PASS** | [39278999766](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39278999766) |

दोनों downloaded artifacts के JSON/XML/PNG consistency और file hashes जाँचे गए। वास्तविक screenshots का दृश्य निरीक्षण भी किया गया। दोनों workflows source APK का hash BUILD_INFO से **इंस्टॉल करने से पहले** मिलाते हैं। Native `versionCode` हर ABI की aapt badging से पढ़ा गया, अनुमान से नहीं: x64 **805908008**, arm64 **805908004**। दोनों का version name `155.0.8059.80`, package `com.swiftra.app`, variant `b1`, signer SHA-256 `029de0fab8f35ee0990ced814d38ab47d6a1be9bc49ffea9bbf4dc190010fe06` है।

Driver commit: `e28192ea0a2861d2251bd252ce82da7f11b227ce`। Source-fork commit: `9d2446ff0452353f9e915fbba8f0984d9f1a2656`; upstream tag commit `43a195105613ac83c21d3f14de279f4a045c7da0`। x64 producer `39223536200` के वास्तविक log में वही APK SHA फिर मिला; ARM source run `39223539138` भी सफल पूरा हुआ। नया APK इस harness परिवर्तन के लिए दोबारा build नहीं किया गया और focused mode से publish नहीं होता।

### Keystore में क्या सचमुच जाँचा गया

Safety की private-pref fixtures की वापसी के बाद **उसी profile पर नया CI-local cookie** बनाकर SQLite/WAL/journal तथा restart का असली browser behavior देखा गया:

`prefix=sw1 plain_value=False token_in_db=False wrapped_pref=True cookie_after_restart=True keystore2=True`

यह केवल exit 0 पर आधारित नहीं है: पुराना probe NOT_RUN पर भी 0 लौटाता है, इसलिए नया focused wrapper ऊपर की पूरी postcondition माँगता है। यह key-loss recovery, सभी पुराने cookies का संरक्षण, card/IBAN/password storage, biometric-bound encryption या physical hardware/StrongBox attestation का PASS नहीं है।

## Safety के पाँच मामले — दोनों ABI पर PASS

| मामला | अपेक्षित वास्तविक native स्थिति | अतिरिक्त शर्त |
|---|---|---|
| cache नहीं + rejected signature | `Can’t check Swiftra version` | success timestamp 0 ही |
| वास्तविक production signature verification | `Swiftra is up to date` | नया timestamp **ऐप ने** लिखा; exact version दृश्य |
| वास्तविक हालिया सफलता + rejected signature | `Swiftra is up to date` | वही genuine timestamp; exact version दृश्य |
| 48 घंटे से अधिक पुराना cache + rejected signature | `Can’t check Swiftra version` | stale timestamp नया नहीं हुआ |
| भविष्य की घड़ी वाला cache + rejected signature | `Can’t check Swiftra version` | future timestamp पर भरोसा नहीं |

Positive case वास्तविक HTTPS + app signature verifier इस्तेमाल करता है; उसकी सफलता सहायक ने preference में seed नहीं की। Native safe cards को वास्तविक header टैप करके खोला गया; version assertion कमजोर नहीं किया। Play Store button अनुपस्थित था। Password leak check / Google sign-in इससे प्रमाणित नहीं हुए।

## आवश्यकता-वार स्थिति

| आवश्यकता | बदलाव | उद्गम | जाँच प्रकार | प्रमाण | स्थिति | बाधाएँ / सीमाएँ |
|---|---|---|---|---|---|---|
| सही native Safety state | पाँच cases, genuine production check, cold processes, native card expansion | Chromium 155, AOSP 14/16 | native Android UI + prefs, दोनों ABI | ऊपर दोनों run links; `evidence/safety-update-2026-10-19/{x64-run-39278995763,arm64-run-39278999766}/` | **PASS (Android emulator)** | Redroid/Pixel profile को physical phone न मानें; full parity नहीं |
| private-pref fixture IO | numeric refs, encoded-marker collision/CR संरक्षण, whole-tree invariant, checked atomic rename, uid/mode/context | pinned AOSP + Chromium sources | दोनों Android positive paths; desktop negative controls | `android-source-research.json`, `tests/test_safety_pref_io.py` | **PASS (Android emulator)** positive path; **PASS (static only)** negative controls | original command-line flags restore शेष; physical refusal केवल component-tested |
| 0021 cookie encryption after fixtures | `sw1`, no plaintext, wrapped pref, restart recovery, Keystore2 | वास्तविक source-built APKs, existing provider | native cookie/DB behavior, दोनों ABI | दोनों `keystore_e2e.json` / logs | **PASS (Android emulator)** | software environments; key-loss/card/password/physical hardware tests नहीं |
| पूरा ARM artifact / मौजूदा release gate | full artifact के security/feature markers, Safety 5/5, Keystore और device checks 9/0; curated subset पर gate दोबारा चला | `39223539138` → `39274414134` | full native suite + baseline A/B + audit/device checks | [39274414134](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39274414134), `arm64-full-run-39274414134/curated-release-gate.txt` | **PASS (Android emulator)** मौजूदा E2E gate | यह हर performance metric/no-regression, physical phone, account या पूरे product का PASS नहीं; publication स्थिति अलग |
| unit / failure-path regressions | metadata privacy, atomic failure preservation, unsupported/physical refusal, postcondition correctness | driver `e28192e` | CI/local component tests | CI **39278996300: 266 passed, 1 skipped, 111.96s**; local **259 passed, 8 skipped, 122.51s**; relevant **95 passed** | **PASS (static only)** | native product का विकल्प नहीं; skips अलग दर्ज |
| startup / uniform no-regression | नया full ARM mixed data + historical context; नुकसान छिपाया नहीं | same-APK flags/fixtures; अलग-APK 0011 baseline; exact JSON/logs | native ARM measurements, small/unequal samples | `docs/startup-keystore-followup.md`, `performance-caveats.json` | **FAIL** uniform no-regression; causal attribution **BLOCKED** | cold +7.99% vs 0011; same-APK first-page LCP +11.51%, one bench +5.90%, cached cold load +5.24%; load/download gains universal Chrome/Keystore claim नहीं |
| Password Vault 0022 | 23 core + 9 अतिरिक्त auth-source audit; stale baseline claims सुधरे | pinned Chromium 155 | source inspection only | `docs/plans/password-vault*.md`, research JSONs | **PASS (static only)** audit; implementation **NOT RUN / BLOCKED** | backend/settings/helper guards, metadata-first strong/fresh auth UI, fail-closed writes, migration tests शेष |
| update-button download | inherited `REQUIRE_NON_BROWSER` जोखिम अलग दर्ज | Android official Intent docs + 0020 | static only | `docs/safety-update-e2e.md` | **NOT RUN / BLOCKED** | native tap/intent/download परीक्षण नहीं; menu visibility पर्याप्त नहीं |
| पूरा मूल उत्पाद | scope नहीं घटाया | `MASTER_PROMPT.md` §15 | पूर्ण acceptance अलग | मास्टर दस्तावेज़ / `TESTING.md` | **NOT RUN / BLOCKED** | G1 legal permission, full current-Chrome parity, physical ARM64, user-owned accounts और अन्य खुले gates |

## इतिहास नहीं छिपाया गया

1. **39264127317**: setup ParseError, 0/5, update fixture नहीं लिखा।
2. **39265508902**: 0/5; Expat code 14, text XML 43,894 bytes, 0 literal controls। Backgrounding अकेला समाधान नहीं था। AOSP numeric control references मूल compatibility finding थीं; binary XML/torn write मानकर नहीं चला गया।
3. **39266966087**: parser आगे बढ़ा, पर unacknowledged `exec-in` write empty पढ़ी गई; 0/5, restoration असफल। केवल disposable no-account CI profile प्रभावित हुआ। बाद में private staging + verified atomic rename आया।
4. **39268484164**: 3/5, restored=True; states सही, पर collapsed current cards ने required version छिपाया। Source + screenshot से वास्तविक expansion जोड़ा गया।
5. **39273364869**: x64 5/5, restored=True; original full artifacts सुरक्षित, publish job skipped। वास्तविक focused artifact को full release gate ने exit 1 से अस्वीकार भी किया, जैसा अपेक्षित था।
6. **39278995763 / 39278999766**: दोनों ABI artifacts में 5/5 + उसी profile का post-Safety Keystore PASS पुष्ट। Workflow status अकेला आधार नहीं बनाया गया।

स्थानीय tests ने encoded literal-marker collision और CR→LF normalization पहले पकड़ीं। सभी 32 C0 values text/attributes में round-trip होती हैं। Whole-tree semantic invariant disk write से पहले किसी बदलाव पर रुकता है। कोई control stripping या permissive recover parser नहीं है। Physical/unknown hardware पर fixture helper install/root और cleanup mutations से पहले रुकता है।

## स्रोत / सुरक्षा सीमा

- Real native Chromium source fork; WebView mockup / APK relabel नहीं। Signing keys/store दोबारा नहीं बनाए गए। कोई secret/private prefs artifacts में नहीं डाले गए।
- Commit guard ने `keystore` filename से जुड़े public file-checksums को पहले generic-key false positive माना और commit रोका। हर value वास्तविक file digest से सत्यापित करके checksum manifest को file/sha256 records में बदला गया; scanner/rules/allowlist को ढीला नहीं किया। बाद में staged और range scans साफ़ रहे। Readable log copies केवल trailing whitespace normalize करती हैं; exact originals `original-text-logs.json` में सुरक्षित हैं।
- केवल public repository के standard free runners उपयोग हुए। क्षणिक API queue/status/step snapshots को test outcome नहीं माना गया; actual downloaded artifacts निर्णायक हैं।
- Auth audit ने Android nonempty-message CHECK-crash और stock controller में BIOMETRIC_WEAK की अनुमति पकड़ी। इसे strong-only vault समझकर कॉपी न करें; 0022 अभी unimplemented है।
- `PASS (Android emulator)` ≠ `PASS (actual Android device)`। Google/Arena user-account validation और native update-button download अभी अलग हैं। पूर्ण सुरक्षा या अप्रमाणित “100x” तेज़ी का दावा नहीं है।
