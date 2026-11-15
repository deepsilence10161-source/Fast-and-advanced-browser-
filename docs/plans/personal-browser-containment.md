# व्यक्तिगत Android browser: डेटा रहे, browser के बाहर स्वतः न पहुँचे

**प्रभावी तिथि:** 19 अक्तूबर 2026। **स्थिति:** requirements/source audit, static preflight और अलग **opt-in native source layer** तैयार; नया privacy APK या actual-device acceptance नहीं। प्रथम चरण का इतिहास सुरक्षित है; आगे का implementation/test evidence §8 में है।

## उपयोगकर्ता का निर्णायक सुधार

- Android app चाहिए।
- **डेटा delete नहीं करना है।** Browser के अपने login/site data को रखकर, उसका Android accounts/दूसरे apps/shared storage में स्वतः पहुँचना रोकना है।
- **Privacy पहले, AI बाद में।** इस चरण में Gemini जोड़ने के लिए privacy policy में अपवाद नहीं बनाए जाएँगे।

पहला ephemeral/incognito/session-wipe प्रस्ताव इस सुधार के बाद लागू नहीं है। कोई app-exit/background/lock auto-wipe, `pm clear`, profile deletion या account migration इस कार्य में नहीं किया गया। मौजूदा `com.swiftra.app` का डेटा/व्यवहार बदला नहीं गया। अलग personal variant सुरक्षित दिशा है; अंतिम package ID, migration और distribution अभी तय/लागू नहीं हैं। मूल सामान्य Swiftra/Chrome-parity scope अलग बना रहेगा।

## 1. “Browser के भीतर” की वास्तविक सीमा

App का internal private storage भी भौतिक रूप से device पर होता है। लक्ष्य **ऐप के sandbox में durable data, नियंत्रित IPC और कोई अनचाहा export/account-link/backup नहीं** है। Android प्रति-app UID और sandbox देता है; यह rooted/compromised OS, privileged services या सभी vulnerabilities के विरुद्ध पूर्ण गारंटी नहीं है।

चार अलग परतें:

1. **Browser-private local data:** cookies, site storage, history, bookmarks, tabs/drafts जहाँ support हो; app restart के बाद भी रहेंगे। Website expiry/logout/`Clear-Site-Data`, quota eviction, uninstall, OS “clear storage”, key loss और device failure को browser हमेशा रोक नहीं सकता। कोई false “हमेशा login रहेगा” दावा नहीं।
2. **Android/other apps:** OS accounts, system password/autofill providers, clipboard, shared Downloads/MediaStore, exported providers, external intents, screenshots/recents, backups—इन्हें अलग controls और acceptance चाहिए।
3. **वेबसाइट/इंटरनेट:** user द्वारा खोली गई website को आवश्यक requests/data/IP जाते हैं। Local containment, zero-network या website से anonymity नहीं है। Safe Browsing/TLS/sandbox को कमजोर नहीं किया जाएगा।
4. **विश्वसनीय platform boundary:** Android Keystore, OS rendering/input और keyboard जैसे services होते हैं। System keyboard input देख सकता है; no-learning hint, keyboard को अनिवार्य रूप से offline नहीं बनाती। Root/OS compromise, बाहरी camera और malicious accessibility के विरुद्ध absolute claim नहीं।

**Google website login ≠ Chrome profile sign-in ≠ Android system account.** Website account को browser cookies में रखना और Android में account जोड़ना अलग workflows हैं। केवल Gmail signup को system account creation मान लेना सही diagnosis नहीं; actual user flow अलग जाँचा जाएगा।

## 2. Personal-variant लक्ष्य-नीति — आंशिक source implementation, Android पर अप्रमाणित

