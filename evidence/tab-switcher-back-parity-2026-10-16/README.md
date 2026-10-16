# Tab switcher (Hub) BACK parity — b1 Swiftra, head 4d3a725 (2026-10-16)

| platform | run | hub खुला | tabs | BACK -> tab | ensure_main relaunch | swiftra crash | device_checks |
|---|---|---|---|---|---|---|---|
| x64 Android emulator (API 36) | ui-capture 38918534121 | True | 2 | True | 0 | 0 | 9/9 PASS |
| arm64 Redroid 14 (native arm64 CPU, software GPU — **real phone नहीं**) | arm64-e2e 38918537719 | True | 2 | True | 0 | 0 | 9/9 PASS |

Reference: Chromium 155.0.8059.80 `HubCoordinator.handleBackPress()` -> `selectCurrentTabAndHideHub()`।
`09_tab_switcher.png` में Hub (2 tab cards, "Search your tabs", tab groups/history panes) दिखता है।
NTP promo sheet ("Now you can customize your homepage") harness ने "No thanks" से बंद की (meta.json `promo_sheets`)।
पहले वाला FAIL (9eeb663) harness की गलती थी — d9b5a29 में वापस लिया; यह run उसकी पुष्टि है (d9b5a29 के runs 38916663718/38916666704 भी PASS)।
