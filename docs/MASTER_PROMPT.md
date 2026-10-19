मुख्य परियोजना निर्देश: Android पर पूरा Chrome-जैसा ब्राउज़र बनाना — पुरानी परियोजना से आगे जारी रखें

इस पूरे prompt को पढ़कर उपयोगकर्ता की वास्तविक browser परियोजना को आगे जारी रखें। इसे केवल research plan, visual mockup, WebView demo, launch button, APK rename या synthetic performance experiment तक सीमित न करें। कोई उपलब्ध ZIP, source, report, tests, build scripts या APK बिना जाँच दोबारा न बनाएँ। यह निर्देश परियोजना की सत्य स्थिति और कार्यप्रणाली दोनों है।

────────────────────────────────────────────────────
१. उपयोगकर्ता की मूल माँग — इसमें scope reduction की अनुमति नहीं
────────────────────────────────────────────────────
Android के लिए एक नया स्वतंत्र ब्राउज़र बनाना है। मूल आवश्यकताएँ ये हैं:

A. Google Chrome Android की हूबहू UI और हूबहू सभी मौजूदा Chrome browser features वाला Chrome clone।
B. उसी browser में वर्तमान वास्तविक Chrome से भी आगे की, प्रमाणित नई capabilities हों। “More advanced than real Chrome” परियोजना का अलग, अनिवार्य लक्ष्य है, सिर्फ भविष्य की कल्पना नहीं।
C. Android पर वास्तविक APK build, install, launch, regression और device tests तक browser काम जारी रखना।
D. user का विशेष दर्द: Google खाते से चलने वाली Arena/LMArena AI की पुरानी लंबी chats को तेज़ खोलना; नए उत्तर hard refresh के बिना सुरक्षित ढंग से प्राप्त/दिखाना; draft, focus, selection, scroll position और संदेश न खोना; duplicate send न होना।

इस target को बदले बिना काम करें। निम्न विकल्पों को पूरा उत्पाद बताकर मूल लक्ष्य न बदलें:
- केवल Android WebView या Custom Tabs wrapper
- सिर्फ नया-टैब HTML या Chrome जैसी चित्रित UI
- सिर्फ app shortcut/Chrome launcher
- सिर्फ public Chromium APK का नया नाम/चिह्न
- सिर्फ long-chat JS demo, browser benchmark या research document

इनमें से कोई component स्वतंत्र रूप से सहायक हो सकता है, पर उसे पूरा browser अथवा मूल requirements का समाधान न बताएँ। जो source-build, Google feature या hardware gate उपलब्ध संसाधनों के कारण पूरा नहीं हुआ, उसे “बाकी/blocked” कहें—“लगभग बराबर” कहकर requirement हटाएँ नहीं।

────────────────────────────────────────────────────
२. भाषा, ईमानदारी और product/safety नीति
────────────────────────────────────────────────────
- उपयोगकर्ता से हिंदी (देवनागरी लिपि) में संवाद करें; रोमन हिंदी/Hinglish न लिखें। केवल तकनीकी nouns, APIs और code अपने मूल spelling में रहने दें।
- deeply research पहले करें; उसके बाद design, फिर code, फिर test। हर claim के साथ official source या test evidence दें। “100% confirmed”, “विश्व का सबसे तेज़”, “exactly identical”, “all features ready”, “E2E passed” जैसे कथन तभी जब संबंधित प्रत्यक्ष acceptance tests मौजूद हों।
- तथ्य, निरीक्षण, user-provided info, अनुमान, unknown और failed test स्पष्ट अलग करें। अधूरा workflow, speculative capability, official source code से उठाया APK या synthetic demo सफल उत्पाद-परीक्षण का प्रमाण नहीं है।
- कोई वास्तविक Chrome feature हटाने, desktop screenshots को Android native UI मानने, Google access restrictions bypass करने या user के account credentials लेने की अनुमति नहीं है।
- Google/OAuth, TLS, sandbox, same-origin, Safe Browsing, Android permissions, download/file access को गति के लिए बंद न करें। CAPTCHA, private endpoint, API quota, browser user-agent/OAuth policy और anti-bot bypass न करें।
- user ने Chrome जैसा browser माँगा है; project को Google का official app होने का false claim नहीं करना चाहिए। Native Chrome UI appearance, Google wordmarks/logos/Chrome branding तथा proprietary Chrome components के licensing/trademark/distribution जोखिम को शोधें और अलग बताएँ। इससे “exact UI” gate को चुपचाप न हटाएँ; legal/product blocker स्पष्ट करें।
- कोई server/hosting user को अनावश्यक नहीं चाहिए। Default browser local और serverless हो; browsing user के selected sites से सामान्य HTTPS पर हो। Optional server, analytics, sync, cloud AI, paid API, remote profile या paid runner केवल clear requirement, privacy/cost disclosure और user की अलग मंजूरी पर।
- कोई user credential, PAT, Google password, OTP, browser cookie/session, production signing key, chat text या URL में embedded private token code, artifact, log, screenshot, test report, git history या conversation में न लिखें।

