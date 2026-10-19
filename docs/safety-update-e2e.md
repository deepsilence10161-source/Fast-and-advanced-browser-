# Safety check: signed update status acceptance (2026-10-19)

Scope: handoff §9.2, patches `0005` v2 and `0020`. This is an additional native Android test, not a new APK/source patch, and not proof of feature/UI parity with current Chrome.

## Research before implementation

Checked against Chromium tag **155.0.8059.80** on 2026-10-19:

| Primary source | Supported observation | Limit |
|---|---|---|
| [SafetyHubUpdateCheckModuleMediator.java](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/safety_hub/android/java/src/org/chromium/chrome/browser/safety_hub/SafetyHubUpdateCheckModuleMediator.java) | `null` gives unavailable; `NONE` gives up-to-date; installed version is the update row's summary | Upstream has no Swiftra signed channel; downstream patch 0005 must be applied |
| [SafetyHubFetchService.java](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/safety_hub/android/java/src/org/chromium/chrome/browser/safety_hub/SafetyHubFetchService.java) | The native service subscribes to `UpdateStatusProvider` and notifies mediators on completion | Source is not runtime evidence |
| [UpdateStatusProvider.java](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/omaha/android/java/src/org/chromium/chrome/browser/omaha/UpdateStatusProvider.java) | Status is calculated asynchronously once per process, so every fixture requires a stopped/restarted app | Downstream patch 0020 supplies actual verification/cache semantics |
| [SafetyHubFragment.java](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/safety_hub/android/java/src/org/chromium/chrome/browser/safety_hub/SafetyHubFragment.java) | The Safety check page owns an `update_check` native preference | Capture/navigation still need to be tested on each ABI |
| [android_chrome_strings.grd](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/ui/android/strings/android_chrome_strings.grd) | Exact source messages: `IDS_SAFETY_CHECK_UPDATES_UPDATED`, `IDS_SAFETY_HUB_UPDATE_UNAVAILABLE_TITLE`, `IDS_SAFETY_HUB_VERSION_SUMMARY` | English native CI; other locale/accessibility coverage remains separate |

Pristine-tag `patch --dry-run --fuzz=0`: both 0005 and 0020 applied without fuzz locally. This is **PASS (static only)**, not an Android pass.

## Cases and evidence requirements

| Case | Fixture | Required native result and independent evidence |
|---|---|---|
| bad_fresh | No previous verified check; signed public fixture changed by one byte | Can't check Swiftra version; both JSON and signature fetched; app logs bad-signature rejection; no timestamp written |
| good_production | Remove only update cache entries, then use the app's **normal production HTTPS endpoint**, not test switch | Swiftra is up to date + installed version; app itself writes a fresh `last_ok` after signature verification. The harness never seeds the positive timestamp |
| bad_recent | A real successful production check, then tampered test request | Up to date remains valid within the documented 48-hour grace period; rejected request cannot write a new verification time |
| bad_stale | Previously verified timestamp moved beyond 48 hours, then tampered request | Can't check version; rejected signature cannot refresh an expired check |
| bad_future | Previous timestamp moved into the future, then tampered request | Can't check version; clock rollback cannot create a valid recent check |

All cases require the native Safety check title, unambiguous visible update state, installed-version summary and no dead `Go to Google Play` button. Native XML and screenshots are captured only on the no-account settings page; browser navigation uses `about:blank`. No real login, cookie or account is used.

A tampered request **does not** erase a genuine recent success. Claiming "every tampered request must show can't check" would contradict patch 0005's explicitly allowed 48-hour cache.

## Safety and release gates

- Root is for disposable Actions Android emulator/Redroid fixture control only, not a product dependency and never a physical-device pass. The harness now refuses unknown/physical `ro.hardware` before requesting root or installing anything.
- Only `swiftra_update_*` XML entries are modified; unrelated settings and the wrapped OSCrypt key are preserved. Private prefs are never printed, placed in argv, or saved in artifacts.
- Every edit happens with the app stopped. Original update entries are restored; failed restoration prevents PASS. An AtomicFile `.bak` causes a refusal rather than an ambiguous fixture.
- Full `run_capture.sh` includes the test. Builds containing **both** 0005 and 0020 must produce `SAFETY_UPDATE_E2E PASS` to publish. Missing/NOT_RUN/FAIL blocks the new APK; the existing release is retained.
- Both existing workflows have an optional `checks=safety_update` mode. It installs the unchanged source APK and completes no-account first run, then runs only this focused acceptance. **It never publishes**, and is not a substitute for the full release gate.
- This test does **not tap the update download button**. Its intent/download behavior remains separate and NOT RUN; menu visibility alone is not proof that tapping downloads the APK.

