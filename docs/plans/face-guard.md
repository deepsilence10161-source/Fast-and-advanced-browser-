# Face Guard — केवल मालिक का चेहरा दिखने पर browser सक्रिय

**तिथि:** 17 नवंबर 2026 · **स्थिति:** चरण 0–1 (design + host-परीक्षित निर्णय-core) तैयार। कैमरा, model, UI, Settings, APK और Android E2E **NOT RUN**।

## 1. उपयोगकर्ता की माँग
- Browser में live face detection; **केवल मालिक का चेहरा दिखते रहने** पर ही content सक्रिय रहे।
- Settings में On/Off हो सके।
- Privacy-first लाइन बनी रहे: कोई auto-wipe, डेटा-हटाना या account-migration नहीं; AI deferred।

## 2. तय किए गए डिफ़ॉल्ट (उपयोगकर्ता बदल सकता है)
| विषय | निर्णय |
|---|---|
| डिफ़ॉल्ट | **Off**। चालू करने से पहले enrollment अनिवार्य |
| क्या होता है (उपयोगकर्ता निर्णय, 17-11-2026) | चेहरा हटते ही **तुरंत tab switcher / recent-tabs (select-tab) स्क्रीन खुले**; media pause। Switcher में page के **thumbnails/titles छिपे (masked)** रहेंगे और tab चुनना तब तक बंद जब तक मालिक फिर प्रमाणित न हो — वरना thumbnail ख़ुद page-सामग्री दिखा देते। मालिक लौटे → स्थिर पहचान के बाद thumbnails दिखें और tab चुना जा सके |
| गति का लक्ष्य | चेहरा हटने से lock तक **लक्ष्य ≲ 0.5 s** (डिफ़ॉल्ट lockDelay 300 ms + frame-अंतराल + detection)। यह **लक्ष्य** है, गारंटी नहीं; emulator पर मापा जाएगा। Frames रुकें तो भी timer से lock (stale 1 s) |
| दूसरा चेहरा | मालिक के साथ किसी और का चेहरा आए → भी lock (सख़्त)। यह विकल्प बंद किया जा सकता है |
| Fail-closed | template गायब/ख़राब, camera permission नहीं, camera विफल, frames रुकें, background — सब पर lock |
| बाहर निकलने का रास्ता | device PIN/pattern/password से override (backgrounding तक); मालिक कभी स्थायी रूप से बाहर न हो |
| बंद करना | केवल तब जब मालिक अभी प्रमाणित हो या device credential दिया गया हो |
| डेटा | केवल embedding template, app-internal storage में Keystore-wrapped। तस्वीरें/वीडियो कभी disk, log, network या clipboard में नहीं |
| विफलता पर | कोई data-delete नहीं; template ख़राब हो तो lock + पुनः enrollment, पुराना डेटा सुरक्षित |

## 3. स्पष्ट सीमाएँ (दावे में नहीं बदलेंगी)
1. **फ़ोटो/वीडियो से धोखा:** सामान्य face matching असली चेहरे और स्क्रीन/फ़ोटो में फ़र्क नहीं करती। Liveness (blink/head-turn या depth) अलग चरण है; तब तक "सुरक्षा" नहीं, **सुविधा/shoulder-surfing रोक** कहा जाएगा।
2. **Accuracy अपरिमाणित:** match threshold (डिफ़ॉल्ट 0.70) **UNCALIBRATED** है। चुने हुए model पर FAR/FRR मापे बिना कोई सटीकता-दावा नहीं।
3. **Security boundary नहीं:** rooted/compromised device या OS-स्तर के हमलावर के विरुद्ध नहीं।
4. **Camera हर समय:** foreground में camera चालू = बैटरी/गर्मी, और Android का camera indicator दिखेगा। Background में camera बंद।
5. **रोशनी/चश्मा/मास्क** से मालिक lock हो सकता है — इसलिए device-credential override ज़रूरी है।
6. **Bias:** face models अलग-अलग त्वचा-रंग/उम्र समूहों पर अलग चलते हैं; चुने model का सार्वजनिक आकलन पढ़कर ही अपनाया जाएगा।

## 4. वास्तुकला (चरण)
| चरण | काम | सत्यापन | स्थिति |
|---|---|---|---|
| 0 | यह design और निर्णय | समीक्षा | तैयार |
| 1 | `FaceGuardPolicy` — lock/unlock state machine, edge actions (LOCK/UNLOCK, nextDeadlineMs timer), embedding matching/template | host JVM: 76 assertions + 15 mutants reject | **तैयार (host only)** |
| 2 | Model चयन (licence, आकार, bias, on-device): detector + embedding। Camera2 (framework, GMS-मुक्त) से frames | licence/आकार रिपोर्ट, host accuracy-harness | बाकी |
| 3 | Enrollment UI, Keystore-wrapped template storage, LOCK पर masked tab switcher खोलना (Chromium `LayoutType.TAB_SWITCHER`; thumbnails/titles mask), media pause | x64 emulator virtual camera दृश्य | बाकी |
| 4 | Settings toggle (Privacy) + camera permission flow + device-credential override | x64 emulator + ARM64 Redroid UI | बाकी |
| 5 | Personal layer `0104` (सामान्य `patches/series` में नहीं), full Android compile | CI build x64 + arm64 | बाकी |
| 6 | Android E2E | नीचे §5 | बाकी |

Chromium के Android `shape_detection` Face API पर निर्भर नहीं रहेंगे: वह GMS पर आधारित है और unbranded build में उपलब्ध नहीं है। केवल detection (identity नहीं) देने वाले `android.media.FaceDetector`/camera2 face statistics अकेले "केवल मेरा चेहरा" का प्रमाण नहीं हैं।

