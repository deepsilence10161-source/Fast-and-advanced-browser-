# Persistent personal browser — native source development

**19 अक्तूबर 2026 · Android APK / privacy acceptance अभी NOT RUN।**

अनुबंध: सामान्य browser profile/login/site data टिके; automatic Android account-link, दूसरे apps/shared storage/backup exports बन्द हों। Incognito या profile auto-wipe नहीं। Privacy पहले, AI बाद में। मुख्य नीति/acceptance: [`personal-browser-containment.md`](../../docs/plans/personal-browser-containment.md)।

## Source layers

| Layer | Source changes | प्रमाण की सीमा |
|---|---|---|
| `0100` guard + `0101` patch | आठ-file account/sign-in/manifest/IME layer; no platform delegate, completed denial callbacks, backup exclusions/provider grants | pinned-source apply; account facade/provider + real interface host JVM; Android dependencies stubs |
| `0102` guard + `0103` patch | 17-file egress/storage/clipboard/window layer; private download root, native path guards, public publish/system-downloader denial, URL/Share/viewer controls, browser-private clipboard, secure-window controls | source apply; actual C++ predicate with sanitizers; three actual Java classes with dependency stubs; not full Android compile |

दोनों मिलाकर **25 source files**, 21 prerequisite-file hashes और चार absent-output guards। Ordinary `patches/series`, `patches/args.gn` और existing public signer pin नहीं बदले। Optional build-script branch केवल explicit personal inputs पर चुनी जाती है। Existing Swiftra/profile/device data नहीं छुआ।

### महत्त्वपूर्ण व्यवहार

- Downloads: `<app-internal data directory>/Downloads` (आम Chrome layout में `app_chrome/Downloads`), cache/SD/public Downloads नहीं। Preference/policy से बाहरी path चुनने पर containment policy लागू; root failure पर दूसरे storage domain में fallback नहीं। Native checks reservation, path substitution और final-success metadata से पहले हैं।
- MediaStore publish/copy/open/rename तथा legacy Android DownloadManager handoff deny। OMA/legacy requests cookie/referrer copying से पहले reject। Existing `addCompletedDownload` पहले से invalid system ID लौटाता था—उस पुराने no-op को नया fix नहीं कहा।
- सामान्य HTTP(S) tab navigation बनी रहती है; external intent schemes/app/WebAPK handoffs बन्द। System Share cancelled callback देता है, “shared successfully” नहीं। Internal media viewer own-package pinned; Share/Open-with flags false। Unsupported viewers/installer/Files fallback बन्द होने से कुछ files/flows नहीं खुलेंगे।
- `BrowserContainedClipboard` Android ClipboardManager/file URI provider आरम्भ नहीं करता। Text/HTML/custom text और raw PNG-signature buffers browser process में रहते हैं। Focus loss पर साफ़ नहीं होते। **यह RAM clipboard है, durable vault नहीं**; process death पर clipboard खो सकता है। URI/files और अन्य image-format copy अभी supported नहीं; native Android widgets/IME clipboard paths अलग remaining gate हैं। Profile/cookies/history/download files इससे delete नहीं होते।
- FLAG_SECURE/recents policy normal/incognito transition में बनी रहे, इसका source control है; root-view autofill/content-capture hints भी हैं। **Hints सभी explicit system autofill/credential APIs को block करने का प्रमाण नहीं।** Mock window tests, वास्तविक screenshot/recording tests नहीं हैं।

## Development build — अब अलग manual workflow तैयार है

`.github/workflows/personal-source-build.yml`: explicit अलग package, `personal-...` state, विकास-स्थिति की confirmation, दोनों ABI का चयन, केवल standard free runners। Reusable stages default में सामान्य path ही रखते हैं। Signing secrets पहले जैसे केवल signing step को मिलते हैं; नई keys नहीं बनतीं।

