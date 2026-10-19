# 0021 Keystore: startup की ऐतिहासिक निगरानी (19-10-2026)

हैंडऑफ़ §9.3 का अगला diagnostic: तीन पुराने x64 emulator runs के **असली job logs** इस session में पढ़े गए। कोई नया performance run इस तालिका में नहीं जोड़ा गया है। नया focused Safety check run startup benchmark का विकल्प नहीं है।

| पुराना E2E run | APK SHA-256 (आरंभ) | STARTUP_TRACE `TotalTime` | ART `install` median | ART `profile` / `speed` | Keystore marker |
|---|---|---:|---:|---:|---|
| [39218924046](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39218924046/job/117949356320) | `2bd84b64401f` | 819 ms | 1842 ms | 1854 / 1746 ms | उस log में दर्ज नहीं |
| [39234628268](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39234628268/job/118000622212) | `b8f6a934ebe9` | 1061 ms | 2196 ms | 2138 / 2228 ms | `KEYSTORE_E2E NOT_RUN prefix=v10 ... wrapped_pref=False` |
| [39249911374](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39249911374/job/118050897372) | `b1ea03ea9e77` | 966 ms | 2224 ms | 2144 / 2065 ms | `KEYSTORE_E2E PASS prefix=sw1 ... cookie_after_restart=True` |

## मापा गया तथ्य बनाम निष्कर्ष

- `819 → 966` देखना अकेला पर्याप्त नहीं: इनके बीच **1061 ms** वाला run भी है। पहले और अंतिम ART install medians भी `1842 → 2224` बदले।
- सबसे हाल के दो runs: trace ratio `966/1061 = 0.9105`; ART install ratio `2224/2196 = 1.0128`; ratio-of-ratios `0.8990`। यह केवल diagnostic है, किसी confounder का प्रमाणित correction नहीं।
- `STARTUP_TRACE` का `TotalTime` एक launch का sample है। `ART_STARTUP` का install पाँच cold launches का median है, जो बाद में `cmd package compile --reset` के बाद मापा गया। दोनों एक ही समय/compile state का माप नहीं हैं। Source: `scripts/ci/startup_trace.py`, `scripts/ci/art_startup.py`।
- तीनों APK SHA अलग हैं। साझा CI host/scheduling, पहले के workload, compilation और अन्य source changes भी अलग हो सकते हैं। यह same-APK A/B नहीं है और केवल 0021 का causal effect अलग नहीं करता।
- इसलिए **Keystore से startup regression सिद्ध नहीं**, और **Keystore ने startup तेज़ किया** भी सिद्ध नहीं। पुराने handoff के noisy comparison को product-speed claim न बनाएँ।

## अगली मापन शर्तें

1. नए full x64/arm64 runs से startup trace, ART baseline, tested APK SHA और feature markers साथ रखें; focused safety runs को इस गिनती में न रखें।
2. Android native arm64 Redroid को physical phone न कहें। वास्तविक फ़ोन/current installed Chrome की तुलना अभी अलग gate है।
3. किसी नए speed lever का दावा same-APK, alternating controlled A/B और पर्याप्त trials के बाद ही। TLS, sandbox या encryption कमज़ोर करके लाभ न दिखाएँ।
4. Crypto failure को public-key fallback या credential deletion से छिपाने के बजाय fail-closed correctness भी जाँची जाए।

प्रमाण: `evidence/safety-update-2026-10-19/startup-history.json` में पूरे SHA और source job URLs; `startup-history-markers.txt` में exact timestamped log lines। ऊपर की तालिका केवल ऐतिहासिक x64 observations है।

## अब उपलब्ध नया full ARM64 run — मिश्रित परिणाम, regression छिपाएँ नहीं

Full native Redroid run **39274414134** के वास्तविक artifact में source APK `a3df4cf7…248f02`, Safety 5/5, `KEYSTORE_E2E PASS sw1`, device checks 9/0 और मौजूदा `E2E_GATE PASS` हैं। **यह gate measured performance की उपस्थिति स्वीकार करता है; इससे हर metric में improvement/no-regression सिद्ध नहीं होता।**

- नया ARM trace `TotalTime=825 ms`; ART पाँच-launch medians: **1098 / 1069 / 1133 ms** (install/profile/speed), gains **+2.6% / −3.2%**। केवल `speed` compile करना अपने-आप तेज़ नहीं था।
- पुराना ARM **39240241640**: trace **798 ms**, ART **1036 / 944 / 1079 ms**, `KEYSTORE_E2E NOT_RUN prefix=v10 wrapped_pref=False`। दोनों अलग APK/hosts हैं। इन ratios को causal Keystore cost या correction न कहें।

### उसी host का alternating अलग-APK baseline (0011)

क्रम `new,base,new,base`; हर candidate के 6 cold launches। नया SHA `a3df4cf7…248f02`, baseline `8954118e…3714fd`।

| metric | नया | पुराना 0011 | नया समय परिवर्तन |
|---|---:|---:|---:|
| cold launch | 750.0 ms | 694.5 ms | **+7.99% धीमा** |
| JS/DOM bench | 355.0 ms | 390.4 ms | −9.07% |
| fixture load | 677.5 ms | 882.0 ms | −23.19% |
| fixture LCP | 554.0 ms | 548.0 ms | **+1.09% धीमा** |

इस एक run में सभी छह new cold samples सभी छह baseline samples से बड़े थे। इसे अनदेखा नहीं किया गया। फिर भी कई source/features साथ बदले हैं: **सिर्फ Keystore को कारण कहना असमर्थित** होगा। और यह installed current Chrome benchmark नहीं है।

### Same-APK flags / fixture measurements

- Full-page load **1431.5 → 706 ms**, HTTP download **9.1 → 6.0 s**, shaped local H2 download **24.1 → 4.8 s**। यह नियंत्रित CI-local network है, आम इंटरनेट की सार्वभौमिक गति नहीं। Loads 6 vs 3, downloads 2 vs 1: छोटे/असमान samples।
- उसी test का LCP **556 → 620 ms (+11.51%)**, एक JS/DOM bench **366.1 → 387.7 ms (+5.90%)**। इसलिए बेहतर load/download देखकर uniform speed PASS न कहें।
- Cached-SPA, हर mode में cold/warm **12+12**: cold load **133.5 → 140.5 ms (+5.24%)**, warm load **124 → 124 ms**; warm LCP **264 → 230 ms**। LCPP candidate का warm load **132 ms** भी universal win नहीं है।

**Status: actual Android measurements, लेकिन uniform no-regression acceptance FAIL / further adjudication BLOCKED.** किसी speed lever/crypto setting को इस noisy mixed bundle के आधार पर अकेला culprit मानकर नहीं बदला गया; encryption/TLS/sandbox कमजोर नहीं किए गए। अगले निर्णय के लिए privacy/security समान रखते हुए isolated lever ablation, balanced repeated trials और physical/current-Chrome reference चाहिए।

Curated full artifact और दोबारा runnable release-gate proof: `evidence/safety-update-2026-10-19/arm64-full-run-39274414134/`। `performance-caveats.json` में summaries/limitations और `prior-arm-39240241640-markers.txt` में exact पुराने ARM markers हैं।