## Status

Current focused x64 result: [39273364869](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39273364869), driver `ff4944e`: **PASS (Android emulator), 5/5, restored=True**, API 36/x86_64. All JSON, XML and screenshots were inspected; both `current` modules were genuinely expanded and showed the exact installed version. Installed source APK SHA-256 `b1ea03ea9e77da9573ef5ad96c2078135acfe678c7ad1abee6feb4fddcaa11ff` was checked against BUILD_INFO before installation. This is focused evidence, not the full release suite, physical-device/account acceptance, or update-button tap/download proof. The publish job was **skipped**, as intended.

Pinned CI unit run `39273365779` at `ff4944e`: **259 passed, 1 skipped in 124.54s**; local relevant suite **88 passed in 0.27s**. Initial full local suite after the original integration was `199 passed, 8 skipped in 123.33s`; later full local coverage and failed-run chronology are retained below.

On builds declaring 0021, focused mode now follows successful Safety restoration with the real loopback cookie Keystore E2E on that **same profile**. Its postcondition requires `sw1`, no plaintext/token in DB, wrapped pref, restart-cookie recovery and Keystore2. It does not trust the legacy script's exit 0 alone (NOT_RUN also returns 0). This extra probe is pending new x64/arm64 focused runs; it is not retroactively claimed for run 39273364869.

The first full local run was **2 failed, 197 passed, 8 skipped**: the focused ARM publish guard had not yet been added, and the A/B workflow assertion expected the old (non-focused-aware) condition. Both were corrected before any push/dispatch. This is harness development history, not an Android-app failure.

First focused x64 run [39264127317](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39264127317), commit `acf1bf0`, stopped in setup: `SAFETY_UPDATE_E2E NOT_RUN cases=0/5 restored=False ParseError (private details withheld)`. No update prefs had been modified. The blocker is in the harness, not an established browser failure. The follow-up backgrounds the Activity before force-stop and records only parse metadata (size/type/position), never private XML. The exact cause remains unconfirmed until a corrected run.

Research for that follow-up: AOSP Android 16 [SharedPreferencesImpl.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/app/SharedPreferencesImpl.java) uses queued asynchronous writes and a backup file; [XmlUtils.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/com/android/internal/util/XmlUtils.java) writes prefs with `Xml.newFastSerializer()`, and [Xml.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/util/Xml.java) returns the text FastXmlSerializer for that method. Therefore binary XML is **not** assumed to explain this failure. Checked 2026-10-19.

Second focused run [39265508902](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39265508902), `490ea11`: `SAFETY_UPDATE_E2E NOT_RUN cases=0/5 restored=False stage=read_original_prefs prefs parse refused: bytes=43894 format=xml code=14 position=(23, 66) controls=0`. Backgrounding did not solve it. Expat code 14 means **reference to invalid character number**, not a raw binary/control byte. AOSP's actual [FastXmlSerializer.java in modules-utils](https://android.googlesource.com/platform/frameworks/libs/modules-utils/+/refs/tags/android-16.0.0_r1/java/com/android/internal/util/FastXmlSerializer.java) explicitly emits `&#0;` through `&#31;` inside Java strings. XML-1.0 ElementTree rejects the forbidden references, while Android uses that representation for preferences.

The corrective codec decodes only those Android control references in memory, preserving unrelated values and wrapped-key strings; on serialization it puts every forbidden control back into Android's numeric-reference form before writing. No characters are dropped and no private preference excerpts are logged. DOCTYPE/ENTITY/CDATA and invalid tag-name repairs are refused, not silently recovered. Unit coverage includes all 29 XML-1.0-forbidden values in 0..31, decimal/hex references, literal `&amp;#0;`, Unicode, marker collisions, original-update-entry restoration and unrelated/wrapped-key preservation. Android outcome is still pending a new run.

