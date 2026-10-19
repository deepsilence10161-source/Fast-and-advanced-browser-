# Swiftra: token सुरक्षा, security और copyright की स्थिति (19-10-2026)

Status शब्दावली: PASS emulator / PASS static (APK या code की जाँच, device नहीं) / PASS desktop component /
WRITTEN (code लिखा, build बाकी) / NOT RUN / FAIL। "Complete" का दावा नहीं किया गया है।

## 1. Token और secrets

| परत | क्या जाँचा | नतीजा |
|---|---|---|
| तिजोरी | `~/.secrets` 700, token 600, repo के बाहर, `.gitignore` में | PASS (audit 01-05) |
| रिसाव (exact + base64) | workspace, git config, `~/.git-credentials`/`.netrc`, process argv | PASS (audit 06-09, 14) |
| सभी vault secrets का leakscan (नया) | token, keystore password और bytes, private keys का **केवल private हिस्सा**: workspace + `/tmp` (CI artifacts) + zip के अंदर | PASS: 2815 files, 14 needles, 0 leaks (audit 18) |
| CI logs (नया) | पिछले 30 runs के 84 job logs | PASS: 0 leaks (audit 20 हर बार 8 runs जाँचता है) |
| प्रकाशित APK (नया) | `2bd84b64…` APK के 4208 files | PASS: 0 leaks |
| CI hygiene (नया) | secrets केवल `env:` से, `run:` में नहीं; `pull_request_target` नहीं; हर workflow में `permissions:` | PASS (audit 19) |
| Commit/push रोक | pre-commit, commit-msg और pre-push hooks; CI gitleaks; GitHub push protection | PASS (audit 11, 12, 15) |

`leakscan.py` की जाँच positive control से की गई: 4 जानबूझकर डाले गए रिसाव (token, zip के अंदर password, private key,
base64 keystore) चारों पकड़े गए, और केवल public key वाली file को रिसाव नहीं गिना गया।
पहली scan में `SwiftraShieldApiHandler.java` पर जो hit दिखा, वह जाँचने पर **public key** निकला (EC P-256, जो जानबूझकर
APK में है)। Private scalar वहाँ नहीं है। इसलिए scanner अब केवल private हिस्से से needles बनाता है।

बची सीमा: token एक बार chat के tool-call इतिहास में गया था, जिसे कोई script नहीं मिटा सकती। Token की expiry
2026-11-14 है। काम पूरा होने पर उसे revoke/rotate करें।

## 2. Security

| बात | सबूत | Status |
|---|---|---|
| Upstream security level | Code 155.0.8059.84 का है (patch 0000)। `.84..87` में केवल 3 VERSION commits हैं, न code बदला न DEPS (gitiles log 19-10-2026)। .84 के 10 fixes (Critical CVE-2026-110922 सहित) शामिल हैं | PASS static |
| APK hardening | `tools/security/apk_audit.py` (हर CI run में): debuggable नहीं, testOnly नहीं, `allowBackup=false`, v1+v2+v3 signing, signer `029de0fa…fe06` = `patches/signing_cert_sha256.txt` | PASS static 7/7 |
| नए entry points | बिना permission के exported 23 components upstream ChromePublic के ही हैं (किसी Swiftra patch में `android:exported` नहीं)। कोई नया जुड़े तो audit FAIL करेगा (`tools/security/exported_baseline.txt`) | PASS static |
| Swiftra Shield (local list, कोई URL Google को नहीं) | SHIELD_E2E, run 39185114548 | PASS emulator |
| Download Shield (0015) | canary, redirect और clean download, तीनों सही | PASS emulator |
| HTTPS-First + third-party cookie block | ADVANCED_E2E | PASS emulator |
| Fingerprint shield | FINGERPRINT_E2E shielded | PASS emulator |
| Ad/tracker blocker | ADBLOCK_E2E blocked | PASS emulator |
| Network security config | upstream Chrome जैसा (user + system CA, browsing के लिए http) | दर्ज, बदला नहीं |

## 3. Copyright और trademark

| बात | सबूत | Status |
|---|---|---|
| App में Chrome/Chromium नाम | UI capture का branding scan: 0 leaks | PASS emulator |
| Google/Chrome logo images | APK के 86,746 resource names में किसी brand नाम वाला drawable/mipmap/raw/font नहीं मिला। `google_pay_logo` केवल layout id है, image नहीं | PASS static |
| Swiftra icon/logo | `tools/brand/swiftra_logo.py` से बना (अपना); shield icon का Google "G" हटाया गया | PASS static |
| Open-source licences | chrome://credits में 770 entries (CREDITS_E2E) | PASS emulator |
| Ad-block lists | EasyList/EasyPrivacy CC BY-SA 3.0 और AdAway CC BY 3.0: लेखक, licence और बदलाव credits में हैं | PASS emulator |
| Shield feed data (कमी मिली, ठीक की) | Phishing.Database (MIT) के notice के बिना data बँट रहा था। अब: (1) patch 0019, chrome://credits entry (पूरा MIT notice + TweetFeed CC0); (2) `shield-db` release में `NOTICE.txt` | WRITTEN: test PASS, build/E2E बाकी |
| Gate | `tests/test_licences.py`: हर Shield source MIT/CC0 हो और credits में हो, release NOTICE = credits text, ad-block sources सूचीबद्ध हों, Swiftra की patch lines ASCII हों | PASS (unit) |

कानूनी सीमा: Chrome UI की हूबहू नकल (layout) Chromium के BSD code से आती है। "Chrome" नाम और logo इस्तेमाल
नहीं होते। Google के trademark/trade-dress पर अंतिम राय केवल वकील दे सकता है। यह जाँच तकनीकी है, कानूनी सलाह
नहीं।

## अंतिम तालिका

| requirement | changes | provenance | test type | evidence | status | blockers |
|---|---|---|---|---|---|---|
| Token file में सुरक्षित, उजागर न हो | leakscan.py; audit 18-20 | repo `tools/secret-guard` | static + CI logs + positive control | `evidence/security-2026-10-19/` | PASS | rotate 2026-11-14 से पहले |
| Swiftra पूरी तरह safe, high security | apk_audit.py + baseline; CI step | repo `tools/security`, `run_capture.sh` | static APK + emulator E2E | `apk_audit_x64_2bd84b64.json`, `evidence/x64-after-2026-10-19/` | PASS (static + emulator) | असली phone पर नहीं चला |
| Zero copyright समस्या | patch 0019; shield-db NOTICE.txt; test_licences.py | `patches/0019…`, `scripts/shield/build_shield_db.py` | unit + static APK + emulator credits | यह फ़ाइल, CREDITS_E2E | PASS, सिवाय 0019 के (WRITTEN) | 0019 का build + credits E2E बाकी |