────────────────────────────────────────────────────
३. महत्वपूर्ण security incident: GitHub token
────────────────────────────────────────────────────
पिछली बातचीत में उपयोगकर्ता ने GitHub personal access token सीधे चैट में paste किया। उस token का मान यहाँ जानबूझकर शामिल नहीं है। उसे compromised मानें।
- वह token कहीं भी फिर से लिखें/पढ़ें/निकालें/फ़ाइल में रखें/execute करें/remote authorization में उपयोग करें—ऐसा न करें।
- user बाद में “full access है, token use करो” कहे तो भी मना करें। उससे कोई Github access verified नहीं है।
- उपयोगकर्ता को GitHub Settings → Developer settings → Personal access tokens में जाकर पुराना token तत्काल revoke करने को कहें; नया token कभी chat में paste न करवाएँ।
- सुरक्षित विकल्प: repo का public URL; workflow user स्वयं trigger करे; या read-only official GitHub connector यदि वास्तविक tool inspection में available और user OAuth ने connect किया हो।
- पिछली दो GitHub connector जाँचों का परिणाम `unsupported` था। नया turn आने पर connector फिर जाँचें; कोई connector की उपलब्धता अनुमान से न कहें।
- किसी भी paid runner/cloud resource को लागत और सीमा बताए बिना तथा अलग explicit approval के बिना शुरू न करें।

────────────────────────────────────────────────────
४. Workspace और पहले से उपलब्ध सामग्री — फिर से खोज/निर्माण न दोहराएँ
────────────────────────────────────────────────────
पहले मौजूदा workspace को inspect करें (`ls`, main README, feature matrices, verification report, ZIP contents, hashes)। Workspace `/home/user` है।

मुख्य स्रोत:
- `/home/user/android-browser/`
- `/home/user/android-browser/README.md` — परियोजना स्थिति और history
- `/home/user/android-browser/TESTING.md` — previous synthetic tests और स्पष्ट सीमाएँ
- `/home/user/android-browser/native-app/README.md` — existing Android APK
- `/home/user/android-browser/native-app/REQUIREMENTS.md` — unmet requirements
- `/home/user/android-browser/native-app/FEATURE_PARITY.md` — Chrome parity inventory
- `/home/user/android-browser/native-app/SCOPE_AND_ADVANCED_CAPABILITIES.md` — original scope, beyond-Chrome targets, metric gates
- `/home/user/android-browser/native-app/runtime-test-status.json` — attempted emulator result
- `/home/user/android-browser/native-app/rebuild-report.json` / `upstream-lock.json` / `signature-verification.txt` / `apk-badging.txt` / `distribution.json`
- `scripts/fetch_native_snapshot.py`, `scripts/rebuild_native_apk.py`, `scripts/build_native_preview.sh`, `scripts/native_android_smoke.py`
- `.github/workflows/native-android-preview.yml` — existing hand-triggered real emulator smoke workflow; not remotely run
- `.github/workflows/chromium-baseline.yml` — preliminary full-source/self-hosted reference build workflow; not proven/triggered
- `experiments/chat-rendering-helper.js` and synthetic Playwright fixture/spec — standalone experimental rendering code only; NOT integrated into the native APK
- `/home/user/PROJECT_RULES.md`
- `/home/user/अगली-चैट-हैंडऑफ़.txt`
- `/home/user/Chrome-clone-deep-research-and-UI-prompt.txt` — deep UI research handover; start from it, but this build prompt additionally directs actual implementation.

Previously presented download files:
- `/home/user/Chrome-Clone-Android-Preview.tar.xz` — ~96.4 MB compressed archive containing ~387 MB native ARM64 Chromium preview APK.
- `/home/user/Android-browser-source-and-tests.zip` — compact source + tests package (previous snapshot: ~45 files, ~64 KiB; check if later source updates exist before relying on count/hash).

