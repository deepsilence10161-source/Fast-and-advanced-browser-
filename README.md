# Fast-and-advanced-browser-

Android के लिए Chrome जैसा (exact Chrome UI + feature parity) और उससे आगे की क्षमताओं वाला browser बनाने की परियोजना। **वर्तमान स्थिति: शोध और evidence चरण।** मूल आवश्यकताएँ (exact Chrome UI, पूरी Chrome feature parity, native login, Chrome से आगे की क्षमताएँ, असली Arena long-chat सुधार) **अभी पूरी या सत्यापित नहीं हैं।** विवरण `native-app/REQUIREMENTS.md` में है।

## Repo में क्या है

| Path | क्या है |
|---|---|
| `research/RESEARCH_REPORT.md` | दिनांकित, आधिकारिक-स्रोत आधारित शोध (architecture, branding/API/license, build, performance, UI, Arena long-chat, security, CI) |
| `research/CHROME_UI_INVENTORY.md` | वास्तविक capture से बनी Chrome UI inventory और capture protocol (क्या देखा गया, क्या नहीं) |
| `native-app/FEATURE_PARITY.md` | 50 Chrome feature क्षेत्र → Chromium source (stable commit पर जाँचा गया) → artifact → test → status |
| `native-app/SCOPE_AND_ADVANCED_CAPABILITIES.md` | अपरिवर्तित दायरा, gates, Chrome से आगे की क्षमताएँ (measurable targets सहित) |
| `native-app/REQUIREMENTS.md` | हर requirement का pass/fail/blocker |
| `native-app/README.md` | APK artifact कैसे पाएँ, जाँचें और install करें |
| `TESTING.md`, `reports/verification-summary.json` | सभी परीक्षण: passed/failed/blocked, platform और evidence के साथ, विफलताओं का इतिहास भी |
| `reports/ui-compare/` | Chrome reference बनाम Chromium artifact की screen-दर-screen तुलना (side-by-side PNG) |
| `evidence/` | Runs के चुने हुए screenshots/XML/JSON, `meta.json`, `provenance.json`, `journey.log` |
| `experiments/chat-rendering/` | Long-chat no-reload का **synthetic** प्रयोग (production feature नहीं, असली Arena पर परीक्षित नहीं) |
| `scripts/` | Snapshot fetcher, UI capture journey, तुलना, inventory, build preflight |
| `.github/workflows/` | `ui-capture` (emulator), `release-artifacts`, `unit-tests`, `secret-scan` |
| `PROJECT_RULES.md` | काम के नियम (evidence discipline, सुरक्षा) |

## परीक्षण दोबारा चलाना

```bash
python3 -m unittest discover -s tests -v                      # Python unit tests
node --test experiments/chat-rendering/chat-store.test.js     # ChatStore unit tests
bash scripts/build_chromium_baseline.sh --preflight-only      # host पर्याप्त है या नहीं (exit 3 = नहीं)
```
GitHub Actions में: **Actions → "UI capture" → Run workflow** (emulator पर Chrome reference बनाम Chromium), **"Release artifacts" → Run workflow** (जाँचा गया APK + source ZIP + SHA256SUMS)।

## सुरक्षा
Repo में कोई key/token नहीं है। हर push पर gitleaks scan चलता है (`secret-scan.yml`)। Release में source ZIP का भी gitleaks scan होता है।

## Branding / License
Chromium का कोड BSD-style license और third-party licenses के अधीन है। "Google Chrome" नाम और logo Google के trademark हैं और लिखित अनुमति के बिना उपयोग नहीं किए जा सकते। इसलिए वितरण से पहले branding gate (G4, `SCOPE_AND_ADVANCED_CAPABILITIES.md`) अनिवार्य है।