**यह workflow अभी GitHub पर प्रकाशित/dispatch/run नहीं हुआ**: authenticated HTTP401 blocker कायम है। Build होना भी privacy E2E PASS नहीं होगा। Personal `BUILD_INFO` में development marker/NOT CERTIFIED आएगा; ordinary Swiftra release gate marker अथवा personal patch देखकर reject करता है, भले दूसरे synthetic markers PASS हों। Dedicated personal runtime/release acceptance अभी बाकी है।

### केवल source bundle बनाना

यह package केवल **synthetic उदाहरण** है, उपयोगकर्ता का अंतिम application ID या migration निर्णय नहीं। Output अनुपस्थित हो और parent directory मौजूद हो:

```sh
python3 tools/personal_browser/prepare.py \
  --package org.example.containmentdev \
  --variant personal-source-review \
  --output .cache/personal-source-bundle
```

Bundle में base patches/overlay/public signer pin और `0013` की relative `adblock/swiftra-ruleset.pb.gz` dependency सुरक्षित हैं। No key/password copy/generation, कोई build/install/dispatch नहीं। Schema2 receipt: `release_ready=false`, `apk_built=false`, `ci_dispatch_performed_by_this_tool=false`; `ci_run_status` input-preparation tool द्वारा **NOT ASSESSED** है। Local workflow-file existence को actual GitHub run नहीं माना गया।

नई अलग pristine development checkout पर source apply:

```sh
python3 scripts/ci/patches.py apply \
  PRISTINE_CHROMIUM_SRC .cache/personal-source-bundle/patches - \
  .cache/personal-source-state.json
```

`PRISTINE_CHROMIUM_SRC` वास्तविक अलग source checkout होगा—existing patched source/profile/device-data directory नहीं। यह command compile/install नहीं करती।

## Tests और provenance

- `upstream-155.0.8059.80.json.gz` में सात और `egress-upstream-155.0.8059.80.json.gz` में 15 public source slices; full checkout नहीं। दोनों indexes में exact URLs/hashes और unsuccessful paths सुरक्षित हैं। `FETCHED` / पुराना `READ` = retrieved/hash, हर पंक्ति की पूर्ण audit या runtime proof नहीं। Fixture licence `UPSTREAM_LICENSE`।
- `source_fixture.py`: byte/source hash verification और strict source apply, fuzz0/offset0।
- `host_probe.py`: real account facade/provider/interface, host **29 assertions**, dependencies stubs।
- `egress_host_probe.py`: real Clipboard/private subclass/snapshot controller, host **40 assertions**, Android/JNI stubs। Platform-backend/array-alias/secure-flag mutations reject।
- वही tool actual production C++ path predicate को **ASan + UBSan** से compile/run करता है: **6,030 adversarial inputs**, कोई Android/download filesystem operation नहीं। Sibling-prefix mutation reject। Lexical predicate proof, filesystem ownership/races/permissions/encryption का proof नहीं।
- Source policy tests, 20 synthetic Jinja configs, guard drift/missing inputs, source-engine integration, deterministic bundles, actual shell input-lane selection/refusal और ordinary-release exclusion। Native main activity/download classes का full Android compile अभी नहीं हुआ।
- Current focused **233 passed in 9.77s**; Python/shell syntax PASS। Full host suite **522 passed, 8 skipped in 127.19s**। पुराने optional-fixture skips; नया test skipped नहीं। Failures/fixes `TESTING.md` और दोनों phase-evidence records में सुरक्षित हैं।

## अभी समाप्त नहीं

Actual x64 Actions + native ARM64 Redroid; retention/crash/restart, real IPC/backup/MediaStore/SD/clipboard/screenshot traps; full-profile encryption/key failure; explicit OS autofill/credential/passkey/Print/Cast/other intent paths; notifications/background network audit; native UI/compatibility/performance; personal package/label/update-channel and dedicated release gates; physical user-present account acceptance।

Original Swiftra/Chrome-parity/Arena scope अलग जस का तस है। न host tests को Android PASS कहा, न पुराने APK को नया private browser। किसी real account, unrelated connected app, paid resource या production-data wipe का उपयोग नहीं हुआ।
