# x64 baseline on the 0010 APK: run 39134172867, harness b6eb27c (emulator, x86_64)
- CPU bench totals: 367.9 / 366.6 ms (dom 98-102, mapset 80-81, sort 59-60, json 57-59).
- Cold start `am start -W` TotalTime: 984 ms (trace span 10.8 s).
- The page-load/download part did not run (`SPEED_E2E NOT_RUN flags not applied`, the restart defect fixed in 655e988).
- x64 gets no PGO change, so it is the control for the arm64 PGO + orderfile comparison.
