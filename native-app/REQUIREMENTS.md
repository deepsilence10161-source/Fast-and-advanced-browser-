# Requirements: pass / fail / blockers

जाँच की तारीख: 2026-10-15 (Asia/Calcutta)। Status शब्दावली (handoff M के अनुसार):
`PASS (actual Android device)` · `PASS (Android emulator)` · `PASS (desktop/browser component)` · `PASS (static/signature/format only)` · `NOT RUN / BLOCKED` · `FAIL`।
हर "PASS" के पीछे एक वास्तविक run और evidence फ़ाइल है। Run IDs GitHub Actions के हैं।

## वर्तमान artifact (एक वाक्य में)
Chromium का आधिकारिक public snapshot `ChromePublic.apk` 155.0.8059.0 (`Android_Arm64` r1697603 और `AndroidDesktop_x64` r1697602), **बिना बदलाव**, package `org.chromium.chrome`। यह Google Chrome Stable 155.0.8059.80 नहीं है, और इस परियोजना का source build भी नहीं है।

## मूल लक्ष्य (B): कोई भी पूरा नहीं
| # | Requirement | Implemented | Real test | Exact evidence | Failures | Remaining blockers |
|---|---|---|---|---|---|---|
| 1 | Chrome Android की exact UI | नहीं (upstream Chromium UI ही है) | Emulator पर 20 screens का Chrome 133 reference बनाम Chromium 155 तुलना | `reports/ui-compare/*/COMPARISON.md`, run 38701948978 | सभी 20 साझा screens **mismatch** (Chrome 133 के सामने) | Stable 155 reference उपलब्ध नहीं (emulator पर 133)। उपयोगकर्ता के फ़ोन के non-private screenshots चाहिए। Chrome branding के लिए Google की लिखित अनुमति चाहिए |
| 2 | सभी Chrome features हूबहू | नहीं | 50 feature क्षेत्र source से trace, 20 screens पर व्यवहार देखा | `native-app/FEATURE_PARITY.md`, `reports/feature-parity.json` | Stable के सामने हर feature `not-tested` | Google-keyed सेवाएँ (Sync, sign-in, Safe Browsing keys, Discover, Gemini) fork में उपलब्ध नहीं या सीमित |
| 3 | Chrome से आगे की मापनीय क्षमताएँ | नहीं (केवल C1 का synthetic prototype) | Synthetic chat fixture | `experiments/chat-rendering/`, नीचे की पंक्ति A3 | — | Chrome baseline पहले पास होना चाहिए; असली फ़ोन पर same-device benchmark चाहिए |
| 4 | वास्तविक निर्माण और परीक्षण जारी | आंशिक: CI, capture, release pipeline, **staged source build pipeline (सत्र 2)** | हाँ | `TESTING.md` §2.6 | इतिहास `TESTING.md` में | Source build से APK बने और सत्यापित: arm64 (run 38841258069) और x64 (run 38841255946), मुफ़्त runners पर; x64 emulator पर पूरा UI + chat fixture 10/10 PASS (run 38865720986) |

