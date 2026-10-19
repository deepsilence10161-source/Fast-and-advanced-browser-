# Swiftra: local password vault (योजना, 19-10-2026)

## अभी की स्थिति (code प्रमाण, tag 155.0.8059.80)

| जाँच | फ़ाइल | नतीजा |
|---|---|---|
| Android पर store backend | `chrome/browser/password_manager/factories/password_store_backend_factory.cc` | `IsPasswordManagerAvailable()` false हो तो `PasswordStoreEmptyBackend`, यानी कुछ save नहीं होता |
| उपलब्धता की शर्त | `chrome/browser/password_manager/android/password_manager_android_util.cc` | Google का internal (downstream) backend **और** GMS का न्यूनतम version, दोनों चाहिए। Swiftra (upstream) में internal backend नहीं है |
| Local database | `components/password_manager/core/browser/password_store/BUILD.gn` | `login_database*`, `password_store_built_in_backend*`, `insecure_credentials_table`, `password_notes_table`, `statistics_table` केवल `!is_android` में compile होते हैं |
| Encryption | `components/os_crypt/async/browser/` | Android के लिए कोई key provider नहीं (केवल `posix_key_provider`) |

Status: Swiftra में password save **नहीं** होता (static, code से पक्का)। Device पर NOT RUN।
दूसरे password manager (Android Autofill service, जैसे Bitwarden) से login का रास्ता upstream जैसा खुला है; उसका E2E PLAN 12 में है।

## Patch योजना (0021, बड़ा काम)

1. `BUILD.gn`: Android पर built-in backend की फ़ाइलें compile करना (`login_database_posix.cc` सहित)।
2. `password_store_backend_factory.cc`: internal backend न हो तो `PasswordStoreBuiltInBackend` (profile store), account store नहीं।
3. Encryption: Android Keystore (AES-256-GCM, non-exportable key) वाला `os_crypt_async` key provider; plaintext कभी disk पर नहीं।
4. Settings UI: बिना GMS वाली native password सूची (देखना, कॉपी, हटाना, export) और biometric/screen-lock re-auth।
5. Leak check: केवल user के कहने पर, k-anonymity (SHA-1 prefix के 5 अक्षर + padding)। सेवा के licence और privacy की जाँच के बाद ही।
6. E2E: example.com/example.org पर local test form से save → app restart → autofill → delete। कोई असली account या credentials नहीं।

जोखिम: affiliation/sync deps, upstream के Android-only दावे (DCHECK), APK का आकार। हर कदम का build + emulator E2E होगा।
