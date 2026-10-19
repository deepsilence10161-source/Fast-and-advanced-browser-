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

प्रमाण: `evidence/safety-update-2026-10-19/startup-history.json` में पूरे SHA और source job URLs; `startup-history-markers.txt` में exact timestamped log lines। **Status: historical Android emulator observations only; new 0021 performance acceptance NOT RUN / BLOCKED.**
