# c1 सत्यता fixes — evidence (2026-10-17)

| | build (x64 / arm64) | E2E (x64 / arm64) |
|---|---|---|
| before (1f2788f harness, b2 APK) | 38935765027 / 38931729325 | 38989201196 / 38989202816 |
| after ae8c946 (patch hash 43c2a6b03a23) | 38991582517 / 38991583759 | 38993002550 / **38994313725** (rerun) |

arm64 का पहला run 38993004513: Redroid container का graphics stack ढहा — 02:09:13 से launcher3/systemui/Swiftra सभी के
RenderThread abort ("drawRenderNode called on a context with no surface", ANGLE EGL init) → device_checks 6/9। पहला abort
launcher3 (Swiftra नहीं); उसी APK पर rerun 38994313725: 9/9, crash 0। `arm64_env_failure_38993004513/` में सारांश।

| Check | before | after x64 | after arm64 (rerun) |
|---|---|---|---|
| false_claims (truth scan) | x64 4 / arm64 6 | 0 | 0 |
| expected texts | — | copyright_chromium_authors, update_cant_check | same |
| branding_leaks | 0 / 0 | 0 | 0 |
| device_checks | 9/9 | 9/9 | 9/9 |
| chat | 10/10 | 10/10 | 10/10 |
| crash / ANR | 0 / 0 | 0 / 0 | 0 / 0 |
| cold / warm median ms | — | 711.5 / 604 | 699.5 / 247 |

ae8c946 screenshot से नई खोज: Safety check "Can’t check Swiftra version" card पर "Go to Google Play" (non-branded में no-op,
dead button) — 0005 के अगले संस्करण में छिपाया; scanner नियम `dead_play_button` (ae8c946 artifacts पर 2 hits)।
arm64 = Redroid container, software GPU — NOT a real phone।