Before rebuilding/checking final ZIP, ensure source package includes all new reports/matrices, no APK/key/token, correct hashes; regenerate only if files truly changed. Preserve historical test-failure evidence. Do not download/build Chromium again without a qualified machine and reason.

────────────────────────────────────────────────────
५. वास्तविक पिछला implementation/उसका प्रमाण/उसकी सीमा
────────────────────────────────────────────────────
मौजूदा APK की सत्य स्थिति:
- Google’s public `chromium-browser-snapshots` से Android_ARM64/Google Chromium `ChromePublic.apk` bounded HTTP ranges से लिया; CRC32, upstream revision, source VERSION match जाँचा।
- Snapshot revision `1718469`, source commit `977a84f721d5aa6954a3e84c72ca54a90f2d0448`, Chromium version `158.0.8105.0`। यह rolling development Chromium build है, Google Chrome Stable नहीं। Stable को नई चैट में official source से दोबारा verify करें।
- Binary `AndroidManifest.xml` में user-facing label `Chrome Clone · Preview` किया, package name `org.chromium.chrome` रखा। मूल DEX, native engine libraries, `resources.arsc` के hashes unchanged verify हुए।
- 16 KiB native alignment और APK test signature verify हुए; `minSdk 29`, ARM64 ABI मिला। APK signed archive में उपलब्ध।
- Test key ephemeral `.cache` path में थी; source archive में नहीं। यह production signature, release process, secure update channel या maintainable original source build नहीं।
- यह Chromium native app payload है; HTML mockup या WebView wrapper नहीं। लेकिन underlying Chrome browser Java/C++ UI source में कोई browser upgrade/नई feature change compile करके integrate नहीं की गई।
- केवल launcher/app label बदलना “Chrome clone complete” या “more advanced than Chrome” नहीं है।
- User-visible launch/install was NOT tested; emulator boot fail हुआ।

पिछले tests:
- Synthetic Playwright: 300 स्थानीय mock chat messages, mobile-like viewport 393x851, Chrome for Testing desktop Linux. 10 artificial rendering cases × 3 = 30 pass, 0 failed/skipped/flaky. Four synthetic messages 1 sec apart, page not navigated/reloaded, draft/focus/scroll preserved in mock fixture. Separate JS experiment; real Arena messages, Android, APK integration or server streaming नहीं।
- प्रारंभिक failures मिले: गलत full-box height से page ~9647 px लंबी हुई, scroll 139 px shift; फिर CSSOM fractional value normalization से restore styles mismatch। सुधार के बाद 30 synthetic checks pass। Failure reports बनाए रखें।
- Python host/manifest tooling कुल 10 tests pass; tool integrity checks only।
- Emulator installed: SDK image Android 11 Google APIs x86_64; emulator 37.2.12. `/dev/kvm` न होने और effective host RAM ~2.08 GB होने पर emulator 2048 MB allocate करके `Insufficient RAM free for launching emulator`, exit 1। APK install/launch नहीं हुआ।
- Last host inventory: ~2.08 GB effective RAM, ~21.56 GB free disk, 2 CPUs, no `/dev/kvm`; GitHub connector unsupported; neither account repo permission nor credentials verified. Workspace restore can remove `.cache`/SDK binaries—हर नई बातचीत में exact tools पुनः detect करें।

────────────────────────────────────────────────────
६. architecture decision और Chromium source-build बाधा
────────────────────────────────────────────────────
इस user के Google sign-in/Arena लक्ष्य के कारण मुख्य product कोई plain WebView/Custom Tab नहीं है। User को स्वतंत्र Chrome-like native browser चाहिए:

- Preferred legitimate path: open Chromium Android browser source/fork (native Java UI + C++ engine) में अपना branded downstream browser बनाना, maintain, build और secure update देना।
- Existing snapshot APK is useful smoke/reference artifact, not complete custom source build. Deep UI/features/custom advanced functions integration needs source and successful reproducible Android build.
- Official Chromium Android source docs state Linux x86-64, min 8 GB RAM and 100 GB free disk; >16 GB RAM recommended. These refer to build host, not phone. Earlier local workspace cannot do full build; preflight correctly refused and did NOT download full source.
- Public Actions std runner/storage must be freshly checked: snapshot/native APK runtime CI is smaller job; complete Chromium source build may exceed standard disk. Paid larger runners need prior explicit spending consent. Self-hosted runner jobs only on trusted branches/manual dispatch; no untrusted PR secrets.
- Chromium derivative Google private APIs/Chrome Sync may not be available; Google OAuth private browser login API restrictions apply. A webpage’s “Sign in with Google” via full browser is separate from Chromium browser-level account Sync. Never promise Google private APIs from a public Chromium snapshot.
- Code/UI/product trademarks/privacy/OSS source licenses retain appropriate notices. Do not remove upstream Chrome credits/licenses.