| क्षेत्र | अपेक्षित व्यवहार | स्पष्ट सीमा / trade-off |
|---|---|---|
| Persistent profile | सामान्य durable site profile; app restart पर cookies/site data उपलब्ध | Incognito को persistent vault का नाम नहीं देना; कोई automatic wipe नहीं |
| Android accounts | existing phone accounts enumerate/import न हों; Add Account intent/API बंद; Chrome sign-in/Sync नहीं | कुछ native/federated broker flows काम नहीं करेंगे; जहाँ वैध हो web login fallback |
| Passwords | app-owned local vault, fresh user authentication, Keystore-wrapped key | 0022 local vault अभी unimplemented; Google Password Manager को local storage न कहें |
| System autofill / passkeys | external autofill/credential-provider integration default बंद | System-provider-dependent passkeys/sign-in के compatibility blockers स्पष्ट रखने होंगे |
| Local storage | browser data app-internal storage में; private downloads भी shared storage से अलग | केवल permission हटाना पर्याप्त नहीं—actual paths, native writers और grants जाँचना आवश्यक |
| Backup / migration | cloud backup, D2D और supported cross-platform transfer से opt-out; custom BackupAgent नहीं | `allowBackup=false` अकेला सभी OEM cases का proof नहीं; rules और real restore/migration tests चाहिए |
| Data encryption | existing cookie encryption बनाए रखें; full profile/cache/LevelDB/SQLite/WAL की अलग design | 0021 cookies/OSCrypt का प्रमाण पूरे browser profile की encryption नहीं है |
| Key failure | पुराने data को preserve करके error; silent fallback/empty-vault/wipe नहीं | नई private writes में public fixed-key fallback स्वीकार नहीं करना; runtime work अभी बाकी |
| External apps / intents | स्वतः बाहर launch, account broker, external browser, Share/Print/Cast बंद | User-approved exceptions अभी अधिकृत नहीं; website functionality प्रभावित हो सकती है |
| Clipboard / providers | sensitive data की automatic clipboard copy नहीं; URI grants/exports बंद | app-private provider भी URI grant मिलने पर बाहर data दे सकता है |
| Screen / recents | secure window/recents protection, notifications में page/account/content नहीं | यह OS/root/बाहरी camera के विरुद्ध पूर्ण protection नहीं |
| Keyboard | normal persistent tabs में भी no-personalized-learning request; system autofill paths की जाँच | third-party keyboard का व्यवहार browser enforce नहीं कर सकता |
| Network / telemetry | browser-origin background requests का audit, unrelated telemetry/sync नहीं | user-requested websites, approved security/update traffic अलग वर्ग; packet-capture proof बाकी |
| AI | इस privacy phase में deferred | भविष्य में cloud data-sharing पर explicit consent; consumer Gemini fork entitlement assume नहीं |

Browser के भीतर download खोलने के लिए internal viewer/streaming और private content handling चाहिए। केवल public DownloadManager directory को छिपाना containment नहीं। Installer/update का अलग audited, user-approved artifact path आवश्यक हो सकता है; profile या arbitrary files को export करने का सामान्य छेद नहीं बनाना है।

## 3. पहले से मौजूद code का सत्यापन

Pinned public reference: **Chromium 155.0.8059.80**, source provenance `evidence/personal-container-research-2026-10-19.json` में। यह current-latest Chrome होने का दावा नहीं है।

| Source observation | सही निष्कर्ष |
|---|---|
| AndroidManifest में `backup_key` होने पर allowBackup=true + ChromeBackupAgent; else allowBackup=false | template conditional है। Existing Swiftra static APK audit allowBackup=false माँगता है। Backup पहले से disabled होने का रास्ता नया fix नहीं कहलाएगा; merged APK/rules की अलग जाँच आवश्यक |
| manifest में GET_ACCOUNTS/MANAGE_ACCOUNTS/USE_CREDENTIALS, storage और credential-candidate permissions | platform integration surfaces मौजूद हैं; declarations से actual user data exfiltration सिद्ध नहीं होता, न permissions हटाने से सभी account APIs बन्द हो जाती हैं |
| `AccountManagerFacadeImpl.createAddAccountIntent()` delegate को call करता है; comment device account जोड़ने का intent कहता है | website cookies से अलग native Add Account bridge का source-backed intervention point; इसे runtime-verified automatic linkage न कहा जाए |
| `ChromeFileProvider`/`DownloadFileProvider` exported=false लेकिन grantUriPermissions=true | non-exported अकेला “कभी बाहर share नहीं” का प्रमाण नहीं |
| `ImeAdapterImpl` में normal tab के लिए learning allowed; incognito में NO_PERSONALIZED_LEARNING | retained normal profile की privacy को incognito flag पर निर्भर छोड़ना पर्याप्त नहीं; editor/omnibox/other input paths भी audit करने होंगे |
| ExternalNavigationHandler में बाहरी intents/Play Store/WebAPK paths | सिर्फ browser sign-in toggle बदलना complete containment नहीं |
| existing 0021 Keystore provider | cookies पर historical runtime evidence है; पूरे profile की encryption अथवा key-failure fail-closed policy का प्रमाण नहीं। Existing v10 fallback को private-variant acceptance नहीं मानना |