Third focused run [39266966087](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39266966087), `6fd3e52`: initial prefs parsing succeeded, but the first `exec-in` write read back as an empty file at `bad_fresh:prepare`; `NOT_RUN cases=0/5 restored=False`. This was only the disposable no-account CI emulator. The original truncate-in-place transport was not sufficiently safe.

Corrective IO: use `adb shell -T` with stdin and remote-exit acknowledgement, stage a separate private temporary file, verify bytes and uid/gid/mode/SELinux label, then atomic rename. Failure before verification cannot truncate the original; the temporary file is removed. Command-line flags also use the checked stdin path and byte round-trip. The physical-device hardware guard runs before root/install. Desktop functional tests exercise successful replacement, dropped-stdin and changed-metadata refusals with the original intact. Relevant local suite: **78 passed**; earlier full suite after the codec: **235 passed, 8 skipped in 123.76s**. This is still not an Android PASS.

Primary IO research: Android's [adb commandline.cpp](https://android.googlesource.com/platform/packages/modules/adb/+/refs/tags/android-16.0.0_r1/client/commandline.cpp) implements `exec-in` as a one-way `copy_to_file()` with no remote-exit result, whereas the [adb shell manual](https://android.googlesource.com/platform/packages/modules/adb/+/refs/tags/android-16.0.0_r1/docs/user/adb.1.md) documents `-T` (no pty) and remote exit/stdout/stderr protocol (unless disabled with `-x`). Checked 2026-10-19. The exact low-level reason for the observed empty write was not traced; the unsafe/unacknowledged path was removed rather than assumed reliable.

Fourth focused run [39268484164](https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/actions/runs/39268484164), `07a332f`: **FAIL, 3/5 cases, restored=True**. All five native row states matched their expected states, and the production case wrote its genuine successful-verification timestamp. The two `current` cases still failed the required visible-version assertion: the real native safe module was collapsed. [SafetyHubExpandablePreference.java](https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/chrome/browser/safety_hub/android/java/src/org/chromium/chrome/browser/safety_hub/SafetyHubExpandablePreference.java) explicitly shows its summary only while expanded, and `onClick()` toggles expansion. The corrected test taps the real native current-row header, then still requires the visible exact installed version. It does not weaken the assertion or alter browser UI. The original failed JSON and collapsed screenshot are retained in evidence.

Two additional local negative controls exposed codec edge cases before this rerun: a legal numeric reference could hide a literal placeholder prefix, and raw legal CR would normalize to LF on reparsing. The prefix search now checks the numeric-decoded representation too; CR is re-escaped alongside forbidden controls. All 32 Android controls are tested in text and attributes. Before emitting fixture bytes, an in-memory whole-tree semantic round-trip invariant refuses any change with a fixed, private-data-free error.

Physical-device refusal is now side-effect free in `finally` too (no force-stop/flags/reverse cleanup after refusal). The wrapper checks actual BUILD_INFO for **both 0005 and 0020**: unsupported older/baseline APKs get NOT_RUN, not a false browser FAIL. This does not relax the release gate for supported APKs. Original command-line flags are still removed rather than restored on eligible disposable CI devices; cleanup improvement remains open.

## Separate static risk: update-button intent (not yet runtime tested)

The tag's `UpdateStatusProvider.startIntentUpdate()` adds `FLAG_ACTIVITY_REQUIRE_NON_BROWSER`, inherited from upstream's Play Store path. Patch 0020 changes the offer to an HTTPS GitHub release URL but currently leaves this flag unchanged. Android's [official Intent reference](https://developer.android.com/reference/android/content/Intent#FLAG_ACTIVITY_REQUIRE_NON_BROWSER), checked 2026-10-19, says it throws `ActivityNotFoundException` if no non-browser handler resolves the URL. Therefore a device with only browsers may have no working update-button handler; the upstream catch returns false. This is a **source-supported risk**, not a reproduced device result. A safe tap/intent/download acceptance test and an ABI source build are still needed before claiming a fix. Do not infer working downloads from the existing menu/badge visibility test.
