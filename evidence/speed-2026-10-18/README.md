# Speed evidence index (2026-10-18)

Subfolders: `aa-0010/` (A/A calibration), `baseline-0010-arm64/`, `baseline-0010-x64/` (each has its own README),
`baseline-0011-arm64-39144748799/`, `art-startup-0010-*/`, `desktop-harness-cft156.json`.

## 0011 arm64 baseline, run 39144748799 (APK 8954118e, patches 0000-0011: no 0016 / 0017)

`SPEED_E2E MEASURED load_ms 1461->1440.5 lcp_ms 608->580.0 kib 887.1->887.1 download_s 9.1->9.1 conns 3->3
h2_download_s 24.1->24.1 h2_conns 1->1 bench_ms 394.5->395.3`: both modes are the same browser here (A/A within 1-5%).
The HTTP/2 download (24 MiB, server paced at 1 MiB/s per connection) took **24.1 s on one connection** in both modes.
That is the "before" number for patch 0017 (Turbo Download; model: about 5 connections, about 5 s). Bench was 394.5 ms
here vs 435 ms in the 0010 run on another runner: compare benches only within one run (A/B), not across runs.

## ART startup (is a baseline profile worth it?)

| Run | APK | install (`verify`) | `speed-profile` | `speed` |
|---|---|---|---|---|
| arm64 39143911192 | 0010 | 1037 ms | 948 ms (-8.6%) | 1005 ms |
| arm64 39144748799 | 0011 | 1038 ms | 996 ms (-4.0%) | 1074 ms |
| x64 39143906198 | 0010 | 2048 ms | 1940 ms (-5.3%) | 2077 ms |

Cold-start TotalTime medians of 5. A sideloaded install starts in `verify` until background dexopt; a profile-guided
compile makes first-day cold starts 4-9% faster. That is the gain a bundled baseline profile can deliver (profgen,
docs/speed-pack.md). A full `speed` compile is not faster (larger code, more page-in).

## speed_e2e timeouts in the a248fde runs (39143906198 / 39143911192, 0010 APKs)

Both hit the 1200 s limit. After a verified restart, every swiftra-mode load got "no browser websocket" and waited
60 s. Both modes were the same browser (0010), so this was a harness/environment issue. Fixed in cf26972: re-forward +
25 s poll, one verified restart per mode, `diag_<tag>.txt` (ANR/logcat), and failed loads no longer count toward
bytes/requests.
