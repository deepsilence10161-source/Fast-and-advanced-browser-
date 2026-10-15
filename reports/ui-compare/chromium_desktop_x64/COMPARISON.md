# UI comparison: com.android.chrome 133.0.6943.137 (emulator reference) vs org.chromium.chrome 155.0.8059.0 (artifact)

Chrome Stable target: **155.0.8059.80**. Emulator reference version differs, so every row is `not-tested` against Stable.

| screen | status vs emulator ref | id J | text J | desc J | pixel MAD | evidence |
|---|---|---|---|---|---|---|
| 01_first_run | mismatch | 0.421 | 0.667 | 0.0 | 0.0722 | 01_first_run.png |
| 01_first_run_1 | mismatch | 0.421 | 0.667 | 0.0 | 0.0728 | 01_first_run_1.png |
| 01_first_run_2 | mismatch | 0.053 | 0.0 | 1.0 | 0.3505 | 01_first_run_2.png |
| 02_ntp | mismatch | 0.312 | 0.0 | 0.2 | 0.2187 | 02_ntp.png |
| 03_omnibox_focused | mismatch | 0.4 | 0.0 | 0.027 | 0.0246 | 03_omnibox_focused.png |
| 04_omnibox_suggestions | mismatch | 0.42 | 0.05 | 0.077 | 0.0127 | 04_omnibox_suggestions.png |
| 05_page_loaded | mismatch | 0.326 | 0.875 | 0.5 | 0.0516 | 05_page_loaded.png |
| 06_page_info | mismatch | 0.909 | 1.0 | 1.0 | 0.0355 | 06_page_info.png |
| 07_app_menu | mismatch | 0.526 | 0.474 | 0.5 | 0.0569 | 07_app_menu.png |
| 08_second_tab_ntp | mismatch | 0.241 | 0.312 | 0.5 | 0.4765 | 08_second_tab_ntp.png |
| 09_tab_switcher | mismatch | 0.096 | 0.0 | 0.045 | 0.07 | 09_tab_switcher.png |
| 10_incognito_ntp | mismatch | 0.421 | 0.455 | 0.444 | 0.1323 | 10_incognito_ntp.png |
| 10b_tab_switcher_incognito | mismatch | 0.639 | 1.0 | 0.5 | 0.1085 | 10b_tab_switcher_incognito.png |
| 11_settings | mismatch | 0.5 | 0.5 | 0.667 | 0.052 | 11_settings.png |
| 11b_settings_scrolled | mismatch | 0.421 | 0.455 | 0.667 | 0.0395 | 11b_settings_scrolled.png |
| 12_history | mismatch | 0.667 | 1.0 | 0.4 | 0.0084 | 12_history.png |
| 13_bookmarks | mismatch | 0.324 | 0.25 | 0.714 | 0.0581 | 13_bookmarks.png |
| 14_downloads | mismatch | 0.588 | 0.6 | 1.0 | 0.0148 | 14_downloads.png |
| 15_dark_page | mismatch | 0.026 | 0.0 | 0.0 | 0.1043 | 15_dark_page.png |
| 16_landscape | mismatch | 0.326 | 0.2 | 0.3 | 0.029 | 16_landscape.png |
| 15b_dark_menu | not-tested | - | - | - | - | only artifact reached this screen |

Details (missing/extra elements) are in `comparison.json`.
