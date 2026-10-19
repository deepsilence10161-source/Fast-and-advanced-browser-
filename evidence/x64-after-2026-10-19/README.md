# x64 emulator E2E on the APK with all speed/security patches (run 39185114548, commit aea2608)

APK: build 39145132480 (sha256 2bd84b64...c942; patches 0010-0013, 0016, 0015, 0017). Android x86_64 emulator
(GitHub Actions standard runner). Status per gate = the result line in the files here.

| Gate | Result | Before (0011 APK) |
|---|---|---|
| ADBLOCK_E2E | PASS verdict=blocked | FAIL (ad blocker not in that APK) |
| CREDITS_E2E | PASS complete (770 entries, adblock + boringssl licences) | FAIL |
| DOWNLOAD_SHIELD_E2E | PASS canary=blocked_dialog redirect=blocked_dialog clean=downloaded | FAIL (0015 not in that APK) |
| FINGERPRINT_E2E | PASS shielded | PASS |
| ADVANCED_E2E / SHIELD_E2E / STARTUP_NETLOG | PASS | PASS |
| ART_STARTUP | install 780 / profile 701 / speed 732 ms (cold medians) | x64 2234 -> 2266 ms (different emulator session; cross-run, not an A/B) |
| STARTUP_TRACE | NOT_CAPTURED (trace file not written) | 1101 ms |
| SPEED_E2E | NOT RUN: exit 124 (timeout). DevTools stopped answering in the first mode, then every adb call timed out; same pattern in run 39185979151 | measured |

The speed harness was changed after this run (progress lines, thread stacks + full logcat on the first DevTools
failure, per-mode time budget, alternating mode order); the speed numbers will come from the next run.
