# UI comparison: com.android.chrome 133.0.6943.137 (emulator reference) vs org.chromium.chrome 155.0.8059.0 (artifact)

Chrome Stable target: **155.0.8059.80**. Emulator reference version differs, so every row is `not-tested` against Stable.

| screen | status vs emulator ref | id J | text J | desc J | pixel MAD | evidence |
|---|---|---|---|---|---|---|
| 01_first_run | mismatch | 0.421 | 0.667 | 0.0 | 0.0722 | 01_first_run.png |
| 01_first_run_1 | mismatch | 0.421 | 0.667 | 0.0 | 0.0728 | 01_first_run_1.png |
| 01_first_run_2 | mismatch | 0.053 | 0.0 | 1.0 | 0.3505 | 01_first_run_2.png |
| 02_ntp | mismatch | 0.312 | 0.0 | 0.2 | 0.2191 | 02_ntp.png |
| 03_omnibox_focused | mismatch | 0.4 | 0.0 | 0.029 | 0.0203 | 03_omnibox_focused.png |
| 04_omnibox_suggestions | mismatch | 0.42 | 0.05 | 0.077 | 0.0155 | 04_omnibox_suggestions.png |
| 05_page_loaded | mismatch | 0.306 | 0.0 | 0.444 | 0.1146 | 05_page_loaded.png |
| 06_page_info | mismatch | 0.6 | 0.4 | 1.0 | 0.0848 | 06_page_info.png |
| 07_app_menu | mismatch | 0.556 | 0.625 | 0.5 | 0.0724 | 07_app_menu.png |
| 08_second_tab_ntp | mismatch | 0.241 | 0.312 | 0.5 | 0.4768 | 08_second_tab_ntp.png |
| 09_tab_switcher | mismatch | 0.096 | 0.0 | 0.045 | 0.0708 | 09_tab_switcher.png |
| 10_incognito_ntp | mismatch | 0.421 | 0.455 | 0.444 | 0.1323 | 10_incognito_ntp.png |
| 10b_tab_switcher_incognito | mismatch | 0.639 | 1.0 | 0.5 | 0.1085 | 10b_tab_switcher_incognito.png |
| 11_settings | mismatch | 0.5 | 0.5 | 0.667 | 0.052 | 11_settings.png |
| 11b_settings_scrolled | mismatch | 0.421 | 0.524 | 0.667 | 0.0379 | 11b_settings_scrolled.png |
| 12_history | mismatch | 0.238 | 0.125 | 0.333 | 0.0147 | 12_history.png |
| 13_bookmarks | mismatch | 0.444 | 0.6 | 0.714 | 0.0569 | 13_bookmarks.png |
| 14_downloads | mismatch | 0.588 | 0.6 | 1.0 | 0.0148 | 14_downloads.png |
| 15_dark_page | mismatch | 0.023 | 0.0 | 0.0 | 0.6032 | 15_dark_page.png |
| 16_landscape | mismatch | 0.298 | 0.0 | 0.333 | 0.0567 | 16_landscape.png |
| 15b_dark_menu | not-tested | - | - | - | - | only artifact reached this screen |

Details (missing/extra elements) are in `comparison.json`.
