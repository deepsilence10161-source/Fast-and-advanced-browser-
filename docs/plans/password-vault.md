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
3. Encryption: नया `os_crypt_async` provider (tag `v20`, `PosixKeyProvider` से ऊँची precedence): हर install पर random 256-bit key, जो Android Keystore की non-exportable key से wrap होकर prefs में रहे; algorithm `kAES256GCM`। `v10` केवल पुराने data को पढ़ने के लिए। plaintext कभी disk पर नहीं।
4. Settings UI: बिना GMS वाली native password सूची (देखना, कॉपी, हटाना, export) और biometric/screen-lock re-auth।
5. Leak check: केवल user के कहने पर, k-anonymity (SHA-1 prefix के 5 अक्षर + padding)। सेवा के licence और privacy की जाँच के बाद ही।
6. E2E: example.com/example.org पर local test form से save → app restart → autofill → delete। कोई असली account या credentials नहीं।

जोखिम: affiliation/sync deps, upstream के Android-only दावे (DCHECK), APK का आकार। हर कदम का build + emulator E2E होगा।