प्रथम अनुमानित `chrome/android/java/src/.../ChromeActivity.java` path **404** आया; उसे source proof नहीं माना। अगली source pass में pinned `chrome/android/chrome_java_sources.gni` और directory listing ने वास्तविक `chrome/android/java/src/org/chromium/chrome/browser/app/ChromeActivity.java` path resolve किया। `ChromeBaseAppCompatActivity.java` का सही पुराना-root path भी fetched/reviewed है। यह path discovery है—window/recents protection अभी लागू या runtime-tested नहीं।

## 4. इस चरण में वास्तव में क्या बनाया गया

### Strict static decoded-manifest preflight

`tools/security/personal_container_manifest.py` और `tests/test_personal_container_manifest.py`। यह developer audit utility है—browser feature या नया APK नहीं। Existing build/patch series/publisher नहीं बदले।

जाँच:

- अपेक्षित package, no shared UID, non-debuggable/non-test-only और shell profiling बन्द।
- explicit allowBackup=false, no BackupAgent, restoreAnyVersion disabled।
- legacy backup off या whole-domain exclusions।
- cloud, D2D और documented iOS transfer modes के लिए सभी नौ storage domains पर whole-domain excludes; encryption-conditional backup को “backup off” नहीं मानता।
- qualified `xml-*` resource overrides भी जाँचना; missing/unresolved resources और unknown modes fail।
- platform accounts/system credential/shared-storage permission declarations reject; unresolved/missing permission names भी fail।
- providers की exports और URI-grant declarations बन्द।
- malformed XML, DTD/entity और resource-directory escape reject।

उदाहरण—केवल वास्तविक merged/decoded build inputs मिलने पर:

```sh
python3 tools/security/personal_container_manifest.py \
  --manifest MERGED_DECODED_AndroidManifest.xml \
  --resources DECODED_RES_DIRECTORY \
  --expected-package REVIEWED_PERSONAL_PACKAGE_ID
```

`--expected-package` placeholder को वास्तविक reviewed package से बदलना होगा। Tool APK decoder नहीं है, signature/binary binding नहीं करता। XML input पर PASS मिलने पर भी output में **product_containment = NOT RUN / NOT CERTIFIED** हमेशा रहता है। अभी इसे publisher का पूर्ण privacy gate नहीं बनाया गया है।

यह policy साधारण Chrome compatibility से अधिक सख़्त है। भविष्य में supported platform modes/API behavior बदलें तो source/policy/test review आवश्यक होगा; silent broadening नहीं। Android SDK/OEM द्वारा इन rules के वास्तविक enforcement का परीक्षण बाकी है।

## 5. Native acceptance — किसी unit test से प्रतिस्थापित नहीं

सभी वास्तविक tests assistant-run **x64 Actions emulator + native ARM64 Redroid**, और फिर अलग physical Android user-account acceptance पर होंगे। Synthetic fixtures केवल example.com/example.org/CI-local permitted canary; असली Google account या private chat CI में नहीं।

