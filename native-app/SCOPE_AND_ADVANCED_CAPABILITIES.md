# दायरा और Chrome से आगे की capabilities

> यह दायरा **अपरिवर्तित** है। इसे "लगभग समान", केवल WebView, Custom Tab, HTML demo, screenshot mock या launcher में नहीं बदला जाएगा। किसी वास्तविक gate को हटाकर सफलता घोषित नहीं की जाएगी।

## A. मूल तीन लक्ष्य (जस के तस)

1. **हूबहू Chrome:** Google Chrome Android ऐप की exact UI और उपलब्ध सभी Chrome features वाला Android browser.
2. **Chrome से आगे:** मापनीय, अत्याधुनिक capabilities। यह अलग अनिवार्य आवश्यकता है, केवल विचारों की सूची नहीं।
3. **वास्तविक काम:** असली build और असली परीक्षण के साथ लगातार प्रगति।

**विशेष उपयोग-समस्या (Arena/LMArena):** उपयोगकर्ता Google खाते से login करता है। लंबी chat देर से खुलती है और नए उत्तर के लिए hard refresh करना पड़ता है। लक्ष्य: update लगातार आएँ, पूरा page reload न हो, और लिखा हुआ text, focus, selection तथा scroll स्थिति न बिगड़े। इसका दावा तभी होगा जब वास्तविक Android browser में, उपयोगकर्ता के अपने account session पर, उपयोगकर्ता-साक्षी परीक्षण सफल हो।

## B. अलग-अलग gates

| Gate | पास होने की शर्त | आज की स्थिति |
|---|---|---|
| G1 Exact UI parity | Chrome Stable 155.0.8059.x (phone) के matched reference screenshots के सामने हर UI region: element, label, bounds, state और transition मेल खाएँ | **BLOCKED**: Stable 155 का reference नहीं है (emulator पर Chrome 133)। Chrome 133 बनाम Chromium 155 artifact की तुलना की गई: सभी 20 साझा screens mismatch (run 38701948978, `reports/ui-compare/`) |
| G2 Exact feature parity | हर feature का व्यवहार-परीक्षण, और उसकी Google service/locale/account/OS निर्भरता दर्ज | **NOT FINISHED**: `FEATURE_PARITY.md` |
| G3 Beyond-Chrome | G1+G2 baseline बिना regression के; हर नई सुविधा का functioning implementation और same-device तुलना | **NOT STARTED** (केवल योजना, नीचे)। C1/C2 rendering-रणनीति का synthetic prototype: desktop 3×10/10, Android emulator 10/10 (Chrome 133, Chromium 155 x64)। यह shipped capability नहीं है |
| G4 Android delivery | Source provenance, reproducible build, असली install/launch, compatibility, असली device या CI evidence, signed secure updates | **PARTIAL**: official snapshot का verified fetch और emulator पर install/launch PASS; release-artifacts run 38700392608 में SHA-256 + apksigner v2 + 16 KB zipalign PASS; ARM64 translation में 5 में से 2 runs में ANR; **अपना source build (सत्र 2): arm64 APK बना और सत्यापित** (155.0.8059.80, run 38841258069, apksigner v2 + aapt2 PASS; emulator पर install + UI journey PASS, पर ARM translation में page renderer crash = FAIL environment; run 38856553471); x64 source APK चल रहा है; physical device और signed updates NOT RUN |
| G5 Arena E2E | अनुमति-प्राप्त, उपयोगकर्ता-साक्षी session: long history load, streaming/recovery, no reload, no data loss | **NOT RUN** |

## C. Chrome से आगे की capabilities: हर एक का मापनीय लक्ष्य

हर feature के लिए सामान्य मापन-नियम:
- एक ही ARM64 device, OS, refresh rate, network, cache और site data, और एक ही Chrome baseline।
- 10 cold + 10 warm trials; median और p95 दर्ज।
- server/model/network की देरी को browser rendering से अलग मापना।
- कोई सार्वभौमिक तेज़ी का दावा नहीं।