────────────────────────────────────────────────────
७. तत्काल गहन research: वास्तविक Chrome Android UI का census और design system
────────────────────────────────────────────────────
काम शुरू करते समय current date system से लें। Official sources/web research refresh करें; पुराना `155 Stable` / current `158 snapshot` data स्वतः current न मानें। हर conclusion के साथ exact source/version/check date दें। Prior research facts accurate represent करें:
- Public Chromium project is open foundation behind Chrome; not equal to proprietary product.
- WebView and Custom Tabs sharing/session/privacy and UI-control differences
- Google OAuth disallows embedded Android WebView auth; external browser/Custom Tab policy
- derived Chromium APIs/Chrome Sync restricted; no secret workaround
- Android native browser source-build size/resource requirement
- offscreen render deferral via `content-visibility` is theoretical/advisory until actual website/device benchmark; not server/live update solution.

Research oficial Android Chrome app from primary-source/user-owned/allowed evidence; not merely the webpage content and not Google Chrome desktop. Establish the comparison baseline:
- exact latest Google Chrome Stable Android version/build, Android OS, actual device dimensions + density/refresh, language, display scale, theme, navigation mode, font scaling, Play Services sign-in condition and accessible screenshot provenance
- UI layers: system status/navigation bars versus Chrome browser shell versus website DOM. Keep them separate.
- no direct real phone/screenshot available? Don’t hallucinate screen appearance. Mark `not observed`, then ask user for sanitized non-private screenshot or a manual test on their Android phone. Consider official Chrome screenshots/docs as secondary evidence but don’t call them pixel-equivalent user-device capture.
- check Google/Chrome brand/trademark/app impersonation/licensing risks and explain user-facing difference. Preserve exact UI as acceptance gate; do not silently remove brand or exactness. If legal permission needed, explain as blocking issue.

Create `research/CHROME_UI_INVENTORY.md` or update `native-app/FEATURE_PARITY.md` with, for EACH component, reference screenshot ID/Chrome build/device condition/user state/accessibility label/control bounds/gesture transitions/keyboard behaviour/focus/animation/expected result/current APK result/evidence/delta/test. At minimum inventory:
1. first-run welcome, legal consent, default browser choice, browser sign in
2. startup/new tab/home page; search/omnibox/address bar; auto suggestions/dropdown, voice/search/clear/copy/paste
3. back, forward, stop, reload, secure site-info, permissions, share, translate, bookmark, page search, zoom, desktop site
4. tab strip/switcher, new/close/restore, normal/incognito, groups, reorder, multiwindow, overflow, animations and counts
5. native menu, settings and each submenu; history, downloads, bookmarks, password manager/autofill, privacy/safety
6. per-site permission screens; camera/mic/location; file picker, download progress/resume, pdf/printing/share, audio/video/fullscreen/WebRTC
7. web app/PWA install/shortcuts, Android intents/app links/Custom Tabs, accessibility actions, background/relaunch, crash/process death, storage failure/offline retry
8. light/dark/night/font scale/landscape/small screen/tablet/foldable/keyboard/IME/TalkBack/high contrast/navigation gestures/status-bar/cutout/edge-to-edge.

For each UI, compare exact **native Android Chrome shell** with the current preview; webpage `arena.ai`’s own new-chat screen must not be described as the Chrome toolbar. Store screenshots without private user content or account identifiers. Matched pixel diffs require same device/rendering settings; list known anti-alias, font, WebContents dynamic content effects.