## Gates (B)
| Gate | Status | Evidence | Blocker |
|---|---|---|---|
| Exact UI parity vs Chrome Stable 155 | **NOT RUN / BLOCKED** | — | Stable 155 reference नहीं है। Emulator image में Chrome 133 है |
| UI बनाम उपलब्ध emulator reference (Chrome 133) | **FAIL** (मापा गया mismatch) | `reports/ui-compare/` | — |
| Exact feature parity | **NOT RUN / BLOCKED** | `native-app/FEATURE_PARITY.md` | Reference + Google services |
| Beyond-Chrome capabilities | **NOT RUN / BLOCKED** | `native-app/SCOPE_AND_ADVANCED_CAPABILITIES.md` | Baseline पहले, फिर real device |
| Android delivery: provenance | **PASS (static/signature/format only)** | `evidence/release-run-38700392608/` (GCS MD5+CRC32C, SHA-256, apksigner v2, aapt2, zipalign 16 KB) | — |
| Android delivery: reproducible build | **PARTIAL** (सत्र 2): staged source build से x64 और arm64 APK बने (runs 38841255946, 38841258069), apksigner/aapt2 PASS; byte-for-byte reproducibility की जाँच NOT RUN, tag 155.0.8059.80 (commit `43a1951…`), x64 run 38745313869 और arm64 run 38750988168। Restore-path PASS (run 38751068356: 57,552 edges, restore 514 s) | `research/RESEARCH_REPORT.md` §3b, `scripts/ci/chromium_stage.sh` | APK बनना और सत्यापित होना बाकी; कुल समय अभी अज्ञात |
| Android delivery: install + launch (emulator) | **PASS (Android emulator)** | run 38701948978: तीनों targets `reached_browser_ui` | — |
| Android delivery: install + launch (physical ARM64) | **NOT RUN / BLOCKED** | — | उपयोगकर्ता का फ़ोन |
| Android delivery: signed secure updates | **NOT RUN / BLOCKED** | — | अपना signing key + update channel नहीं (Chromium snapshot का upstream test signature है) |
| Arena E2E (account, long history, streaming, no reload) | **NOT RUN / BLOCKED** | — | उपयोगकर्ता-साक्षी session आवश्यक; credentials कभी नहीं माँगे जाएँगे |

## इस चरण के परिणाम (A)
| # | Requirement | Status | Evidence |
|---|---|---|---|
| A1 | Snapshot APK की अखंडता (MD5 + CRC32C + SHA-256 + v2 signature + 16 KB zipalign) | PASS (static/signature/format only) | run 38700392608, `evidence/release-run-38700392608/` |
| A2 | Chromium 155 ARM64 build x86_64 emulator पर ARM translation से चलता है | PASS (Android emulator) journey 21/21 (runs 38699920976, 38704128045), पर अस्थिर: 6 में से 2 runs में ANR, और renderer `SIGSEGV` in `libndk_translation.so` (web page पर "Aw, Snap!")। Performance प्रतिनिधि नहीं | `TESTING.md` §2.1, §3 #10–12 |
| A3 | Long-chat no-reload synthetic fixture (10 cases) | PASS (desktop/browser component) 3×10/10, desktop Chrome 155 headless (run 38699618638); PASS (Android emulator) 10/10 Chrome 133 और 10/10 Chromium 155 x64 (run 38701948978)। ARM64: **FAIL (environment)**, translation में renderer crash, इसलिए असली फ़ोन आवश्यक (run 38704128045)। दोहराव run 38704128045: Chrome 133 और Chromium x64 फिर 10/10 | `evidence/chat-*`, `evidence/ui-capture-run-38701948978/*/chat_fixture.json` |
| A4 | Startup timings (10 cold + 10 warm, `am start -W`) | मापा गया (emulator, प्रतिनिधि नहीं) | `TESTING.md` |
| A5 | Secret hygiene (gitleaks on every push + release source ZIP) | PASS (static) | `secret-scan.yml` runs, release run 38700392608 |
| A6 | Unit tests (Python 10 + Node 6) | PASS (desktop/browser component) | `unit-tests.yml` |

## उपयोगकर्ता से न्यूनतम आवश्यक input
1. अपने फ़ोन पर Chrome का version (Settings → About Chrome), फ़ोन model, Android version, और `research/CHROME_UI_INVENTORY.md` §2.5 के क्रम में **बिना account/निजी जानकारी के** screenshots।
2. अपने फ़ोन पर release artifact से `ChromePublic-Android_Arm64.apk` install करके: खुला या नहीं, crash हुआ या नहीं, और पहली स्क्रीन का screenshot।
3. (बाद में, वैकल्पिक) Arena test का समय, ताकि आप स्वयं login करके `TESTING.md` का protocol चलाएँ। Password, OTP या cookie कभी साझा न करें।
4. ~~Full source build के लिए paid runner~~: अब आवश्यक नहीं (सत्र 2: मुफ़्त runners पर staged build, §3b)।