## 5. Acceptance (प्रत्येक के लिए वास्तविक Android रन)
- **x64 Actions emulator (API 36):** emulator का virtual scene camera/नियंत्रित वीडियो-इनपुट से: मालिक दिखे → खुला; ग़ायब → lock; दूसरा चेहरा → lock; permission हटाने → lock; Settings toggle Off → कभी lock नहीं; App restart के बाद template और setting बनी रहे; डेटा/profile संरक्षित (C08)।
- **Native ARM64 Redroid:** Redroid में सामान्यतः कैमरा नहीं होता। इसलिए वहाँ **Settings toggle, enrollment-अनुपस्थिति पर fail-closed lock, permission-denied lock और override** जाँचे जाएँगे; **कैमरा-आधारित पहचान ARM64 पर NOT RUN** लिखी जाएगी जब तक वास्तविक input उपलब्ध न हो — इसे PASS नहीं कहा जाएगा।
- Host PASS को Android PASS नहीं कहा जाएगा।

## 6. खुले निर्णय (उपयोगकर्ता से)
1. ~~Face न दिखे तो क्या?~~ **तय:** tab switcher खुले (masked thumbnails)। खुला प्रश्न: क्या masked switcher में भी tab चुनना पूरी तरह बंद रहे (डिफ़ॉल्ट) या चुनने पर face-check माँगे?
2. दूसरा चेहरा दिखे तो lock (डिफ़ॉल्ट) या अनदेखा?
3. Liveness (blink/head-turn) चरण 6 से पहले चाहिए?

## 7. चरण 2 के शोध-निष्कर्ष (17 नवंबर 2026; सार्वजनिक स्रोत, अभी model चुना नहीं गया)
| विषय | निष्कर्ष | स्रोत/स्थिति |
|---|---|---|
| Face detector उम्मीदवार | MediaPipe BlazeFace short-range (Apache-2.0, model card उपलब्ध), या YuNet (MIT, 5-point landmarks) | तृतीय-पक्ष wrapper repos की licence तालिकाएँ; मूल repo/model-card से **अलग से सत्यापित करना बाकी** |
| Embedding उम्मीदवार | MobileFaceNet (लगभग 5 MB, 128–512-d)। **Licence वितरण-निर्भर** — कुछ repos MIT बताते हैं पर उनका training data (जैसे WebFace) अकसर केवल-शोध शर्तों पर होता है। AuraFace (Apache-2.0) बड़ा ResNet100 है | **अपनाने से पहले weights + training-data की licence पढ़ना अनिवार्य**; अभी NOT CHOSEN |
| Photo/screen spoof | 2D RGB कैमरा बिना liveness के photo-spoof के प्रति कमज़ोर; NIST SP 800-63B प्रमाणीकरण के लिए presentation-attack detection माँगता है | इसलिए Face Guard को अभी "प्रमाणीकरण" नहीं, सुविधा/shoulder-surfing रोक कहा जाएगा |
| Bias | NIST IR 8280: false-positive अंतर बड़े (कई algorithms में 10x से 100x तक), महिलाओं/बुज़ुर्गों/बच्चों में अधिक; false-negative अंतर छोटे | "अजनबी का खुल जाना" (false accept) मुख्य जोखिम है → threshold मालिक के अपने डेटा और विरोधी नमूनों पर calibrate होगा, और strict बाकी रहेगा |
| Runtime | Chromium Android build में TFLite Java runtime का मार्ग **अभी सत्यापित नहीं**; यह चरण 2 का मुख्य तकनीकी जोखिम है | खुला |

इन सबसे यह नहीं निकलता कि कोई model "सुरक्षित" या "सटीक" है; ये केवल चयन-मानदंड हैं।

## 8. चरण 3 के source-निष्कर्ष (Chromium 155.0.8059.80, सार्वजनिक gitiles; patch अभी नहीं लिखा)
| ज़रूरत | मिला हुआ बिंदु (सत्यापित: फ़ाइल मौजूद, पंक्तियाँ पढ़ीं) | टिप्पणी |
|---|---|---|
| LOCK पर tab switcher खोलना | `chrome/android/java/src/org/chromium/chrome/browser/compositor/layouts/LayoutManagerChrome.java` — `showLayout(LayoutType.HUB, animate)` (155 में switcher **Hub** layout का हिस्सा है; `LayoutType.HUB = 2`) | `animate=false` से तुरंत खुलेगा; tabs=0 या hub-disabled (`isHubEnabled()`) स्थितियाँ अलग संभालनी होंगी |
| Thumbnails mask करना | `chrome/browser/tab_ui/android/java/src/org/chromium/chrome/browser/tab_ui/TabContentManager.java` — `getTabThumbnailWithCallback(...)` (एकल प्रवेश-द्वार का उम्मीदवार) | lock के दौरान null/placeholder लौटाना; titles/favicons का mask और उन सभी रास्तों की जाँच **बाकी** |
| Settings toggle | Privacy settings की Java फ़ाइल और `privacy_preferences.xml` का सटीक 155 path **अभी नहीं मिला** (मेरा पहला अनुमान 404 था) | GN/listing से खोजना है; अंदाज़े से patch नहीं लिखा जाएगा |
| UI थ्रेड/समय | LOCK का `showLayout` UI thread पर; camera frames background thread पर; policy में timer (`nextDeadlineMs`) | latency मापना बाकी |
