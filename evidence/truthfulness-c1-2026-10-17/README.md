# c1 सत्यता fixes — evidence (2026-10-17)

| | build (x64 / arm64) | E2E (x64 / arm64) |
|---|---|---|
| before (1f2788f harness, b2 APK) | 38935765027 / 38931729325 | 38989201196 / 38989202816 |
| after ae8c946 (patch hash 43c2a6b03a23) | 38991582517 / 38991583759 | 38993002550 / **38994313725** (rerun) |
| **final 1df130a** (patch hash e1c3ab189907) | **38995292721 / 38995294189** | **38996588758 / 38996590010** |

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

## final 1df130a (0005 + dead button fix)
| Check | x64 (emulator API 36) | arm64 (Redroid 14) |
|---|---|---|
| false_claims (dead_play_button सहित 4 नियम) | 0 | 0 |
| expected texts | copyright_chromium_authors, update_cant_check | same |
| branding_leaks | 0 | 0 |
| device_checks / chat | 9/9 / 10/10 | 9/9 / 10/10 |
| crash / ANR | 0 / 0 | 0 / 0 |
| cold / warm median ms | 1238 / 1050.5 (emulator variance; ae8c946 पर 711.5/604) | 720.5 / 246.5 |
| Settings पन्ने capture | 15/18 (Sign in skip; Default browser, Notifications = system UI) | 15/17 |
| APK SHA-256 (= BUILD_INFO = state-release asset) | `ce52a4bfbd0634154eed3cb63b797f3059c3d30cfbba5c62f4804e350c74a155` | `827485c03fbea787977ba0fb77af1ca884e5c7239bbf13a2da88d5da44d7660f` |

पिछले (b2-final) state-release APKs: x64 `5233be2661f2fa706141fe5620d2a02d1c7a0514708eb178f17de7f3dcae49f4` (38935765027),
arm64 `7d1ee676c258510bfed2a3bd1baf72a923c61a5ed395d7a4812b2b54faa92572` (38931729325)।
