# परियोजना के नियम (सहयोग और प्रमाण-अनुशासन)

1. **भाषा:** उपयोगकर्ता से हिंदी (देवनागरी) में बात करें, Hinglish नहीं। तकनीकी नाम और कोड अपने मूल रूप में रहें।
2. **काम का क्रम:** आधिकारिक, वर्तमान स्रोतों से शोध → आवश्यकता, जोखिम और मापनीय acceptance → न्यूनतम code → अलग-अलग परतों में परीक्षण (unit → emulator → असली device) → रिपोर्ट।
3. **"100% पक्का" का अर्थ:** सर्वोत्तम व्यावहारिक जाँच। सत्यापित तथ्य, अनुमान, अपरीक्षित बातें और बाहरी बाधाएँ हमेशा अलग लिखें। प्रमाण के बिना "verified" न कहें।
4. **दायरा:** मूल दायरा (`native-app/SCOPE_AND_ADVANCED_CAPABILITIES.md`) कभी चुपचाप कम न करें। कोई बाधा हो तो उसे gate के रूप में लिखें और उपयोगकर्ता से न्यूनतम सुरक्षित input माँगें।
5. **Status शब्दावली:** `PASS (actual Android device)` · `PASS (Android emulator)` · `PASS (desktop/browser component)` · `PASS (static/signature/format only)` · `NOT RUN / BLOCKED` · `FAIL`। UI parity के लिए: `verified / mismatch / blocked / not-tested`।
6. **विफलताओं का इतिहास:** पहली कोशिश की विफलताएँ भी `TESTING.md` में रखें। सब कुछ पहली बार में पास हुआ, ऐसा न दिखाएँ।
7. **Secrets:** token, cookie, password, OTP, signing key या account data कभी source, APK, log, report, screenshot या Git में न जाए।
   - GitHub API के लिए केवल `~/.secrets/gh.sh`, git के लिए केवल `~/tools/secret-guard/gitx`।
   - pre-commit, commit-msg और pre-push hooks तथा CI में gitleaks scan अनिवार्य हैं। Hooks `core.hooksPath` से चलते हैं, और `gitx` हर बार पहले self-heal करता है (`tools/secret-guard/lib.sh`)।
   - Token का एकमात्र स्थान `~/.secrets/gh_token` है (700/600)। इसे कभी `cat`/`echo` से print न करें, URL या argv में न डालें। जाँच के लिए: `tools/secret-guard/audit.sh`।
   - `test-e2e.sh` केवल साफ़ working tree पर चलाएँ (वह `reset --hard` करता है)।
8. **निजता:** UI capture केवल `about:blank`, `example.com` और `example.org` पर, बिना login के। उपयोगकर्ता के निजी chat का text कभी capture न करें। Arena परीक्षण केवल उपयोगकर्ता के अपने device और account पर, उसकी उपस्थिति में।
   - **अपवाद (उपयोगकर्ता की "Full permission", 2026-10-17):** Safe Browsing / Swiftra Shield जाँच के लिए emulator पर Google का हानिरहित test page `testsafebrowsing.appspot.com` खोला जा सकता है। साथ में केवल CI के अंदर `adb reverse` से चलने वाला local canary page (कोई असली हानिकारक site नहीं)।
9. **लागत:** केवल public repo के मुफ़्त standard runners। Larger runner या cloud VM उपयोगकर्ता की स्पष्ट लागत-स्वीकृति के बाद ही।
10. **Branding:** Google trademarks (नाम/logo) का वितरण लिखित अधिकार के बिना नहीं होगा। UI और व्यवहार की parity की आवश्यकता फिर भी जस की तस है; यह वितरण से पहले का एक legal gate है।
11. **Repository:** काम केवल `deepsilence10161-source/Fast-and-advanced-browser-` में होगा (उपयोगकर्ता का निर्देश, 15-10-2026)।
12. **Files GitHub पर रहें, workspace में नहीं** (उपयोगकर्ता निर्देश, 2026-10-15)। Code, docs, evidence और tools repo में रहते हैं; बड़े binaries (APK) केवल Actions artifacts में। Workspace में केवल working clone `fab/`, `.secrets/` (कभी GitHub पर नहीं) और `private-notes/` (सार्वजनिक repo में न डालने योग्य audit) रहते हैं। Run artifacts को local जाँच के बाद हटा दिया जाता है। Actions artifacts 90 दिन बाद expire होते हैं, इसलिए स्थायी evidence repo के `evidence/` में commit किया जाता है। कारण: snapshot की ~128 MB सीमा पार होने पर पिछला snapshot अधूरा बचा था (stale `.git`, permissions खो गए थे)।
13. हर नए session की शुरुआत में `bash /home/user/fab/tools/bootstrap.sh` चलाएँ (self-heal + 16-जाँच audit)। Snapshot permissions, `.git/config`, `.git/hooks`, `~/.cache` और `~/tools` नहीं रखता।
