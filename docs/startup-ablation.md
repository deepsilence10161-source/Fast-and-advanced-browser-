# Startup ablation: सुरक्षा समान, वही APK — 20-10-2026

## कारण और सीमा

19-10 का ARM baseline A/B cold median 750 बनाम 694.5 ms था (+7.99%), पर APKs/कई features अलग थे। उसे Keystore का causal खर्च नहीं कहा जा सकता। अगला प्रयोग **वही installed APK** रखकर केवल छह allowlisted performance features में से एक को disable करेगा; shipped control में सब compiled defaults रहेंगे। Keystore, Safe Browsing, ad/tracker blocking, TLS, site isolation और signed updates नहीं बदले जाएँगे। यह browser implementation का विकल्प नहीं, अगले न्यूनतम source fix के लिए diagnostic है।

Candidates: `AndroidStartupImprovements`, `AndroidSystemFontPrewarming`, `TweakApplicationPreloadMoveWarmUp`, `AndroidWarmUpSpareRendererWithTimeout`, `SQLitePersistentCookieStoreEarlyInit`, `EarlyCookieLoadOnPreconnect`। नाम/पैरामीटर pinned `155.0.8059.80` config से हैं; किसी custom arbitrary flag का input नहीं। केवल `about:blank`/native launcher तथा `chrome://version` receipt; कोई HTTPS exception, external test page या certificate bypass नहीं।

## शोध से महत्वपूर्ण measurement trap

- Pinned `components/cached_flags/.../CachedFlag.java` स्पष्ट कहता है: Java pre-native flag पिछले run की SharedPreferences से आता है और उसी process में स्थिर रहता है। Native command line बदलने का असर उसी startup के Java code में मानना गलत होगा।
- इसलिए हर mode पहले unmeasured native warm-up करता है, CLI nonce/override सत्यापित करता है, HOME/stop के बाद केवल नामित cached booleans और safe-mode counters memory में पढ़ता है। अपेक्षित cache और zero crash/safe-mode state आने के बाद ही measured cold launches शुरू हों। Private prefs न लिखे/न artifact में सहेजे जाएँ।
- `base/feature_list.cc` CLI override precedence देता है। `CachedFlagUtils` native values एक `apply()` में cache करता है; physical/unknown device पर helper चलना निषिद्ध है।
- Android के official Macrobenchmark metrics TTID और fully-drawn को अलग रखते हैं। यहाँ **`am start -W TotalTime`** diagnostic है, Macrobenchmark/TTFD या page LCP नहीं। Source: https://developer.android.com/topic/performance/benchmarking/macrobenchmark-metrics#startup-timing (20-10-2026 पढ़ा)।

## पहले निर्धारित protocol / acceptance

- 4 counterbalanced blocks; प्रति mode प्रति block 3 cold launches = 12/mode, 7 modes। सभी modes समान `speed` AOT state में; measured start/end dexopt status दर्ज हों। यह diagnostic compiled state है, sideload-default `verify` का दावा नहीं।
- Warm-up के tabs बंद हों; हर measured launch से पहले browser PID gone और नया PID/`LaunchState: COLD` + positive TotalTime आवश्यक। OS page cache wipe, data clear या key deletion नहीं।
- Actual installed base.apk SHA आरंभ/अंत में बराबर; CLI receipt, cached-flag receipt, safe-mode/crash counters और हर sample का validity कारण दर्ज हों। Missing/uncertain receipt पर NOT_RUN/PARTIAL, fake gain नहीं।
- Command-line file की मूल bytes/mode वापस हों; shipped cached flags फिर app द्वारा prime हों; अंत में dexopt `--reset`। Secret data/keys/logs/actual command-line dump नहीं।
- Wrapper उसके बाद उसी profile पर मौजूदा `KEYSTORE_E2E` चलाकर `sw1`, no plaintext, wrapped pref, restart-cookie recovery और Keystore2 की कड़ी postcondition माँगे।
- दोनों ABI के real GitHub Actions Android runs सहायक चलाएगा। केवल free standard public-repo runners। नया focused mode कभी publish नहीं करेगा।
- Medians, raw samples, block differences और interval **MEASURED** हैं। कोई feature अपने-आप disable/promote नहीं होगा। Startup candidate बेहतर हो तो अगला चरण समान privacy वाले LCP/page/JS measurements तथा verify-ART confirmation होगा; पूरे product/current Chrome/physical-device PASS का दावा नहीं।

स्थिति: न्यूनतम harness और unit/host functional tests लागू हैं; full local suite **289 passed, 8 skipped (126.06s)**। Actual Android ablation outcomes अभी NOT RUN, इसलिए कोई product flag बदला/promote नहीं किया गया। स्रोत hashes `evidence/startup-ablation-2026-10-20/research.json` में हैं। मूल `MASTER_PROMPT.md` §15 तथा कानूनी/account/physical gates अपरिवर्तित हैं।


## पहला वास्तविक run: AOT, दोनों ABI — 20-10

Driver `18b60ad`: x64 **39387937370**, ARM64 **39387941069**। दोनों में **84/84 valid process-cold samples**, 28/28 mode-blocks; हर mode के 12 samples। CLI/next-run cache/safe-mode receipts, समान installed SHA, fixed speed-AOT state तथा original flag bytes/mode बहाली पुष्ट। उसके बाद उसी profile का **KEYSTORE_E2E PASS sw1**। यह diagnostic protocol का सफल execution है, performance improvement PASS नहीं।

| ablation | x64 median block delta | ARM64 median block delta | निष्कर्ष |
|---|---:|---:|---|
| बिना AndroidStartupImprovements | +3.65% | −1.79% | दिशा भी अलग |
| बिना system-font prewarming | −0.89% | −2.37% | intervals दोनों में zero को काटते हैं |
| बिना preload move-warmup | −0.72% | +3.15% | दिशा अलग |
| बिना spare renderer warmup | −0.43% | +2.90% | दिशा अलग |
| बिना cookie-store early init | −0.87% | 0.00% | निर्णायक लाभ नहीं |
| बिना early cookie preconnect | +0.08% | +2.81% | निर्णायक लाभ नहीं |

Positive delta = flag हटाने पर धीमा। **सभी छह block-bootstrap intervals में zero शामिल है; कोई flag product में बदला नहीं गया।** केवल point estimate देखकर startup fix घोषित नहीं किया गया। Raw samples, summaries और device/hash metadata evidence में हैं।

## अगला निर्धारित pass: install-like verify ART

AOT Java की interpreter/JIT लागत को हटा देता है; पुराने sideload-default cold signal को इससे निर्दोष/दोषी नहीं कहा जा सकता। इसलिए वही protocol अब दोनों ABI पर fixed **verify (`cmd package compile --reset`)** में भी चलेगा। हर mode और start/end status verify होना आवश्यक है; background dexopt से state बदली तो partial/NOT_RUN। `ablation_compilation` input केवल speed/verify allowlist है; browser/security settings समान रहती हैं। Results लंबित हैं; no automatic flag promotion।

## पुराने वास्तविक trace का सीमित अतिरिक्त निरीक्षण

ARM full run 39274414134 के startup trace में provider location `browser_process_impl.cc::GetKey` worker **9.526 ms** और reply task **0.070 ms** मिला। Worker Activity.onCreate से **355.188 ms** पर शुरू हुआ; profile creation **355.128–373.411 ms** में चल रहा था। Reply **379.993 ms** पर हुआ। यह एक sample का whole-task duration है—पूर्ण crypto cost/queue wait, causal 8% regression या हर device का खर्च नहीं। Key/value bytes या preference contents inspect/print नहीं किए गए।