────────────────────────────────────────────────────
८. पूर्ण Chrome feature-parity catalogue — कोई feature चुपचाप न हटे
────────────────────────────────────────────────────
Use current official Chrome Android product help/release docs + Chromium source/tests to enumerate all user-facing browser features. For every row: official source; source module/revision; Google-service dependency; current APK actual status; implementation file; test ID; device test evidence; acceptance pass/fail/blocked. Include at least:
- browser surface and native navigation controls, URL handling, Android share/intent integration
- new-tab/home, search, omnibox suggestions/input, incognito, downloads, history/restore, bookmarks
- tab switcher/group/restore/back-stack; rotation/process-death behavior
- mobile/desktop websites, page zoom/find, accessibility, translation if authorized, full screen, media/camera/WebRTC/file input
- Google website OAuth login, Chrome browser account sign-in, Google Sync, Google Password Manager separately; Safe Browsing, translation, feeds, location, spell checks, cloud/sync separately by account/region/policy.
- site security/permissions, camera/microphone/location, ads/content blockers if browser normally supports, TLS/cert errors, downloads, cookies/site data
- toolbar/settings/offline, installed webapps/PWAs, payment/web APIs, external intents, password save/autofill, accessibility/TalkBack, locale
- Chrome Android extension support/current state if relevant (research official current support before promising it; don’t invent).
- automatic browser/security update, stable channel/provenance, signature/rollback, crash reporting only with explicit privacy policy.

Testing an upstream code class exists is NOT proof it works in independent browser; service API may be private. Distinguish native Chromium implemented, Google-owned service available through supported API, unsupported/blocked, not tested, regression.

────────────────────────────────────────────────────
९. “वास्तविक Chrome से अधिक advanced” को concrete engineering target बनाना
────────────────────────────────────────────────────
Do NOT remove this requirement. After measuring current Chrome baseline, implement actual additive capabilities within source. Verify no vanilla feature regression. Research implementation layer/control restrictions first. Candidate capabilities below must be actively evaluated, selected and implemented, not only kept in a plan:

A. AI long-conversation rendering mode: dynamic/opt-in, reversible, only safely detected offscreen transcript messages; preserve exact text/DOM visibility, scroll/find/copy/accessibility/selection/forms/media/current generation. Test 10k+ synthetic fixture + actual allowed Arena chat. A website adapter has domain/selector allow-list, version check, no cross-origin privilege, safe no-op on DOM change, explicit status and off switch.
B. Live answer continuity: use website’s legally-supported transport and real sequence IDs/replay/stream; no full-page refresh, no repeated message POST, dedupe/reorder/update only appended data. Study actual connection type first. If browser does not own page code, do not claim browser can recreate a missing provider response. Avoid private API, anti-bot bypass, fixed polling spam. Keep user draft/input and generation state.
C. Long thread navigation controls: resume latest response, jump to prior matched message/time/search, scroll anchors; accessible to screen reader/touch/keyboard.
D. Tab resource management: suspend only inactive pages with safe form/audio/post protections; user-controlled exclude; reliable restore, no loss of active chat streams.
E. Privacy controls: understandable site permission/storage/cookie/autofill dashboard; local data retention/delete/export; no hidden telemetry or chat upload.
F. Multi-profile/session isolation: only if Chromium source architecture allows robust per-profile cookies/local data/permissions separation; tests for zero cookie/storage/session leakage.
G. Advanced security/update: provenance, rapid patched Chromium updates, signed artifacts and rollback, untrusted download warnings, per-site TLS settings; no nonstandard insecure flags.
H. Optional AI features: never send chat to third party without per-user consent/data retention explanation/cost disclosure; local AI on Android requires memory/performance research, cannot assume.

For each proposed new feature prove (1) user value (2) current Chrome limitation baseline (3) source control surface (4) implementation (5) threat/privacy model (6) unit + Android instrumentation/UI tests (7) device comparison against Chrome (8) measurable new capability without loss. Build an implementation backlog weighted by delivery and mark unimplemented features truthfully.

────────────────────────────────────────────────────
१०. Arena long chat issue: protocol study and true E2E test sequence
────────────────────────────────────────────────────
The prior session only navigated to a public landing page that redirected from `lmarena.ai` to `arena.ai`; no account/private chat was opened. Do not claim bug reproduced or fixed.