1. **Retention:** controlled site cookie + localStorage/IndexedDB + draft रखें → background/lock/force-stop/crash/restart → data मिले; accidental auto-wipe/duplicate sends नहीं। Synthetic test data के अलावा कोई profile reset नहीं।
2. **Account boundary:** hermetic CI account/intent trap के साथ existing accounts से silent import न हो; device Add Account/broker external launch न हो। वास्तविक Google flow केवल user-owned device/account पर user-present; email/OTP/cookies output नहीं।
3. **Storage boundary:** unique synthetic canary private app storage में टिके; shared Downloads/MediaStore/OS-visible paths में नया canary नहीं। SQLite/WAL/LevelDB/cache/download paths अलग inventory।
4. **Backup:** merged binary manifest/resource binding + bmgr/restore tests + D2D/OEM migration matrix। Backup payload न बनना और restore से profile न आना; production data clear/uninstall नहीं।
5. **IPC:** controlled receiver/provider/URI-grant traps से clipboard/share/print/external intent/credential/autofill leaks न हों। सिर्फ permission absence पर्याप्त नहीं।
6. **Encryption:** covered fields के full on-disk scans; key failure/corruption पर data न मिटे, weak new writes न हों; whole-profile claim से पहले हर store का coverage।
7. **Screen/input:** FLAG_SECURE/recents और keyboard editor flags; OS screenshot test की status वास्तविक device के हिसाब से। Keyboard compliance की सीमा अलग रखें।
8. **Network:** controlled endpoint receipts और scoped logs से browser background traffic/website traffic अलग; TLS/Safe Browsing/sandbox/secure updates कमजोर नहीं।
9. **Performance/compatibility:** same APK cold/warm/page/download measures, drafts और long-stream continuity; कुछ broker-dependent sites के blockers छिपाएँ नहीं।
10. **AI gate:** privacy boundary prove होने के बाद ही अलग Gemini feasibility/consent। किसी unrelated connected app को Gemini authorization नहीं मानना।

## 6. वर्तमान जाँच और अवरोध

| आवश्यकता | बदलाव | Provenance / test type | Evidence | स्थिति / blocker |
|---|---|---|---|---|
| Data रहे, auto-wipe न हो | corrected contract; product code untouched | user clarification | यह दस्तावेज़ | requirements दर्ज; runtime NOT RUN |
| native source का containment audit | आठ fetched files + failed path सुरक्षित | pinned public source/static | research JSON | static observation only |
| static manifest utility | strict policy + Google CURRENT_ACCOUNT_ACCESS denial | decoded synthetic XML/host tests | tests + §8/testing history | current focused **134 passed in 4.79s**, इसमें 66 static-manifest cases; actual APK NOT RUN |
| negative controls | unresolved permission/UTF-16 history + नया Google bridge/debug override guard | host negative/mutation tests | TESTING.md + दोनों evidence JSON | पहले के सभी failures सुरक्षित; corrected host guards PASS |
| full local regression | पूरे host suite का वास्तविक run | host suite, Android नहीं | TESTING.md + native-source evidence | current **431 passed, 8 skipped in 128.41s**; device/feature PASS नहीं |
| persistent private browser feature | आठ-file opt-in native source patch और separate bundle tool | source apply + facade/provider host JVM with stubs | §8; नया native-source evidence | partial source implementation; APK/full containment NOT RUN |
| x64 और native ARM64 CI | कोई dispatch नहीं | GitHub access | authenticated HTTP401 | BLOCKED; पुराने APK को नया mode नहीं कहा जाएगा |
| physical/account/OEM behavior | कोई private account access नहीं | actual device required | उपलब्ध नहीं | NOT RUN |
| GitHub publication | स्थानीय clone में files | credential-safe git | remote auth HTTP401 | BLOCKED; published दावा नहीं |

Session bootstrap 18/20: दो remote protection/log checks 401 के कारण unverified, “protections off” सिद्ध नहीं। Local secret scan zero leaks। GitHub connector lookup unsupported; उसे available integration नहीं माना गया। किसी secret को chat में माँगा या print नहीं किया। CI/local Chromium source build duplicate नहीं चलाया गया; paid runner/VM नहीं शुरू किया।

## 7. प्राथमिक स्रोत

- Android Application Sandbox: <https://source.android.com/docs/security/app-sandbox>
- Android internal storage/security checklist: <https://developer.android.com/privacy-and-security/security-tips>
- Auto Backup, exclusions और transfer modes: <https://developer.android.com/identity/data/autobackup>
- Android 12 OEM D2D caveat: <https://developer.android.com/about/versions/12/backup-restore>
- Chrome sign-in का अलग workflow: <https://support.google.com/chrome/answer/185277?hl=en&co=GENIE.Platform%3DAndroid>
- Chromium manifest @155: <https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/android/java/AndroidManifest.xml>
- Account bridge @155: <https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/signin/public/android/java/src/org/chromium/components/signin/AccountManagerFacadeImpl.java>
- IME bridge @155: <https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/content/public/android/java/src/org/chromium/content/browser/input/ImeAdapterImpl.java>

