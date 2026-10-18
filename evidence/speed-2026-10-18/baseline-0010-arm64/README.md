# arm64 baseline on the 0010 APK (no PGO, no orderfile, no Speed Pack): run 39134174533, harness b6eb27c

## CPU benchmark (`tools/speedpack/bench.js`, 5 runs per workload, median)
| run | total ms | dom | mapset | sort | json | parse | regex | hashing | objects | numeric | strings |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 435.1 | 158.4 | 114.3 | 56.1 | 48.7 | 14.8 | 13.1 | 12.1 | 10.4 | 4.5 | 2.7 |
| 2 | 444.4 | 163.2 | 118.3 | 56.8 | 48.6 | 15.1 | 13.0 | 12.2 | 10.1 | 4.3 | 2.8 |
| 3 | 434.9 | 159.9 | 113.2 | 55.9 | 48.6 | 14.9 | 12.9 | 12.0 | 10.2 | 4.5 | 2.8 |

Spread ±1.2 %, so a PGO effect of a few percent is measurable on the same runner type. This is the "before" number for
the arm64 PGO + orderfile build (`docs/speed-pack.md`). (This harness still had the restart defect fixed in 655e988, so
the page-load/download part of this run is not used.)

## Cold start trace (`scripts/ci/startup_trace.py`, `--trace-startup`, 10 s)
- `am start -W`: TotalTime 728 ms.
- Browser main thread milestones: `AsyncInitializationActivity.onCreate` at 17.8 ms; `onResume` at 107.5 ms; then one
  `Choreographer` frame from 114.7 ms lasting 187.8 ms (first draw of toolbar + NTP; only ~5 ms of it is instrumented:
  `ToolbarLayout.onMeasure` 2.2 ms, `startChromeBrowserProcessesAsync` 2.9 ms); `BrowserMainRunnerImpl::Initialize` at
  311.3 ms.
- Main-thread self time over 10 s: Choreographer frames 425 ms (9 frames), task overhead 119 ms, mojo 44 ms,
  `KeyedServiceFactory::GetServiceForContext` 26.8 ms (1681 calls), `finishNativeInitialization` 21.8 ms,
  toolbar init 20.5 ms, first tab WebContents 19.6 ms.
- GPU process: `eglInitialize` 31 ms, raster flushes 61 ms (Redroid renders in software, `redroid_gpu_mode=guest`).
- Reading: no Swiftra-specific work stands out. The largest single cost is the first Android frame under software
  rendering (same UI code as Chrome, so it is not a Swiftra-vs-Chrome difference and will be much smaller with a real
  GPU). Native init is what PGO + orderfile address. Not measured on a real phone (NOT RUN).