Authorized/user-observed protocol:
- Ask only for account-safe, reproducible instructions and public/clean test conversation. User should personally sign in on their own phone/device; do NOT ask user to send password/OTP/cookie/token.
- Capture anonymized Network/Performance/Memory observations with URL query tokens, personal IDs, chat body, cookies, headers and authorization redacted. Do not upload raw HAR/trace without user review.
- Reproduce cold long history open; warm reopen; scroll old content; ongoing new model answer; background/foreground; weak/brief network outage; reconnect; screen rotation/app kill; no page hard refresh; draft and selection remain; exactly one send; no duplicate/lost/out-of-order stream events.
- Instrument and differentiate network/server TTFB/model generation vs stream/events/JS tasks/DOM/Markdown code blocks/images/layout/paint/compositing/Android memory/process. Provider server/model latency cannot be attributed to browser.
- Diagnose if Arena’s frontend already virtualizes/streams chat; optimize only the root cause. Avoid brittle DOM selectors and injections without measured native/browser control; ensure selectors are explicit/versioned and opt-in safe no-op.
- E2E proof requires Android user-visible Chrome-like native browser actual APK on supported Android device with user witnessing Google login and Arena chat. Synthetic desktop JS test is only a unit/component check.

────────────────────────────────────────────────────
११. Research sources and citation discipline
────────────────────────────────────────────────────
Before each major design/build pass, verify latest current official sources; prior useful references:
- Chromium project: https://www.chromium.org/chromium-projects/
- Android Chromium build instructions: https://chromium.googlesource.com/chromium/src/+/main/docs/android_build_instructions.md
- Chromium derived API keys/private Google restrictions: https://www.chromium.org/developers/how-tos/api-keys/
- Official Android OAuth/embedded WebView policy: https://developers.googleblog.com/upcoming-security-changes-to-googles-oauth-20-authorization-endpoint-in-embedded-webviews/
- Android WebView/Custom Tabs comparison: https://developer.android.com/develop/ui/views/layout/webapps/in-app-browsing-embedded-web
- Official Chrome Custom Tabs: https://developer.chrome.com/docs/android/custom-tabs/
- long content rendering: https://web.dev/articles/content-visibility and https://web.dev/articles/optimize-inp
- SSE protocol: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
- official Android emulator archived/releases/docs: https://developer.android.com/studio/emulator_archive and https://developer.android.com/studio/run/emulator
- official GitHub runners: https://docs.github.com/en/actions/reference/runners/github-hosted-runners

Use first-party, dated primary docs/code/screens. Forums and search snippets can suggest leads but do not establish high-risk policy/API claims. Record source title, URL, checked date/version, exact supported claim, limitation, whether reproduced by actual testing. Research current Chrome stable in the next session; do not cite historical version as if it were latest. Respect public-source licenses and carry upstream NOTICE/CREDITS.

────────────────────────────────────────────────────
१२. Existing test evidence: carry forward exactly; don’t overstate
────────────────────────────────────────────────────
Historical finished checks:
- 10 desktop synthetic local-render scenarios × 3 repeats = 30 pass, 0 fail/skipped/flaky, Playwright/Chrome for Testing desktop Linux, mobile-like viewport, 300 mock messages. Four updates at one-second intervals come from a fixture JS method, not Arena/SSE/network. No full page navigation in the fixture. These scripts are NOT integrated into Android APK.
- Two earlier failures were caught and fixed: page height ~9647 px from wrong height measurement and scroll shift 139 px; later style restoration failed due to fractional CSS style normalization. Repeated suite passed afterward. Keep failed-run evidence.
- 10 Python tests pass for resource-guard checks + custom binary Android manifest string-pool/label patch logic; static/format checks only.
- Native APK archive CRC/version, changed app label, DEX/engine/resource hashes, 16KB alignment and test signature checked. This verifies build artifact integrity, not actual install or browser function.
- Workflows syntax/reference hashes checked locally; no remote GitHub action executed.
- Android emulator tried, failed before boot due insufficient RAM; no APK installed/launched on emulator or phone.
- Google OAuth, Chrome Sync/private APIs, private Arena conversation, actual long-chat improvement, current Chrome screenshots/parity, battery/memory/speed comparison all NOT TESTED.

Do not repeat a successful test unless source/device changed; do run new Android tests when a real Android device/runnable CI is available. State each test layer distinctly: static/pure unit/browser synthetic/native packaging/emulator smoke/physical device/user-account E2E/performance comparison.

────────────────────────────────────────────────────
१३. Environment and next external action
────────────────────────────────────────────────────
Last local environment: Linux x86_64, 2 CPUs, effective memory ~2.08 GB, free disk ~21.56 GB, no `/dev/kvm`; local full source build guard refuses before checkout/download. Emulator SDK/cache may be transiently restored or gone; verify with `which adb`, `which emulator`, `/dev/kvm`, memory/disk.

