# Token सुरक्षा व्यवस्था (secret-guard)

उद्देश्य: GitHub token (और कोई भी secret) गलती से भी कहीं उजागर न हो — न चैट output में, न log, न commit, न push, न CI log।

## परतें
| परत | फ़ाइल | क्या करती है |
|---|---|---|
| तिजोरी | `~/.secrets/gh_token` (dir 700, file 600) | token का एकमात्र स्थान। यह किसी git repo के अंदर नहीं है। |
| API helper | `~/.secrets/gh.sh <api-path>` | token को curl config के रूप में **stdin** से देता है, इसलिए वह `ps`/argv में नहीं दिखता। हर output `redact.py` से गुज़रता है। |
| git auth | `~/.secrets/git-cred.sh` + `gitx` | credential helper सिर्फ़ `github.com` को token देता है। URL, `.git/config` या `~/.git-credentials` में कुछ नहीं लिखा जाता। |
| Redaction | `redact.py` | असली token, उसका base64 रूप, `github_pat_…`, `ghp_/gho_/ghu_/ghs_/ghr_…` और `Authorization:` header को `***REDACTED***` कर देता है। |
| pre-commit | `hooks/pre-commit` | staged बदलावों में exact-token match और gitleaks चलाता है। स्कैनर विफल हो तो commit रुक जाता है (fail-closed)। |
| commit-msg | `hooks/commit-msg` | commit message में token हो तो commit रोकता है। |
| pre-push | `hooks/pre-push` | push होने वाले सभी commits (content + message) को scan करता है। `commit --no-verify` से बचकर आया commit भी यहाँ रुकता है। |
| CI | repo में `.github/workflows/secret-scan.yml` | हर push/PR पर पूरी history का gitleaks scan, redacted log के साथ। binary SHA-256 से जाँचा जाता है। |
| GitHub | repo settings | secret scanning + push protection चालू हैं (API से सत्यापित)। |

## उपयोग (एजेंट के लिए अनिवार्य नियम)
- API के लिए हमेशा `~/.secrets/gh.sh`, git के लिए हमेशा `~/tools/secret-guard/gitx` इस्तेमाल करें।
- token फ़ाइल को कभी `cat`/`echo`/print न करें। token को URL, command-line argument, commit, log, report, artifact या Actions secret के मान के रूप में न डालें।
- हर नए clone में hooks लगाएँ: `~/tools/secret-guard/install-hooks.sh <repo>`
- workspace scan: `~/tools/secret-guard/scan.sh dir /home/user`
- repo history scan: `~/tools/secret-guard/scan.sh repo <repo>`
- पूरा E2E परीक्षण: `~/tools/secret-guard/test-e2e.sh <repo>` (असली token केवल local commit-परीक्षण में; push-परीक्षण केवल नकली token से)

## ज्ञात सीमाएँ (ईमानदारी से)
- उपयोगकर्ता ने token चैट संदेश में भेजा था। पहले turn में एजेंट ने उसे फ़ाइल में लिखने के लिए token को सीधे bash command में डाला था, इसलिए वह tool-call के इतिहास में भी है। इसे कोई script मिटा नहीं सकती। उपाय: काम पूरा होने पर token को revoke/rotate करें।
- `~/.secrets/` workspace snapshot में बना रहता है, ताकि अगले संदेशों में काम चल सके। workspace को किसी और से साझा न करें।
- GitHub push protection ने नकली (गैर-मान्य) token वाला push **नहीं रोका**। इसलिए local hooks और CI scan ही असली रोक हैं; push protection एक अतिरिक्त परत भर है।
- gitleaks पैटर्न पर आधारित है। नए/कस्टम प्रकार के secret छूट सकते हैं। असली GitHub token के लिए exact-match जाँच अलग से चलती है।
