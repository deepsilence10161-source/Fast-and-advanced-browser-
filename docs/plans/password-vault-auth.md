# 0022: native authentication audit (केवल source, 19-10-2026)

**Implementation / Android authentication E2E: NOT RUN.** यह 0022 का नया feature या runtime PASS नहीं है। Chromium tag `155.0.8059.80` के नौ अतिरिक्त auth files और पहले से पढ़े password client पर आधारित निर्णय हैं। स्रोत/hash सूची: `evidence/password-vault-auth-research-2026-10-19.json`।

## पक्के source facts और integration traps

1. `ChromePasswordManagerClient::GetDeviceAuthenticator()` पहले से Android पर factory इस्तेमाल करता है, मगर **60-second validity** देता है। इसे fresh reveal/export authentication समझकर कॉपी न करें।
2. `ChromeDeviceAuthenticatorFactory` में Android **FragmentActivity** वाला overload भी है। Settings vault screen को tab/WebContents बनाने की मजबूरी नहीं; सही profile/activity lifetime फिर भी अनिवार्य है।
3. Android `DeviceAuthenticatorAndroid::AuthenticateWithMessage()` में **`CHECK(message.empty())`** है। Desktop जैसा अपना nonempty reason भेजना release APK में भी crash कराएगा। इस API पर empty message चाहिए; ऑपरेशन का स्पष्ट कारण native UI में पहले बताना होगा या अलग, audited prompt integration चाहिए।
4. `DeviceAuthenticatorCommon::NeedsToAuthenticate()` `Now - last_good_auth >= auth_validity_period` देखता है। वैध monotonic timestamp और **zero period** पर हर ऑपरेशन फिर authentication माँगता है। Reveal/copy/export के लिए zero-period policy प्रस्तावित है; यह source property है, नया runtime test नहीं।
5. मौजूदा Java controller prompt में **`BIOMETRIC_STRONG | BIOMETRIC_WEAK | DEVICE_CREDENTIAL`** है और confirmation required false है। केवल इस factory को इस्तेमाल करने से **strong-only biometric** सुरक्षा सिद्ध नहीं होती।
6. Strong-only vault policy चाहिए तो weak authenticator को स्वीकार न करने वाला, version-compatible Android prompt path बनाना/जाँचना होगा। Android 10/API 29 combinations और screen-lock fallback अलग पढ़े/परीक्षित जाएँ; unsupported पर चुपचाप weak/no-auth fallback न हो। अभी ऐसा patch नहीं लिखा गया।
7. Missing activity/controller में capability query false होती है; उसके बाद सीधे `authenticate()` नहीं बुलाना। उपलब्ध configured screen-lock/biometric capability पहले जाँची जाए। Unsupported/unconfigured पर metadata-only state/स्पष्ट setup सूचना रहे, plaintext reveal/export नहीं।
8. Native `Cancel()` failure callback चलाता है; late auth completion cleared callback को ignore करती है। Callback स्वयं owner destroy कर सकता है—source में उसके बाद code न चलाने की चेतावनी है। Vault callback को profile + credential + action + UI lifetime से bind/WeakPtr-guard करें; background/cancel/configuration-change behavior का असली Android परीक्षण शेष है।
9. Java controller AndroidX `BiometricPrompt`, `BiometricManager` और `KeyguardManager` इस्तेमाल करता है। इन files में Google Password Manager/Sync private backend नहीं जोड़ा गया। इससे उन अलग Google services की अनुमति/कार्यक्षमता नहीं मिलती।

## 0022 के लिए निष्कर्ष, अभी लागू नहीं

- पहले metadata-only API; unauthenticated list के लिए existing `PasswordStoreBridge.GetAllCredentials()` से plaintext Java में न लाएँ। उस पुराने method में in-method re-auth नहीं है; सभी callers को सार्वभौमिक रूप से unauthenticated/vulnerable घोषित नहीं किया गया है।
- प्रत्येक reveal/copy/export से पहले उपयुक्त **fresh** OS verification; failed/cancelled/unsupported/background request पर secret न लौटे। Cipher/key availability check इस UI authentication का विकल्प नहीं।
- 0021 की cookie-compatible wrapped key को biometric-bound vault key बताकर प्रस्तुत न करें। UI gate और hardware/Keystore authentication binding अलग गुण हैं; physical hardware/attestation अभी NOT RUN है।
- Cancel/failure, no screen lock, weak-only biometric, strong biometric, device credential, rotation/background/late callback, तथा key unavailable/corrupt wrapped-pref cases की native acceptance चाहिए। सभी sensitive captures/logs निषिद्ध रहें।
- केवल emulator enrollment या desktop mocks से physical credential authentication PASS नहीं होगा। User-owned phone/account validation अलग gate है; कोई PIN/password/OTP माँगा नहीं गया।

यह मूल vault योजना, G1 legal gate या Google Sync/affiliation blockers को छोटा या समाप्त नहीं करता। Auth audit **PASS (static only)** है; 0022 अभी unimplemented है।