## 8. जारी काम: opt-in native source layer और वास्तविक host execution

उपयोगकर्ता के “काम जारी रखो” निर्देश पर केवल योजना नहीं दोहराई गई: `patches/personal/` में **आठ-file native source patch**, उसका pinned-source guard और `tools/personal_browser/` में अलग development-bundle tool/Java host probe बनाए गए। Ordinary Swiftra series/package, signer, production build workflows और existing profiles नहीं बदले। Unit-test workflow में सिर्फ़ `jinja2` dependency जोड़ी गई।

### Source में लागू होने वाले बदलाव

1. **Accounts backend:** `AccountManagerFacadeProvider` अब personal layer में service-loader/platform delegate आरम्भ ही नहीं करता; नया `BrowserContainedAccountManagerFacade` local immutable empty roster देता है। Token requests cancelled, Add Account callback null, credential update false/confirmation null। Completion callbacks पूरे होते हैं; AnyThread Add Account callback UI queue पर post होता है। Device account या profile delete/sign-out नहीं करता।
2. **Java sign-in entry points:** `SigninManagerImpl` के support/allow/switch gates false; `signin()` abort callback देता है, internal native sign-in शुरू नहीं करता। Legacy Sync test entry rejects। **पूरे native IdentityManager/Sync/credential codebase के हर दूसरे रास्ते का isolation इससे सिद्ध नहीं होता।**
3. **Manifest/backup/providers:** library merge से forbidden account/storage/credential permissions वापस न जुड़ें, इसलिए `tools:node=remove` tombstones। `allowBackup=false`, legacy full backup false, no BackupAgent, shell profiling false, और तीन transfer modes के सभी नौ domains exclude। मौजूद browser providers के exports/URI grants false। Plain clipboard/external intents/system credential APIs अलग runtime work हैं।
4. **Persistent web-form input:** `ImeAdapterImpl` के दोनों overloads में no-personalized-learning hint; normal retained profile के लिए Incognito आवश्यक नहीं। यह omnibox/native editors या keyboard की offline compliance का proof नहीं।
5. **सुरक्षित अलग तैयारी:** explicit अलग development package और `personal-...` state label, existing output overwrite नहीं, base patch inputs byte-for-byte, existing public signer pin unchanged, no new keys। Final user package/migration अभी नहीं चुना गया। यह source bundle है, APK नहीं।

`0100` guard छह unchanged source-file hashes जाँचता है; दो नए outputs पहले से मौजूद हों तो भी refuse। Patch zero-context unified diff है: पहले exact hash prerequisite, फिर application; tests में **fuzz=0/offset=0**। इससे formatting gate को ढीला किए बिना diff-context blank lines की whitespace समस्या ठीक हुई। Existing patch engine की touched-file/epoch integration भी host पर चली है।

### Backup source का अतिरिक्त सत्यापन

Android Auto Backup documentation में cloud/D2D/cross-platform modes अलग हैं। Corresponding iOS app को register करने वाले `platform-specific-params` और data exclusions अलग भूमिकाएँ हैं। Official AOSP `android-16.0.0_r4` `FullBackup.java` में platform map entry support opt-in है; parser excludes को अलग पढ़ता है। इस source layer में नौ domains exclude हैं और कोई matching iOS app/registering identifier invent नहीं किया गया। Main branch को हर Android release का समान parser नहीं माना। **Actual Android/OEM restore/transfer फिर भी NOT RUN है।**

- Source: <https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r4/core/java/android/app/backup/FullBackup.java>
- Exact source hashes, branch/tag distinction और unsuccessful Chromium paths: `evidence/personal-native-source-2026-10-19.json` तथा `tools/personal_browser/upstream-index.json`। Chromium pin अब भी 155.0.8059.80 है—current-latest का दावा नहीं।

### Evidence और acceptance matrix