| # | Capability | समस्या / मूल कारण | मापनीय लक्ष्य | Implementation layer | सुरक्षा / privacy | Fallback | E2E परीक्षण |
|---|---|---|---|---|---|---|---|
| C1 | लंबी AI-chat rendering | हज़ारों DOM nodes से layout, paint और memory बढ़ते हैं [I]; असली कारण अभी मापा नहीं गया | Same device पर Chrome की तुलना में: पुरानी chat का first-visible-content p95 ≥20% कम, INP p95 ≤200 ms, scroll jank-frames ≥30% कम, PSS ≤ Chrome +10% | Browser Java/C++ (domain-opt-in rendering hint) + Blink settings; web page का DOM हमारे नियंत्रण में नहीं | केवल उपयोगकर्ता-opt-in domain; page script के साथ कोई डेटा साझा नहीं; reversible | per-site बंद करने का switch | Synthetic 300/3000-message fixture, फिर वास्तविक chat उपयोगकर्ता-साक्षी |
| C2 | Live-answer continuity / reconnect | stream टूटने पर site full reload माँग सकती है [U] | Network drop (airplane 10 s) के बाद reload के बिना जारी रहे; 0 duplicate sends; draft/focus/scroll सुरक्षित | Network stack observability + tab lifecycle (discard/freeze से बचाव); site का protocol हमारे नियंत्रण में नहीं | Protected endpoints को reverse-engineer/automate नहीं करना; कोई payload capture नहीं | सामान्य Chrome व्यवहार | Local SSE fixture, जिसमें `Last-Event-ID` वाले और बिना वाले दोनों मामले हों |
| C3 | लंबी chat navigation | पुराने/नए संदेश तक पहुँचना कठिन | "Jump to latest" ≤1 tap; scroll स्थिति restore का अंतर ≤4 px | Browser UI (native overlay) | कोई content इकट्ठा नहीं; केवल scroll API | Overlay छिपाना | Fixture + a11y (TalkBack) |
| C4 | Background-tab resource management | Background tabs memory/battery लेते हैं | Active form, POST, audio या streaming वाली tab कभी discard न हो; बाकी tabs पर memory 15% कम | Tab lifecycle (C++/Java) | कोई नया data नहीं | Chrome default नीति | 20-tab scenario, PSS/battery |
| C5 | Local privacy dashboard | प्रति-site storage/permission की जानकारी बिखरी हुई है | 1 screen में प्रति-site cookies, storage, permissions; delete ≤2 taps | Settings UI (Java) | पूरी तरह local; कोई telemetry नहीं | Chrome site settings | UI E2E + a11y |
| C6 | Independent profiles | Accounts के बीच cookie crossover | Profile A का cookie Profile B में 0 बार दिखे | Browser profile (C++) | Profile-स्तर पर storage isolation | Single profile | 2-profile login fixture |
| C7 | Reproducible signed updates | Provenance और rollback नहीं है | हर release का source revision, SHA-256 और signature सत्यापित; rollback ≤1 step | CI/release | Signing key repo/CI log में कभी नहीं; signing hardware/secret-store में | Manual install | CI verify-job |
| C8 | Offline draft protection | Reload पर draft खो जाता है | Reload/crash के बाद draft 100% वापस; encrypted at rest; 24 घंटे में auto-delete | Browser (Java, Android Keystore) | Sensitive fields (password/OTP) कभी store नहीं होते | बंद | Renderer-kill fixture |
| C9 | Native controls, gestures, keyboard, multi-window | — | Chrome बराबर या उससे बेहतर; 0 a11y regressions | Browser UI | — | — | Espresso/UIAutomator + TalkBack |

**Acceptance:** हर added feature के लिए ये सभी ज़रूरी हैं: Chrome baseline पास, current Chrome parity से कोई regression नहीं, security/privacy/a11y पास, data loss 0, same-device benchmark evidence। C1 और C2 का दावा केवल वास्तविक long chat के account-aware, उपयोगकर्ता-साक्षी E2E के बाद ही होगा।
