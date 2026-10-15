# परियोजना के नियम (सहयोग और प्रमाण-अनुशासन)

1. **भाषा:** उपयोगकर्ता से हिंदी (देवनागरी) में बात करें, Hinglish नहीं। तकनीकी नाम और कोड अपने मूल रूप में रहें।
2. **काम का क्रम:** आधिकारिक, वर्तमान स्रोतों से शोध → आवश्यकता, जोखिम और मापनीय acceptance → न्यूनतम code → अलग-अलग परतों में परीक्षण (unit → emulator → असली device) → रिपोर्ट।
3. **"100% पक्का" का अर्थ:** सर्वोत्तम व्यावहारिक जाँच। सत्यापित तथ्य, अनुमान, अपरीक्षित बातें और बाहरी बाधाएँ हमेशा अलग लिखें। प्रमाण के बिना "verified" न कहें।
4. **दायरा:** मूल दायरा (`native-app/SCOPE_AND_ADVANCED_CAPABILITIES.md`) कभी चुपचाप कम न करें। कोई बाधा हो तो उसे gate के रूप में लिखें और उपयोगकर्ता से न्यूनतम सुरक्षित input माँगें।
5. **Status शब्दावली:** `PASS (actual Android device)` · `PASS (Android emulator)` · `PASS (desktop/browser component)` · `PASS (static/signature/format only)` · `NOT RUN / BLOCKED` · `FAIL`। UI parity के लिए: `verified / mismatch / blocked / not-tested`।
6. **विफलताओं का इतिहास:** पहली कोशिश की विफलताएँ भी `TESTING.md` में रखें। सब कुछ पहली बार में पास हुआ, ऐसा न दिखाएँ।
7. **Secrets:** token, cookie, password, OTP, signing key या account data कभी source, APK, log, report, screenshot या Git में न जाए।
   - GitHub API के लिए केवल `~/.secrets/gh.sh`, git के लिए केवल `~/tools/secret-guard/gitx`।
   - pre-commit, commit-msg और pre-push hooks तथा CI में gitleaks scan अनिवार्य हैं।
8. **निजता:** UI capture केवल `about:blank`, `example.com` और `example.org` पर, बिना login के। उपयोगकर्ता के निजी chat का text कभी capture न करें। Arena परीक्षण केवल उपयोगकर्ता के अपने device और account पर, उसकी उपस्थिति में।
9. **लागत:** केवल public repo के मुफ़्त standard runners। Larger runner या cloud VM उपयोगकर्ता की स्पष्ट लागत-स्वीकृति के बाद ही।
10. **Branding:** Google trademarks (नाम/logo) का वितरण लिखित अधिकार के बिना नहीं होगा। UI और व्यवहार की parity की आवश्यकता फिर भी जस की तस है; यह वितरण से पहले का एक legal gate है।
11. **Repository:** काम केवल `deepsilence10161-source/Fast-and-advanced-browser-` में होगा (उपयोगकर्ता का निर्देश, 15-10-2026)।
