# Speed A/A calibration on the 0010 APK (2026-10-18)

The 0010 APK has neither the ad blocker nor the Speed Pack, so `chromium_defaults` and `swiftra` modes must measure the
same. This run validates `scripts/ci/speed_e2e.py` before it is used on the 0011+/0012/0013/0015/0016 APKs.

| run | device | result |
|---|---|---|
| 39132156695 | arm64 Redroid | 2 of 4 restarts usable (one per mode). chromium_defaults: page load 1406 / 1438 ms, download 24 MiB in 9.10 s over 3 connections. swiftra: 1413 / 1436 / 1424 ms, 9.11 s over 3 connections. **A/A difference < 1 %**, as expected. The file reached `/sdcard/Download` complete (25,165,824 bytes) in both modes. |
| 39132154988 | x64 emulator | chromium_defaults: page load 2028 / 1926 / 2151 ms, download 9.37 s over 3 connections. Then a hung `screencap` (30 s timeout) raised and the script wrote no JSON. |

Harness defects found by this run and fixed before any APK comparison:
1. **655e988**: restart was not verified. A fixed 7 s wait missed DevTools on arm64 (2 restarts unreadable). An empty
   expected-flag list for `swiftra` mode made a stale `chromium_defaults` command line count as applied. Now: new browser
   PID required, DevTools polled, chrome://version opened with a nonce, the other mode's flags must be absent, and up
   to 3 attempts are made.
2. **655e988**: 1 of 6 page loads never opened its tab (0 server requests). The tab is now reopened once after 10 s.
3. **8055674**: one guarded `screenshot()` helper for shield/advanced/speed E2E. speed_e2e also catches errors per
   mode, writes JSON after every cycle and prints `PARTIAL` when only some restarts worked.

Files: `arm64-speed_e2e.json`, `arm64-speed_e2e.txt`, `x64-speed_e2e.txt`.
Status of the speed claim: **NOT RUN** on a Swiftra APK with the Speed Pack (the 0016 build is queued).