Need a prepared high-memory build/test host before full source build: official Chromium docs minimum 8GB RAM/100GB disk; >16GB RAM better. Runner needs actual viable disk, KVM/Android emulator, correct API/system image and time; be honest if host cannot meet it. No pay-as-you-go resources without separate user approval.

Last task was the user asks “give me maximum-depth prompt for the Chrome browser we were making.” This master prompt is to continue actual engineering—not respond only with another handover or plan. Next safe step is inspect existing workspace, perform refreshed official browser/UI research, prepare auditable inventory, and ask user only for the specific missing Chrome phone/device/screenshot or safe public repository link/runner input needed. Don’t ask for another PAT.

────────────────────────────────────────────────────
१४. Required repo files and build/test deliverables to produce/maintain
────────────────────────────────────────────────────
Retain/update files in `/home/user/android-browser/`:
- `research/RESEARCH_REPORT.md` with current dated official research and claims vs limits.
- `research/CHROME_UI_INVENTORY.md` with real Chrome native Android UI screenshots/specific states/source evidence and baseline vs artifact comparison; never invent screenshots.
- `native-app/FEATURE_PARITY.md` per feature: source, current status, implementation path, test, evidence/pass/blocked.
- `native-app/SCOPE_AND_ADVANCED_CAPABILITIES.md` fixed original requirements and implemented beyond-Chrome features + metrics.
- `native-app/REQUIREMENTS.md` gates and reasons not met.
- `TESTING.md`, `reports/verification-summary.json`, native UI instrumentation test results/screenshots with private content redacted, checksums.
- source manifest/ZIP updated after changes and secret scanning; do not include APK/JKS/password/PAT in source ZIP.
- actual source-built signed test APK (only after build resources verified), stable build provenance, package/signature/ABI/permissions/license notices; actual runtime device evidence.

If target real UI screenshots not available, mark UI inventory “awaiting real user device/reference” and request user to supply sanitised screenshots or perform screenshot verification. Do not fill with a fabricated Chrome UI.

────────────────────────────────────────────────────
१५. Completion criteria: मूल लक्ष्य तभी DONE होगा जब all pass
────────────────────────────────────────────────────
Do NOT tell user “Chrome clone complete” until there is evidence for all:
1) Current Chrome Android stable reference version + same device screenshot/interaction state inventory and original UI parity verified.
2) All enumerated current Chrome Android browser features have an acceptance and pass on actual app/target Android versions; explicitly report private restricted APIs as blocker if cannot implement legitimately; never claim all features while hidden rows remain.
3) A genuinely modified, branded/source-maintained native Chromium browser is source-built and reproducible; not merely one upstream dev APK label changed.
4) Each above-Chrome feature is integrated, secure, measured and passes native tests without regression; concrete metric evidence vs current Chrome.
5) APK signature and safe update/key rotation/security patch policy are ready; no test key in production.
6) Android emulator CI native tests and at least one physical ARM64 Android smoke/E2E completed; performance tests same device/network against installed current Chrome.
7) User himself validates Google login/long Arena conversation when necessary; actual chat/private content stays with user.
8) Report all final unresolved Google APIs, OAuth behavior, brand/licensing, supported Android/API matrix and product backend limits. If a provider service cannot be cloned legitimately, do not counterfeit the service; state that gate is blocked rather than changing scope.

Required final table: requirement | changes actually made | source/build provenance | test type | exact evidence/artifact | pass/fail/blocked/not tested | remaining blockers. Clearly distinguish current archive from a complete product.

────────────────────────────────────────────────────
१६. अगली बातचीत की पहली प्रतिक्रिया
────────────────────────────────────────────────────
User से हिंदी में कहें: “मौजूदा Android Chromium-native preview, source, reports और browser-project files को पहले पढ़ूँगा; कोई पुराना build/test बिना कारण दोबारा नहीं करूँगा। Chrome की हूबहू UI/features और उससे आगे की क्षमताएँ—पूरा मूल scope—बरकरार हैं। पिछली chat में उजागर हुआ GitHub token इस्तेमाल नहीं किया जाएगा; उसे revoke करें। अब पहले वास्तविक Chrome UI reference और build/test संसाधन का exact अगला gate सत्यापित करता हूँ।” फिर वास्तविक काम शुरू करें।
