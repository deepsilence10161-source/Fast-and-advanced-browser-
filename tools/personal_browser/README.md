# Persistent personal browser — opt-in native source layer

**19 अक्तूबर 2026 · source development only · कोई privacy APK नहीं।**

उपयोगकर्ता का अनुबंध: Android browser में सामान्य profile/login/site data टिके; Android accounts, दूसरे apps, shared storage और backup में स्वतः न जाए। Incognito/session-wipe विकल्प नहीं है। Privacy पहले, AI बाद में। मुख्य नीति और native acceptance: [`docs/plans/personal-browser-containment.md`](../../docs/plans/personal-browser-containment.md)।

## इस directory और patch layer का काम

- `../../patches/personal/0100-personal-source-guard.py`: छह pinned155 source files के SHA-256 और दो नए output paths की अनुपस्थिति जाँचता है। Drift, symlink, missing input या पहले से applied layer पर refuse। Source-only guard; installed data से कोई संबंध नहीं।
- `../../patches/personal/0101-persistent-account-boundary.patch`: आठ source files का native patch; account-provider backend को अलग empty/denied implementation, Java sign-in entry points को reject, manifest backup/extraction/provider-grant policy और web-form IME hint।
- `prepare.py`: ordinary Swiftra series + opt-in personal series को **नई development bundle directory** में compose करता है। अलग package और `personal-...` variant स्पष्ट देना ज़रूरी; `com.swiftra.app`, Chrome-family packages, existing output और `a1/b1` स्वीकार नहीं।
- `host_probe.py`: असली patched facade/provider और pinned `AccountManagerFacade` interface को host JDK पर compile/execute करता है। Android, Chromium scheduler/Promise और अन्य dependencies **stubs** हैं। यह ART/Binder/native Sync/Android/browser E2E नहीं है।
- `upstream-155.0.8059.80.json.gz`: सात छोटे public source test inputs, reproducible gzip; full Chromium checkout नहीं।
- `upstream-index.json`: public source URLs/hashes, unsuccessful paths और fixture hash। `READ` का अर्थ fetched source है; हर पंक्ति की पूर्ण security audit या runtime proof नहीं।
- `UPSTREAM_LICENSE`: pinned Chromium BSD-style fixture licence। Upstream headers/credits नहीं हटाए गए।

साधारण `patches/series`, `patches/args.gn`, signer pin, product build workflows और मौजूदा `com.swiftra.app` अपरिवर्तित हैं। केवल host unit workflow में `jinja2` dependency जोड़ी गई। Personal layer को अभी existing builder/publisher में स्वतः नहीं जोड़ा गया है।

## Development-only उपयोग

नीचे का package केवल synthetic **उदाहरण** है—उपयोगकर्ता का चुना हुआ application ID या migration निर्णय नहीं। `--output` का parent पहले से मौजूद और output स्वयं अनुपस्थित हो:

```sh
python3 tools/personal_browser/prepare.py \
  --package org.example.containmentdev \
  --variant personal-source-review \
  --output .cache/personal-source-bundle
```

Generated layout में `patches/` और `adblock/swiftra-ruleset.pb.gz` दोनों हैं: ordinary `0013` transform की relative dependency सुरक्षित रहती है। Existing public signing-certificate pin byte-for-byte copy होता है; **private key/password copy या generate नहीं होते**। Receipt `PERSONAL_SOURCE_ONLY.json` में हमेशा `release_ready=false`, `apk_built=false`, `ci_wired_or_dispatched=false` और `product_containment=NOT RUN / NOT CERTIFIED` रहता है।

Bundle को final product न मानें। बाद का CI integration reviewed अलग package/state, सही application label, personal update-channel policy, merged APK binding और actual native tests माँगेगा। Ordinary Swiftra update feed को इस अलग package का सुरक्षित update channel मानना गलत है।

नई pristine Chromium source tree पर existing patch engine composed bundle लगा सकता है; वह केवल source लिखता है, कोई build/install नहीं करता:

```sh
python3 scripts/ci/patches.py apply \
  PRISTINE_CHROMIUM_SRC .cache/personal-source-bundle/patches - \
  .cache/personal-source-state.json
```

`PRISTINE_CHROMIUM_SRC` को वास्तविक अलग development checkout से बदलें; existing patched source tree या device/app-data directory नहीं। Tests छोटे pinned fixtures पर यही patch layer और patch-engine integration जाँचते हैं, full source build नहीं।

## वास्तव में जाँचा गया

- Pinned source पर native patch dry-run और apply, **fuzz=0 / offset=0**।
- Source guard के drift/missing/symlink/existing-output negative controls और patch-engine touched-files/epoch tracking।
- Facade/provider + वास्तविक pinned interface का `javac -Xlint:all -Werror` compile और host JVM execution: **29 assertions**। Empty immutable roster, no token success, main-thread Add Account callback, denied credentials, completion/no-hang, test override/reset।
- तीन mutation controls: Intent बनाने की कोशिश, गलत auth-error और dropped completion—host probe rejects। Stubs की सीमाएँ बनी रहती हैं।
- **20 synthetic Jinja configurations**: पाँच channels × backup-key absent/present × split definitions false/true। `tools:node=remove` tombstones को host model में हटाकर policy जाँची। **यह वास्तविक Android manifest merger, dependent manifests या binary APK नहीं है।**
- Reproducible separate bundles, existing data/output preservation, package/state/debug/signer refusal tests।
- Final focused: **134 passed in 4.79s** (66 native-source/host tests + 66 static manifest tests + 2 existing APK-audit tests)।
- Full host suite: **431 passed, 8 skipped in 128.41s**; Python compilation PASS। प्रारम्भिक failures और fixes `TESTING.md` में सुरक्षित हैं।

## जो इस layer से पूरा नहीं होता

- सभी external intents, Share/Print/Cast, clipboard text, system autofill/credential/passkey APIs और native account paths। Permissions/providers अकेले पूर्ण IPC isolation नहीं हैं।
- App-internal downloads, file-picker/viewer policy, storage paths, full-profile/SQLite/WAL/LevelDB/cache encryption और key-failure acceptance।
- Omnibox/native editor IME, screenshots/recents, network/telemetry audit, same-APK speed और website compatibility। IME hint से keyboard की offline compliance enforce नहीं होती।
- Actual retention/restart, backup/restore/D2D/OEM/iOS behavior, x64 Actions + native ARM64 Redroid, physical phone और user-present account acceptance।

**GitHub authenticated requests अभी HTTP401 देते हैं; CI dispatch और publication blocked हैं।** कोई नया build/install, profile reset, account access, paid resource या production-data deletion नहीं किया गया।
