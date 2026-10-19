# Swiftra: local password vault (योजना, 19-10-2026)

## अभी की स्थिति (code प्रमाण, tag 155.0.8059.80)

| जाँच | फ़ाइल | नतीजा |
|---|---|---|
| Android पर store backend | `chrome/browser/password_manager/factories/password_store_backend_factory.cc` | `IsPasswordManagerAvailable()` false हो तो `PasswordStoreEmptyBackend`, यानी कुछ save नहीं होता |
| उपलब्धता की शर्त | `chrome/browser/password_manager/android/password_manager_android_util.cc` | Google का internal (downstream) backend **और** GMS का न्यूनतम version, दोनों चाहिए। Swiftra (upstream) में internal backend नहीं है |
| Local database | `components/password_manager/core/browser/password_store/BUILD.gn` | `login_database*`, `password_store_built_in_backend*`, `insecure_credentials_table`, `password_notes_table`, `statistics_table` केवल `!is_android` में compile होते हैं |
| Encryption | `chrome/browser/browser_process_impl.cc`, `components/os_crypt/async/browser/posix_key_provider.cc` | Android (`IS_POSIX`) पर केवल `PosixKeyProvider` जुड़ता है, जिसकी key (`kV10Key`, AES-128-CBC) source में सबके सामने लिखी है। यह छिपाना है, असली encryption नहीं। `login_database_posix.cc` encryptor न होने पर save नहीं करता (fail-closed) |

Status: Swiftra में password save **नहीं** होता (static, code से पक्का)। Device पर NOT RUN।
दूसरे password manager (Android Autofill service, जैसे Bitwarden) से login का रास्ता upstream जैसा खुला है; उसका E2E PLAN 12 में है।

## पहला कदम अलग से फ़ायदेमंद: Keystore key provider (0021)

`components/autofill/core/browser/webdata/payments/payments_autofill_table.cc` card/IBAN के fields को `encryptor` से encrypt करता है, और `chrome/browser/webdata_services/web_data_service_factory.cc` वह encryptor `g_browser_process->os_crypt_async()` से लेता है। Android पर उसमें केवल सार्वजनिक fixed key (`kV10Key`) है। इसलिए Chrome Android और आज का Swiftra, दोनों local card/IBAN data उसी सार्वजनिक key से "encrypt" करते हैं (static, code से)।
**Cookies भी:** `chrome/browser/net/system_network_context_manager.cc` हर profile को `CookieEncryptionProviderImpl(os_crypt_async)` देता है, `enable_encrypted_cookies` का default true है, और `services/network/network_context.cc` का `CookieOSCryptAsyncDelegate` हर cookie value को उसी encryptor से encrypt करता है। यानी Android पर login-session cookies भी सार्वजनिक key से "encrypted" हैं (static, code से)।
**गति का जोखिम:** `CookieOSCryptAsyncDelegate::Init()` encryptor तैयार होने तक cookie load रोकता है, इसलिए Keystore वाला कदम startup पर असर डाल सकता है। इसलिए Keystore का काम background thread पर हो, OSCryptAsync init (जो startup में पहले ही शुरू होता है) के साथ ही चले, और 0021 तभी release होगा जब SPEED_E2E / STARTUP_TRACE A/B में कोई गिरावट न दिखे।

Keystore वाला provider (नीचे कदम 3) vault से पहले भी Swiftra को Chrome से ज़्यादा सुरक्षित बनाएगा। cookies, cards और IBAN, तीनों के लिए। यह एक मापने लायक "Chrome से आगे" बिंदु है, जो device E2E के बाद ही PASS माना जाएगा।

## Patch योजना (0021 provider, फिर 0022 vault; बड़ा काम)

1. `BUILD.gn`: Android पर built-in backend की फ़ाइलें compile करना (`login_database_posix.cc` सहित)।
2. `password_store_backend_factory.cc`: internal backend न हो तो `PasswordStoreBuiltInBackend` (profile store), account store नहीं।
3. Encryption: **0021 में अब लागू provider को दोबारा न बनाएँ**: असली tag `sw1` है (`v20` पुरानी योजना थी), AES-256-GCM, Keystore-wrapped per-install key। x64 run 39249911374 का `KEYSTORE_E2E PASS prefix=sw1 ... cookie_after_restart=True` log इस session में फिर पढ़ा गया; यह ऐतिहासिक emulator evidence है, नया vault test नहीं। नई local LoginDatabase उसी OSCryptAsync को ले; password-save acceptance में `sw1` और no-plaintext अलग जाँचे जाएँ। `v10` को नई vault writes के लिए सुरक्षित fallback न मानें।
4. Settings UI: बिना GMS वाली native password सूची (देखना, कॉपी, हटाना, export) और biometric/screen-lock re-auth।
5. Leak check: केवल user के कहने पर, k-anonymity (SHA-1 prefix के 5 अक्षर + padding)। सेवा के licence और privacy की जाँच के बाद ही।
6. E2E: example.com/example.org पर local test form से save → app restart → autofill → delete। कोई असली account या credentials नहीं।

जोखिम: affiliation/sync deps, upstream के Android-only दावे (DCHECK), APK का आकार। हर कदम का build + emulator E2E होगा।

## अगला implementation pass: नई निर्भरताएँ (19-10-2026, 14:00 UTC के बाद)

नीचे **source निरीक्षण** हैं, कोई नया password-save device PASS नहीं। `0022` अभी लिखा/बिल्ड/प्रकाशित नहीं हुआ। पहले के निष्कर्ष दोहराने के बजाय अगले patch के आवश्यक अतिरिक्त रास्ते जाँचे गए:

| आवश्यक बदलाव / जोखिम | @155 का सटीक प्राथमिक स्रोत | समर्थित तथ्य / अगला निर्णय |
|---|---|---|
| केवल backend बदलना पर्याप्त नहीं | [settings service factory](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/password_manager/factories/password_manager_settings_service_factory.cc), `CreateService()` | Android पर internal password manager उपलब्ध न हो तो **nullptr** देता है |
| Save का दूसरा gate | [ChromePasswordManagerClient](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/password_manager/chrome_password_manager_client.cc), `IsSavingAndFillingEnabled()` | `settings_service && IsSettingEnabled(kOfferToSavePasswords)` आवश्यक है। इसलिए local settings service भी जोड़नी होगी। `--enable-automation` saving को बंद करता है; भविष्य का save E2E वह flag न लगाए |
| Local settings implementation पहले से compile होती है | [core/browser/BUILD.gn](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/password_manager/core/browser/BUILD.gn), [settings implementation](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/password_manager/core/browser/password_manager_settings_service_impl.cc) | `PasswordManagerSettingsServiceImpl` prefs पढ़ती है और backend fetch नहीं करती। अपने local vault के लिए इसका चुनाव हो सकता है; Google backend उपलब्ध होने का झूठा global संकेत न दें |
| LoginDatabase बनाने वाला helper भी Android से बाहर है | [password_store_factory_util.cc](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/password_manager/core/browser/password_store_factory_util.cc), [.h](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/password_manager/core/browser/password_store_factory_util.h) | `CreateLoginDatabase` की declaration और definition दोनों `!IS_ANDROID` में हैं। GN sources भर जोड़कर उसी helper को Android factory से बुलाना पर्याप्त नहीं होगा |
| Key failure पर data loss से बचाव | वही `GetPolicyFromPrefs()` | Android को सीधे existing else-path में लाने पर undecryptable-password deletion policy **true** होगी। यह अभी लागू Android behavior नहीं, naïve guard-removal का जोखिम है। नई vault के लिए **false / preserve-and-error** प्रस्तावित; Keystore failure को empty vault या silently deleted credentials न बनाएँ |
| Desktop factory का affiliation CHECK Android पर न कॉपी करें | [profile factory](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/password_manager/factories/profile_password_store_factory.cc), [backend factory](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/password_manager/factories/password_store_backend_factory.cc) | Android profile factory affiliation service को nullptr भेजती है; desktop construction में `CHECK(affiliation_service)` है |
| Null affiliation का वैध native रास्ता | [request handler](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/password_manager/core/browser/password_store/get_logins_with_affiliations_request_handler.cc), `GetLoginsHelper::Init()` | Null helper पर exact/PSL matching का स्पष्ट upstream fallback है। यह Android app/site affiliation parity का प्रमाण नहीं; वह अलग acceptance/blocker रहेगा |
| Sync source availability | [sync/BUILD.gn](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/password_manager/core/browser/sync/BUILD.gn), [async helper](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/password_manager/core/browser/password_store/login_database_async_helper.cc) | `PasswordSyncBridge` sources Android GN से बाहर नहीं रखे गए; helper bridge बनाता है। इससे Google Sync की अनुमति/कार्यक्षमता सिद्ध नहीं होती। Account store/Google Sync को local store बताकर सक्रिय न करें |
| Existing Java bridge को unauthenticated list के लिए न चलाएँ | [Java PasswordStoreBridge](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/password_manager/android/java/src/org/chromium/chrome/browser/password_manager/PasswordStoreBridge.java), [native bridge](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/password_manager/android/password_store_bridge.cc), `GetAllCredentials()` | वह हर credential का plaintext password Java objects में देता है; उस method में re-auth नहीं है। Metadata-only listing और reveal/copy/export से पहले वास्तविक screen-lock/biometric verification आवश्यक हैं |
| Existing settings launch local UI नहीं है | [PasswordManagerHelper.java](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/password_manager/android/java/src/org/chromium/chrome/browser/password_manager/PasswordManagerHelper.java), `showPasswordSettings()` | Unavailable/download-CSV dialog अथवा credential-manager launcher की ओर जाता है। नया backend लगने मात्र से स्वतंत्र native vault screen नहीं बनती |

### 0022 acceptance में ये मामले भी अनिवार्य रहें

1. GMS/internal backend के बिना native save prompt और local settings toggles वास्तव में काम करें; Google Password Manager/Sync होने का झूठा दावा न हो।
2. Save → force-stop/restart → autofill → update/delete, `example.com`/`example.org` के CI-local synthetic forms पर; cross-origin filling और incognito persistence न हों।
3. नई password writes में `sw1`, SQLite/WAL/journal में plaintext नहीं। केवल `Encryptor::IsEncryptionAvailable()` पर्याप्त नहीं माना जाएगा यदि public `v10` fallback उपलब्ध हो। Keystore failure पर save fail-closed हो और पुराने records न मिटें। यह लक्ष्य है, अभी परिणाम नहीं।
4. Reveal/copy/export में वास्तविक re-auth cancellation/failure/unsupported screen-lock को सफलता न माना जाए; plaintext passwords unauthenticated native list, logs, screenshots या background task preview में न जाएँ।
5. Cold/warm startup और same-APK page/download benchmarks से नया synchronous startup/IO bottleneck न आए; UI thread पर database/Keystore काम न हो।
6. दोनों ABI source builds, x64 emulator तथा native arm64 Redroid E2E; physical Android smoke और G1/G5 gates अलग बने रहें।

प्रमाण सूची: `evidence/password-vault-research-2026-10-19.json` में fetched primary-source hashes। इनमें से किसी निरीक्षण को `PASS (actual Android device)` न कहा जाए।