| Requirement | Changes | Provenance | Test type | Evidence | Status | Blockers / सीमा |
|---|---|---|---|---|---|---|
| सामान्य profile टिके, auto-wipe न हो | Incognito/wipe/sign-out/deletion नहीं जोड़े | user correction; added-source audit | static source only | native patch + no-deletion test | PASS (static/signature/format only) | वास्तविक cookie/IndexedDB/draft restart retention NOT RUN |
| Platform account facade deny | नया no-delegate backend/provider; empty roster और completed denial callbacks | pinned real interface/provider + नया Java | host `javac` + JVM, dependencies stubs | host probe; **29 assertions**, 3 rejected mutations | PASS (host component with stubs) | Android Binder/GMS/native paths का proof नहीं |
| Browser Java sign-in entry reject | support/allow/switch false, abort callback | pinned SigninManagerImpl | source inspection/unit guards | native patch tests | PASS (static/signature/format only) | पूरी class/Chromium Android compile और other native sign-in paths NOT RUN |
| Backup/providers declaration policy | explicit opt-out/exclusions, merge tombstones, provider grants off | Chromium template + official docs/AOSP parser | **20 synthetic Jinja configurations** + static audit | manifest source tests | PASS (static/signature/format only) | Android merger/dependency manifests/APK binding/backup/OEM runtime NOT RUN |
| Web-form keyboard privacy request | unconditional no-learning hint in both overloads | pinned ImeAdapterImpl | source inspection/unit guard | IME source test | PASS (static/signature/format only) | full Android compile, omnibox/native fields/keyboard behavior NOT RUN |
| अलग package/build inputs | non-overwriting deterministic opt-in source bundle | existing base patch engine/signer pin | host bundle/negative tests | prepare.py + source-engine test | PASS (static/signature/format only) | CI wiring, final package/label/update-channel decisions अभी बाकी |
| सभी outward data paths / whole-profile encryption | acceptance scope सुरक्षित, कोई false completion नहीं | §2/§5 | actual Android आवश्यक | no runtime artifact | NOT RUN / BLOCKED | private downloads, external intents/Share/clipboard/system autofill, encryption/key failure, screen/network/perf बाकी |
| दोनों native ABI + phone/account | कोई APK/dispatch/install नहीं | current environment | required native E2E | bootstrap authenticated HTTP401 | NOT RUN / BLOCKED | GitHub authentication; फिर x64 Actions + native ARM64, अलग physical/user-present account acceptance |

**वास्तविक final local results:** focused **134 passed in 4.79s** (66 native-source/host + 66 static-manifest + 2 existing APK-audit), Python syntax compilation PASS, full host suite **431 passed, 8 skipped in 128.41s**। Skips पुराने optional-fixture tests हैं; नए tests skipped नहीं। ये Android, retention, full encryption या speed results नहीं हैं।

प्रथम draft की तीन host-test failures, फिर Google CURRENT_ACCOUNT_ACCESS और duplicate-debug assignment के दो negative-control failures, तथा staged whitespace failure का इतिहास `TESTING.md`/नए evidence JSON में सुरक्षित है। Google permission और late-debug bypass बन्द किए; tests/format policy कमज़ोर नहीं की।

**अभी source-only क्यों:** final merged APK और native acceptance के बिना isolation का दावा गलत होगा। अलग package को ordinary Swiftra update feed का offer देना भी unresolved है; personal label, secure update policy और dedicated release gate के बिना इसे publisher में स्वतः नहीं लगाया गया। `prepare.py` receipt में `release_ready=false`, `apk_built=false`, `ci_wired_or_dispatched=false`, `product_containment=NOT RUN / NOT CERTIFIED` स्पष्ट हैं।

अगले implementation gates: external-intent/Share/clipboard/credential sinks, app-private download/viewer pipeline, complete storage/encryption/key-failure coverage, window/recents और बाकी input paths; फिर merged-APK binding और दोनों ABI पर वास्तविक retention/IPC/backup/network/performance tests। GitHub में सुरक्षित authentication फिर उपलब्ध होने तक CI/publication blocked हैं; किसी token को chat में भेजने की आवश्यकता नहीं।

**निष्कर्ष:** माँग persistent app-contained browser की है, incognito या self-deleting browser की नहीं। अब isolated native source implementation का पहला हिस्सा मौजूद है; complete containment/whole-profile encryption/all-web compatibility/actual Android PASS अभी सिद्ध नहीं हैं।
