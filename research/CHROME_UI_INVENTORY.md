# Chrome Android UI inventory

## 1. Reference की पहचान (ईमानदार स्थिति)

- **लक्ष्य reference:** Google Chrome Stable **155.0.8059.80** (phone)। यह अभी **उपलब्ध नहीं** है।
- **इस फ़ाइल में देखा गया reference:** `com.android.chrome` **133.0.6943.137**, emulator image पर पहले से installed (`sdk_gphone64_x86_64`, Android 16 / API 36, Physical size: 1080x2400, Physical density: 420, font_scale 1.0, navigation_mode 2 (2 = gesture), locale `default (en-US)`, light theme, बिना Google account के)।
- **Evidence:** GitHub Actions run `38701948978`, artifact `ui-chrome_ref`। Screenshots/XML: `evidence/`।
- यह Stable 155 से 22 major versions पुराना है। इसलिए नीचे की हर पंक्ति **Chrome 133 का अवलोकन** है, Stable 155 का नहीं।

## 2. Capture protocol (हर reference के लिए समान)

1. `pm clear <package>`, light theme, portrait, animations बंद, कोई account नहीं।
2. `scripts/ui_capture.py` का scripted journey: first run → NTP → omnibox focus → `example.com` टाइप → page → page info → menu → नया tab → tab switcher → settings → history → bookmarks → downloads → dark theme → landscape → incognito।
3. हर screen पर: PNG screenshot, UIAutomator XML, और labelled nodes का JSON (text, content-desc, resource-id, class, bounds, clickable)।
4. केवल IANA demo domains (`example.com`/`example.org`)। कोई login, account photo, email या निजी chat नहीं।
5. **उपयोगकर्ता के फ़ोन से Stable 155 reference:** यही क्रम manually दोहराएँ, हर screen का screenshot लें, और Chrome version (Settings → About Chrome), फ़ोन model, Android version, display size, font size, theme और gesture/3-button navigation लिख दें। Account वाले screens न भेजें।

## 3. देखे गए screens और elements (Chrome 133.0.6943.137, emulator)

### `01_first_run` — first launch after pm clear
Screenshot: `01_first_run.png` · labelled nodes: 11

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `title` | Make Chrome your own |  | TextView | [0, 946, 1080, 1024] | 1080×78 |  |
| `subtitle` | Sign in to get your bookmarks, passwords, and more on all yo |  | TextView | [0, 1024, 1080, 1148] | 1080×124 |  |
| `signin_fre_continue_button` | Add account to device |  | Button | [63, 1904, 1017, 2030] | 954×126 | clickable |
| `signin_fre_dismiss_button` | Use without an account |  | Button | [63, 2030, 1017, 2156] | 954×126 | clickable |
| `signin_fre_footer` | By continuing, you agree to the Terms of Service. To help im |  | TextView | [63, 2188, 1017, 2274] | 954×86 |  |

### `01_first_run_1` — before tapping 'Use without an account'
Screenshot: `01_first_run_1.png` · labelled nodes: 11

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `title` | Make Chrome your own |  | TextView | [0, 937, 1080, 1022] | 1080×85 |  |
| `subtitle` | Sign in to get your bookmarks, passwords, and more on all yo |  | TextView | [0, 1022, 1080, 1155] | 1080×133 |  |
| `signin_fre_continue_button` | Add account to device |  | Button | [63, 1896, 1017, 2022] | 954×126 | clickable |
| `signin_fre_dismiss_button` | Use without an account |  | Button | [63, 2022, 1017, 2148] | 954×126 | clickable |
| `signin_fre_footer` | By continuing, you agree to the Terms of Service. To help im |  | TextView | [63, 2180, 1017, 2274] | 954×94 |  |

### `01_first_run_2` — before tapping 'Got it'
Screenshot: `01_first_run_2.png` · labelled nodes: 16

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` | Enhanced ad privacy in Chrome |  | TextView | [124, 489, 955, 574] | 831×85 |  |
| `` | We’re launching new privacy features that give you more choi |  | TextView | [42, 627, 1038, 736] | 996×109 |  |
| `privacy_sandbox_m1_notice_row_description_2` | Chrome notes topics of interest based on your recent browsin |  | TextView | [42, 778, 1038, 1046] | 996×268 |  |
| `` | To measure the performance of an ad, limited types of data a |  | TextView | [42, 1496, 1038, 1658] | 996×162 |  |
| `dropdown_element` |  |  | LinearLayout | [42, 1700, 1038, 1826] | 996×126 | clickable |
| `` | More about ads in Chrome |  | TextView | [42, 1700, 975, 1826] | 933×126 |  |
| `privacy_sandbox_m1_notice_row_description_4` | You can make changes in Chrome settings. |  | TextView | [42, 1868, 1038, 1924] | 996×56 |  |
| `settings_button` | Settings |  | Button | [63, 2169, 519, 2295] | 456×126 | clickable |
| `ack_button` | Got it |  | Button | [561, 2169, 1017, 2295] | 456×126 | clickable |

### `02_ntp` — new tab page / start surface
Screenshot: `02_ntp.png` · labelled nodes: 49

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `search_box_text` | Search or type URL |  | EditText | [105, 496, 722, 664] | 617×168 | clickable |
| `voice_search_button` |  | Start voice search | ImageView | [754, 517, 880, 643] | 126×126 | clickable |
| `lens_camera_button` |  | Search with your camera using Google Lens | ImageView | [880, 517, 1006, 643] | 126×126 | clickable |
| `` |  | Facebook: m.facebook.com | FrameLayout | [74, 772, 284, 986] | 210×214 | clickable |
| `tile_view_title` | Facebook |  | TextView | [85, 937, 273, 986] | 188×49 |  |
| `` |  | YouTube: m.youtube.com | FrameLayout | [288, 772, 498, 986] | 210×214 | clickable |
| `tile_view_title` | YouTube |  | TextView | [299, 937, 487, 986] | 188×49 |  |
| `` |  | Amazon.com: www.amazon.com | FrameLayout | [502, 772, 712, 986] | 210×214 | clickable |
| `tile_view_title` | Amazon.com |  | TextView | [513, 937, 701, 986] | 188×49 |  |
| `` |  | Wikipedia: en.m.wikipedia.org | FrameLayout | [716, 772, 926, 986] | 210×214 | clickable |
| `tile_view_title` | Wikipedia |  | TextView | [727, 937, 915, 986] | 188×49 |  |
| `` |  | ESPN.com: www.espn.com | FrameLayout | [930, 772, 1038, 986] | 108×214 | clickable |
| `tile_view_title` | ESPN.com |  | TextView | [941, 937, 1038, 986] | 97×49 |  |
| `header_title` | Discover |  | TextView | [106, 1142, 258, 1198] | 152×56 |  |
| `header_menu` |  | Options for Discover | ImageButton | [912, 1107, 1038, 1233] | 126×126 | clickable |
| `` |  | Newsweek, 1d | ViewGroup | [42, 1507, 320, 1623] | 278×116 | clickable |
| `` |  | Share Man Dragged From Iowa Meeting For Protesting Microsoft | ViewGroup | [806, 1518, 922, 1613] | 116×95 | clickable |
| `` |  | Card Menu Man Dragged From Iowa Meeting For Protesting Micro | ViewGroup | [922, 1518, 1038, 1613] | 116×95 | clickable |
| `home_button` |  | Open the home page | ImageButton | [0, 128, 126, 275] | 126×147 | clickable |
| `optional_toolbar_button` |  | Signed out. Opens options to sign in. | ImageButton | [691, 128, 828, 275] | 137×147 | clickable |
| `tab_switcher_button` |  | See 1 tab | ImageButton | [828, 128, 954, 275] | 126×147 | clickable |
| `menu_button` |  | Customize and control Google Chrome | ImageButton | [954, 128, 1080, 275] | 126×147 | clickable |

### `03_omnibox_focused` — omnibox focused, keyboard expected
Screenshot: `03_omnibox_focused.png` · labelled nodes: 59

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` |  | Facebook: m.facebook.com | FrameLayout | [74, 393, 284, 607] | 210×214 | clickable |
| `tile_view_title` | Facebook |  | TextView | [85, 558, 273, 607] | 188×49 |  |
| `` |  | YouTube: m.youtube.com | FrameLayout | [288, 393, 498, 607] | 210×214 | clickable |
| `tile_view_title` | YouTube |  | TextView | [299, 558, 487, 607] | 188×49 |  |
| `` |  | Amazon.com: www.amazon.com | FrameLayout | [502, 393, 712, 607] | 210×214 | clickable |
| `tile_view_title` | Amazon.com |  | TextView | [513, 558, 701, 607] | 188×49 |  |
| `` |  | Wikipedia: en.m.wikipedia.org | FrameLayout | [716, 393, 926, 607] | 210×214 | clickable |
| `tile_view_title` | Wikipedia |  | TextView | [727, 558, 915, 607] | 188×49 |  |
| `` |  | ESPN.com: www.espn.com | FrameLayout | [930, 393, 1038, 607] | 108×214 | clickable |
| `tile_view_title` | ESPN.com |  | TextView | [941, 558, 1038, 607] | 97×49 |  |
| `header_title` | Discover |  | TextView | [106, 1142, 258, 1198] | 152×56 |  |
| `header_menu` |  | Options for Discover | ImageButton | [912, 1107, 1038, 1233] | 126×126 | clickable |
| `` |  | Newsweek, 1d | ViewGroup | [42, 1507, 320, 1623] | 278×116 | clickable |
| `` |  | Share Man Dragged From Iowa Meeting For Protesting Microsoft | ViewGroup | [806, 1518, 922, 1613] | 116×95 | clickable |
| `` |  | Card Menu Man Dragged From Iowa Meeting For Protesting Micro | ViewGroup | [922, 1518, 1038, 1613] | 116×95 | clickable |
| `omnibox_suggestions_dropdown` |  | 6 suggested items in list below. | RecyclerView | [0, 275, 1080, 1517] | 1080×1242 |  |
| `` | Trending searches |  | TextView | [0, 275, 1080, 380] | 1080×105 |  |
| `line_1` | salad and go arizona |  | TextView | [168, 421, 933, 485] | 765×64 |  |
| `` |  | Refine: salad and go arizona | ImageView | [933, 380, 1059, 527] | 126×147 | clickable |
| `line_1` | manchester city vs psg highlights |  | TextView | [168, 568, 933, 632] | 765×64 |  |
| `` |  | Refine: manchester city vs psg highlights | ImageView | [933, 527, 1059, 674] | 126×147 | clickable |
| `line_1` | trader joe's unexpected cheddar cheese spread |  | TextView | [168, 689, 933, 816] | 765×127 |  |
| `` |  | Refine: trader joe's unexpected cheddar cheese spread | ImageView | [933, 674, 1059, 832] | 126×158 | clickable |
| `line_1` | ps5 jailbreak download games |  | TextView | [168, 873, 933, 937] | 765×64 |  |
| `` |  | Refine: ps5 jailbreak download games | ImageView | [933, 832, 1059, 979] | 126×147 | clickable |
| `line_1` | exoplanets |  | TextView | [168, 1020, 933, 1084] | 765×64 |  |
| `` |  | Refine: exoplanets | ImageView | [933, 979, 1059, 1126] | 126×147 | clickable |
| `location_bar_status` |  |  | LinearLayout | [53, 128, 137, 275] | 84×147 | clickable |
| `url_bar` | Search or type URL |  | EditText | [169, 136, 775, 267] | 606×131 | clickable,focused |
| `mic_button` |  | Start voice search | ImageButton | [807, 128, 933, 275] | 126×147 | clickable |
| `lens_camera_button` |  | Search with your camera using Google Lens | ImageButton | [933, 128, 1059, 275] | 126×147 | clickable |

### `04_omnibox_suggestions` — typed 'example.com'
Screenshot: `04_omnibox_suggestions.png` · labelled nodes: 54

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` |  | Facebook: m.facebook.com | FrameLayout | [74, 393, 284, 607] | 210×214 | clickable |
| `tile_view_title` | Facebook |  | TextView | [85, 558, 273, 607] | 188×49 |  |
| `` |  | YouTube: m.youtube.com | FrameLayout | [288, 393, 498, 607] | 210×214 | clickable |
| `tile_view_title` | YouTube |  | TextView | [299, 558, 487, 607] | 188×49 |  |
| `` |  | Amazon.com: www.amazon.com | FrameLayout | [502, 393, 712, 607] | 210×214 | clickable |
| `tile_view_title` | Amazon.com |  | TextView | [513, 558, 701, 607] | 188×49 |  |
| `` |  | Wikipedia: en.m.wikipedia.org | FrameLayout | [716, 393, 926, 607] | 210×214 | clickable |
| `tile_view_title` | Wikipedia |  | TextView | [727, 558, 915, 607] | 188×49 |  |
| `` |  | ESPN.com: www.espn.com | FrameLayout | [930, 393, 1038, 607] | 108×214 | clickable |
| `tile_view_title` | ESPN.com |  | TextView | [941, 558, 1038, 607] | 97×49 |  |
| `header_title` | Discover |  | TextView | [106, 1142, 258, 1198] | 152×56 |  |
| `header_menu` |  | Options for Discover | ImageButton | [912, 1107, 1038, 1233] | 126×126 | clickable |
| `` |  | Newsweek, 1d | ViewGroup | [42, 1507, 320, 1623] | 278×116 | clickable |
| `` |  | Share Man Dragged From Iowa Meeting For Protesting Microsoft | ViewGroup | [806, 1518, 922, 1613] | 116×95 | clickable |
| `` |  | Card Menu Man Dragged From Iowa Meeting For Protesting Micro | ViewGroup | [922, 1518, 1038, 1613] | 116×95 | clickable |
| `omnibox_suggestions_dropdown` |  | 4 suggested items in list below. | RecyclerView | [0, 275, 1080, 1517] | 1080×1242 |  |
| `line_1` | example.com |  | TextView | [168, 288, 1059, 352] | 891×64 |  |
| `line_2` | example.com |  | TextView | [168, 352, 1059, 408] | 891×56 |  |
| `line_1` | example.com |  | TextView | [168, 463, 1059, 527] | 891×64 |  |
| `line_1` | example.com ip address |  | TextView | [168, 610, 933, 674] | 765×64 |  |
| `` |  | Refine: example.com ip address | ImageView | [933, 569, 1059, 716] | 126×147 | clickable |
| `line_1` | example.com mycomp.test.com localhost |  | TextView | [168, 731, 933, 858] | 765×127 |  |
| `` |  | Refine: example.com mycomp.test.com localhost | ImageView | [933, 716, 1059, 874] | 126×158 | clickable |
| `location_bar_status` |  |  | LinearLayout | [53, 128, 137, 275] | 84×147 | clickable |
| `url_bar` | example.com |  | EditText | [169, 136, 901, 267] | 732×131 | clickable,focused |
| `delete_button` |  | Clear input | ImageButton | [933, 128, 1059, 275] | 126×147 | clickable |

### `05_page_loaded` — https://example.com loaded
Screenshot: `05_page_loaded.png` · labelled nodes: 30

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` | Example Domain |  | WebView | [0, 275, 1080, 2339] | 1080×2064 | focused |
| `` | This domain is for use in documentation examples without nee |  | TextView | [84, 868, 1000, 1141] | 916×273 |  |
| `` | هذا النطاق مُخصص للاستخدام في أمثلة التوثيق دون الحاجة إلى إ |  | TextView | [84, 1178, 1000, 1359] | 916×181 |  |
| `` | 该域名仅用于文档示例，无需获得许可。这并非一项服务，请勿将其用于测试和监控目的。 |  | TextView | [84, 1390, 1000, 1514] | 916×124 |  |
| `` | L’usage de ce domaine est réservé à des exemples de document |  | TextView | [84, 1545, 1000, 1784] | 916×239 |  |
| `` | Данный домен предназначен для использования в примерах докум |  | TextView | [84, 1818, 1000, 2115] | 916×297 |  |
| `` | Este dominio está destinado al uso en ejemplos de documentac |  | TextView | [84, 2149, 1000, 2339] | 916×190 |  |
| `home_button` |  | Open the home page | ImageButton | [0, 128, 126, 275] | 126×147 | clickable |
| `location_bar_status` |  |  | LinearLayout | [126, 128, 210, 275] | 84×147 | clickable |
| `location_bar_status_icon` |  | Connection is secure | ImageView | [136, 170, 199, 233] | 63×63 |  |
| `url_bar` | example.com |  | EditText | [210, 136, 670, 267] | 460×131 | clickable |
| `optional_toolbar_button` |  | New tab | ImageButton | [691, 128, 828, 275] | 137×147 | clickable |
| `tab_switcher_button` |  | See 1 tab | ImageButton | [828, 128, 954, 275] | 126×147 | clickable |
| `menu_button` |  | Customize and control Google Chrome | ImageButton | [954, 128, 1080, 275] | 126×147 | clickable |

### `06_page_info` — page info / connection security sheet
Screenshot: `06_page_info.png` · labelled nodes: 12

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `page_info_url_wrapper` |  |  | LinearLayout | [0, 128, 1080, 254] | 1080×126 | clickable |
| `page_info_truncated_url` | example.com |  | TextView | [381, 132, 698, 249] | 317×117 |  |
| `page_info_connection_row` |  |  | FrameLayout | [0, 254, 1080, 381] | 1080×127 | clickable |
| `page_info_row_title` | Connection is secure |  | TextView | [189, 291, 596, 344] | 407×53 |  |
| `page_info_cookies_row` |  |  | FrameLayout | [0, 384, 1080, 511] | 1080×127 | clickable |
| `page_info_row_title` | Cookies and site data |  | TextView | [189, 421, 603, 474] | 414×53 |  |

### `07_app_menu` — overflow/app menu on a web page
Screenshot: `07_app_menu.png` · labelled nodes: 52

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `button_one` |  | Forward | ImageButton | [388, 143, 523, 269] | 135×126 | clickable |
| `button_two` |  | Bookmark | ImageButton | [523, 143, 658, 269] | 135×126 | clickable |
| `button_three` |  | Download | ImageButton | [658, 143, 793, 269] | 135×126 | clickable |
| `button_four` |  | Page info | ImageButton | [793, 143, 929, 269] | 136×126 | clickable |
| `button_five` |  | Refresh | ImageButton | [929, 143, 1065, 269] | 136×126 | clickable |
| `new_tab_menu_id` |  |  | LinearLayout | [388, 269, 1065, 395] | 677×126 | clickable |
| `menu_item_text` | New tab |  | TextView | [493, 269, 683, 395] | 190×126 |  |
| `new_incognito_tab_menu_id` |  |  | LinearLayout | [388, 395, 1065, 521] | 677×126 | clickable |
| `title` | New Incognito tab |  | TextView | [430, 395, 1023, 521] | 593×126 |  |
| `open_history_menu_id` |  |  | LinearLayout | [388, 550, 1065, 676] | 677×126 | clickable |
| `menu_item_text` | History |  | TextView | [493, 550, 663, 676] | 170×126 |  |
| `quick_delete_menu_id` |  |  | LinearLayout | [388, 676, 1065, 802] | 677×126 | clickable |
| `menu_item_text` | Delete browsing data |  | TextView | [493, 676, 931, 802] | 438×126 |  |
| `downloads_menu_id` |  |  | LinearLayout | [388, 831, 1065, 957] | 677×126 | clickable |
| `menu_item_text` | Downloads |  | TextView | [493, 831, 737, 957] | 244×126 |  |
| `all_bookmarks_menu_id` |  |  | LinearLayout | [388, 957, 1065, 1083] | 677×126 | clickable |
| `menu_item_text` | Bookmarks |  | TextView | [493, 957, 739, 1083] | 246×126 |  |
| `recent_tabs_menu_id` |  |  | LinearLayout | [388, 1083, 1065, 1209] | 677×126 | clickable |
| `menu_item_text` | Recent tabs |  | TextView | [493, 1083, 753, 1209] | 260×126 |  |
| `title` | Share… | Share… | TextView | [388, 1238, 918, 1364] | 530×126 | clickable |
| `find_in_page_id` |  |  | LinearLayout | [388, 1364, 1065, 1490] | 677×126 | clickable |
| `menu_item_text` | Find in page |  | TextView | [493, 1364, 760, 1490] | 267×126 |  |
| `translate_id` |  |  | LinearLayout | [388, 1490, 1065, 1616] | 677×126 | clickable |
| `menu_item_text` | Translate… |  | TextView | [493, 1490, 731, 1616] | 238×126 |  |
| `universal_install` |  |  | LinearLayout | [388, 1616, 1065, 1742] | 677×126 | clickable |
| `menu_item_text` | Add to Home screen |  | TextView | [493, 1616, 917, 1742] | 424×126 |  |
| `title` | Desktop site | Turn on Request desktop site | TextView | [388, 1742, 918, 1868] | 530×126 | clickable |
| `checkbox` |  |  | ImageView | [918, 1742, 1065, 1868] | 147×126 | clickable |
| `preferences_id` |  |  | LinearLayout | [388, 1897, 1065, 2023] | 677×126 | clickable |
| `menu_item_text` | Settings |  | TextView | [493, 1897, 682, 2023] | 189×126 |  |
| `help_id` |  |  | LinearLayout | [388, 2023, 1065, 2149] | 677×126 | clickable |
| `menu_item_text` | Help & feedback |  | TextView | [493, 2023, 844, 2149] | 351×126 |  |

### `08_second_tab_ntp` — second tab opened from menu
Screenshot: `08_second_tab_ntp.png` · labelled nodes: 49

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `search_box_text` | Search or type URL |  | EditText | [105, 496, 722, 664] | 617×168 | clickable |
| `voice_search_button` |  | Start voice search | ImageView | [754, 517, 880, 643] | 126×126 | clickable |
| `lens_camera_button` |  | Search with your camera using Google Lens | ImageView | [880, 517, 1006, 643] | 126×126 | clickable |
| `` |  | Facebook: m.facebook.com | FrameLayout | [74, 772, 284, 986] | 210×214 | clickable |
| `tile_view_title` | Facebook |  | TextView | [85, 937, 273, 986] | 188×49 |  |
| `` |  | YouTube: m.youtube.com | FrameLayout | [288, 772, 498, 986] | 210×214 | clickable |
| `tile_view_title` | YouTube |  | TextView | [299, 937, 487, 986] | 188×49 |  |
| `` |  | Amazon.com: www.amazon.com | FrameLayout | [502, 772, 712, 986] | 210×214 | clickable |
| `tile_view_title` | Amazon.com |  | TextView | [513, 937, 701, 986] | 188×49 |  |
| `` |  | Wikipedia: en.m.wikipedia.org | FrameLayout | [716, 772, 926, 986] | 210×214 | clickable |
| `tile_view_title` | Wikipedia |  | TextView | [727, 937, 915, 986] | 188×49 |  |
| `` |  | ESPN.com: www.espn.com | FrameLayout | [930, 772, 1038, 986] | 108×214 | clickable |
| `tile_view_title` | ESPN.com |  | TextView | [941, 937, 1038, 986] | 97×49 |  |
| `header_title` | Discover |  | TextView | [106, 1142, 258, 1198] | 152×56 |  |
| `header_menu` |  | Options for Discover | ImageButton | [912, 1107, 1038, 1233] | 126×126 | clickable |
| `` |  | Newsweek, 1d | ViewGroup | [42, 1507, 320, 1623] | 278×116 | clickable |
| `` |  | Share Man Dragged From Iowa Meeting For Protesting Microsoft | ViewGroup | [806, 1518, 922, 1613] | 116×95 | clickable |
| `` |  | Card Menu Man Dragged From Iowa Meeting For Protesting Micro | ViewGroup | [922, 1518, 1038, 1613] | 116×95 | clickable |
| `home_button` |  | Open the home page | ImageButton | [0, 128, 126, 275] | 126×147 | clickable |
| `optional_toolbar_button` |  | Signed out. Opens options to sign in. | ImageButton | [691, 128, 828, 275] | 137×147 | clickable |
| `tab_switcher_button` |  | See 2 tabs | ImageButton | [828, 128, 954, 275] | 126×147 | clickable |
| `menu_button` |  | Customize and control Google Chrome | ImageButton | [954, 128, 1080, 275] | 126×147 | clickable |

### `09_tab_switcher` — tab switcher grid, 2 tabs
Screenshot: `09_tab_switcher.png` · labelled nodes: 33

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `toolbar_action_button` |  | New tab | Button | [0, 128, 189, 275] | 189×147 | clickable |
| `` |  | 2 standard tabs | LinearLayout | [413, 128, 540, 275] | 127×147 | selected |
| `` |  | Tab groups | LinearLayout | [540, 128, 667, 275] | 127×147 | clickable |
| `menu_button` |  | Manage open tabs | ImageButton | [954, 128, 1080, 275] | 126×147 | clickable |
| `search_box` |  |  | LinearLayout | [42, 296, 1038, 401] | 996×105 | clickable |
| `search_box_text` | Search your tabs |  | EditText | [84, 296, 996, 401] | 912×105 | clickable |
| `tab_title` | Example Domain | Example Domain, tab | TextView | [142, 443, 403, 548] | 261×105 |  |
| `action_button` |  | Close Example Domain tab | ImageView | [403, 433, 529, 559] | 126×126 | clickable |
| `tab_title` | New tab | New tab, tab | TextView | [661, 443, 922, 548] | 261×105 |  |
| `action_button` |  | Close New tab tab | ImageView | [922, 433, 1048, 559] | 126×126 | clickable |

### `10_incognito_ntp` — incognito new tab page
Screenshot: `10_incognito_ntp.png` · labelled nodes: 35

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` |  | New Incognito tab | FrameLayout | [0, 275, 1080, 2337] | 1080×2062 | focused |
| `new_tab_incognito_title` | You’ve gone Incognito |  | TextView | [84, 603, 665, 688] | 581×85 |  |
| `new_tab_incognito_subtitle` | Others who use this device won’t see your activity, so you c |  | TextView | [84, 743, 996, 1011] | 912×268 |  |
| `new_tab_incognito_features` | Chrome won’t save:
Your browsing history
Cookies and site da |  | TextView | [84, 1066, 600, 1281] | 516×215 |  |
| `new_tab_incognito_warning` | Your activity might still be visible to:
Websites you visit
 |  | TextView | [84, 1336, 673, 1551] | 589×215 |  |
| `learn_more` | Learn more |  | TextView | [84, 1562, 277, 1688] | 193×126 | clickable |
| `cookie_controls_card_title` | Block third-party cookies |  | TextView | [126, 1750, 817, 1814] | 691×64 |  |
| `cookie_controls_card_subtitle` | When on, sites can't use cookies that track you across the w |  | TextView | [126, 1830, 817, 1992] | 691×162 |  |
| `cookie_controls_card_toggle` |  | Block third-party cookies | Switch | [831, 1808, 940, 1934] | 109×126 | clickable,checked |
| `home_button` |  | Open the home page | ImageButton | [0, 128, 126, 275] | 126×147 | clickable |
| `location_bar_status` |  |  | LinearLayout | [126, 128, 232, 275] | 106×147 | clickable |
| `location_bar_incognito_badge` |  | Incognito mode | ImageView | [126, 170, 211, 233] | 85×63 |  |
| `url_bar` | Search or type URL |  | EditText | [232, 136, 807, 267] | 575×131 | clickable |
| `tab_switcher_button` |  | See 1 tab | ImageButton | [828, 128, 954, 275] | 126×147 | clickable |
| `menu_button` |  | Customize and control Google Chrome | ImageButton | [954, 128, 1080, 275] | 126×147 | clickable |

### `10b_tab_switcher_incognito` — tab switcher incognito pane
Screenshot: `10b_tab_switcher_incognito.png` · labelled nodes: 28

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `toolbar_action_button` |  | New Incognito tab | Button | [0, 128, 189, 275] | 189×147 | clickable |
| `` |  | 2 standard tabs | LinearLayout | [349, 128, 476, 275] | 127×147 | clickable |
| `` |  | Incognito tabs | LinearLayout | [476, 128, 603, 275] | 127×147 | selected |
| `` |  | Tab groups | LinearLayout | [603, 128, 730, 275] | 127×147 | clickable |
| `menu_button` |  | Manage open tabs | ImageButton | [954, 128, 1080, 275] | 126×147 | clickable |
| `search_box` |  |  | LinearLayout | [42, 296, 1038, 401] | 996×105 | clickable |
| `search_box_text` | Search your Incognito tabs |  | EditText | [84, 296, 996, 401] | 912×105 | clickable |
| `tab_title` | New Incognito tab | New Incognito tab, tab | TextView | [142, 443, 403, 548] | 261×105 |  |
| `action_button` |  | Close New Incognito tab tab | ImageView | [403, 433, 529, 559] | 126×126 | clickable |

### `11_settings` — menu → Settings
Screenshot: `11_settings.png` · labelled nodes: 31

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` |  | Navigate up | ImageButton | [0, 128, 147, 275] | 147×147 | clickable |
| `` | Settings |  | TextView | [157, 159, 369, 244] | 212×85 |  |
| `menu_id_general_help` |  | Help & feedback | Button | [953, 138, 1080, 264] | 127×126 | clickable |
| `` | You and Google |  | TextView | [0, 275, 1080, 368] | 1080×93 |  |
| `account_management_account_row` |  |  | LinearLayout | [0, 410, 1080, 666] | 1080×256 | clickable |
| `title` | Sign in |  | TextView | [189, 452, 318, 516] | 129×64 |  |
| `summary` | Get your bookmarks, passwords and more on all your devices |  | TextView | [189, 516, 1038, 619] | 849×103 |  |
| `account_management_google_services_row` |  |  | LinearLayout | [0, 666, 1080, 819] | 1080×153 | clickable |
| `title` | Google services |  | TextView | [189, 708, 501, 772] | 312×64 |  |
| `` | Basics |  | TextView | [0, 819, 1080, 912] | 1080×93 |  |
| `title` | Search engine |  | TextView | [42, 996, 318, 1060] | 276×64 |  |
| `summary` | Google |  | TextView | [42, 1060, 165, 1116] | 123×56 |  |
| `title` | Google Password Manager |  | TextView | [42, 1200, 558, 1264] | 516×64 |  |
| `title` | Payment methods |  | TextView | [42, 1348, 389, 1412] | 347×64 |  |
| `title` | Addresses and more |  | TextView | [42, 1496, 437, 1560] | 395×64 |  |
| `title` | Privacy and security |  | TextView | [42, 1644, 432, 1708] | 390×64 |  |
| `title` | Safety check |  | TextView | [42, 1792, 292, 1856] | 250×64 |  |
| `title` | Notifications |  | TextView | [42, 1940, 286, 2004] | 244×64 |  |
| `title` | Theme |  | TextView | [42, 2088, 173, 2152] | 131×64 |  |
| `` | Advanced |  | TextView | [0, 2194, 1080, 2287] | 1080×93 |  |

### `11b_settings_scrolled` — settings scrolled
Screenshot: `11b_settings_scrolled.png` · labelled nodes: 27

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` |  | Navigate up | ImageButton | [0, 128, 147, 275] | 147×147 | clickable |
| `` | Settings |  | TextView | [157, 159, 369, 244] | 212×85 |  |
| `menu_id_general_help` |  | Help & feedback | Button | [953, 138, 1080, 264] | 127×126 | clickable |
| `title` | Privacy and security |  | TextView | [42, 275, 432, 328] | 390×53 |  |
| `title` | Safety check |  | TextView | [42, 412, 292, 476] | 250×64 |  |
| `title` | Notifications |  | TextView | [42, 560, 286, 624] | 244×64 |  |
| `title` | Theme |  | TextView | [42, 708, 173, 772] | 131×64 |  |
| `` | Advanced |  | TextView | [0, 814, 1080, 907] | 1080×93 |  |
| `title` | Tabs |  | TextView | [42, 991, 132, 1055] | 90×64 |  |
| `title` | Homepage |  | TextView | [42, 1139, 251, 1203] | 209×64 |  |
| `summary` | On |  | TextView | [42, 1203, 91, 1259] | 49×56 |  |
| `title` | New tab page cards |  | TextView | [42, 1343, 425, 1407] | 383×64 |  |
| `title` | Toolbar shortcut |  | TextView | [42, 1491, 360, 1555] | 318×64 |  |
| `title` | Accessibility |  | TextView | [42, 1639, 282, 1703] | 240×64 |  |
| `title` | Site settings |  | TextView | [42, 1787, 279, 1851] | 237×64 |  |
| `title` | Languages |  | TextView | [42, 1935, 254, 1999] | 212×64 |  |
| `title` | Downloads |  | TextView | [42, 2083, 254, 2147] | 212×64 |  |
| `title` | About Chrome |  | TextView | [42, 2231, 321, 2295] | 279×64 |  |

### `12_history` — menu → History
Screenshot: `12_history.png` · labelled nodes: 17

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` | History |  | TextView | [42, 159, 230, 244] | 188×85 |  |
| `search_menu_id` |  | Search | Button | [815, 138, 942, 264] | 127×126 | clickable |
| `close_menu_id` |  | Close | Button | [942, 138, 1069, 264] | 127×126 | clickable |
| `privacy_disclaimer` | You may see the history from other apps that open links in C |  | TextView | [42, 291, 1038, 400] | 996×109 |  |
| `clear_browsing_data_button` | Delete browsing data… |  | Button | [0, 442, 1080, 582] | 1080×140 | clickable |
| `` | Today - Oct 15, 2026 |  | TextView | [42, 638, 1038, 694] | 996×56 |  |
| `title` | Example Domain |  | TextView | [190, 744, 507, 808] | 317×64 |  |
| `description` | example.com |  | TextView | [190, 808, 415, 864] | 225×56 |  |
| `end_button` |  | Example Domain Remove | ImageButton | [933, 720, 1080, 888] | 147×168 | clickable |

### `13_bookmarks` — menu → Bookmarks
Screenshot: `13_bookmarks.png` · labelled nodes: 33

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `action_bar` |  |  | ViewGroup | [0, 128, 1080, 275] | 1080×147 | clickable |
| `` | Bookmarks |  | TextView | [42, 159, 336, 244] | 294×85 |  |
| `normal_options_submenu` |  | Sort and view options | Button | [688, 138, 815, 264] | 127×126 | clickable |
| `create_new_folder_menu_id` |  | Create new folder | Button | [815, 138, 942, 264] | 127×126 | clickable |
| `close_menu_id` |  | Close dialog | Button | [942, 138, 1069, 264] | 127×126 | clickable |
| `row_search_text` | Search your bookmarks |  | EditText | [37, 275, 916, 380] | 879×105 | clickable |
| `sync_promo_close_button` |  | Close | ImageButton | [901, 449, 1027, 575] | 126×126 | clickable |
| `sync_promo_title` | Get all your bookmarks |  | TextView | [318, 576, 761, 629] | 443×53 |  |
| `sync_promo_description` | Sign in to get your bookmarks and more on all your devices |  | TextView | [112, 661, 967, 701] | 855×40 |  |
| `sync_promo_signin_button` | Sign in |  | Button | [84, 733, 996, 859] | 912×126 | clickable |
| `` |  | Mobile bookmarks No bookmarks | FrameLayout | [0, 933, 1080, 1181] | 1080×248 | clickable |
| `child_count_text` | 0 |  | TextView | [150, 1060, 252, 1162] | 102×102 |  |
| `title` | Mobile bookmarks |  | TextView | [294, 1025, 645, 1089] | 351×64 |  |
| `` |  | Reading list No unread pages | FrameLayout | [0, 1181, 1080, 1429] | 1080×248 | clickable |
| `child_count_text` | 0 |  | TextView | [150, 1308, 252, 1410] | 102×102 |  |
| `title` | Reading list |  | TextView | [294, 1273, 517, 1337] | 223×64 |  |

### `14_downloads` — menu → Downloads
Screenshot: `14_downloads.png` · labelled nodes: 14

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` | Downloads |  | TextView | [42, 159, 334, 244] | 292×85 |  |
| `settings_menu_id` |  | Settings | Button | [815, 138, 942, 264] | 127×126 | clickable |
| `close_menu_id` |  | Close | Button | [942, 138, 1069, 264] | 127×126 | clickable |
| `` | Using 0.00 KB of 7.73 GB |  | TextView | [0, 275, 1080, 366] | 1080×91 |  |
| `empty_state_text_title` | You’ll find your downloads here |  | TextView | [200, 1279, 878, 1396] | 678×117 |  |
| `empty_state_text_description` | You can save images and files to view offline or share in ot |  | TextView | [92, 1396, 987, 1526] | 895×130 |  |

### `15_dark_page` — system dark theme, example.org
Screenshot: `15_dark_page.png` · labelled nodes: 8

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` | Chrome notifications make things easier |  | TextView | [70, 1355, 982, 1513] | 912×158 |  |
| `` | You’ll be able to easily manage media controls, Incognito se |  | TextView | [70, 1545, 982, 1648] | 912×103 |  |
| `negative_button` | No thanks |  | Button | [449, 1690, 680, 1816] | 231×126 | clickable |
| `positive_button` | Continue |  | Button | [701, 1690, 982, 1816] | 281×126 | clickable |

### `16_landscape` — landscape orientation
Screenshot: `16_landscape.png` · labelled nodes: 27

| resource-id | दिखने वाला text | a11y label (content-desc) | control type | bounds [l,t,r,b] | touch target (px) | state |
|---|---|---|---|---|---|---|
| `` | Example Domain |  | WebView | [128, 210, 2400, 1020] | 2272×810 | focused |
| `` | This domain is for use in documentation examples without nee |  | TextView | [718, 490, 1813, 693] | 1095×203 |  |
| `` | هذا النطاق مُخصص للاستخدام في أمثلة التوثيق دون الحاجة إلى إ |  | TextView | [718, 732, 1813, 853] | 1095×121 |  |
| `` | 该域名仅用于文档示例，无需获得许可。这并非一项服务，请勿将其用于测试和监控目的。 |  | TextView | [718, 887, 1813, 1008] | 1095×121 |  |
| `home_button` |  | Open the home page | ImageButton | [128, 63, 254, 210] | 126×147 | clickable |
| `location_bar_status` |  |  | LinearLayout | [254, 63, 338, 210] | 84×147 | clickable |
| `location_bar_status_icon` |  | Connection is secure | ImageView | [264, 105, 327, 168] | 63×63 |  |
| `url_bar` | example.org |  | EditText | [338, 71, 1990, 202] | 1652×131 | clickable |
| `optional_toolbar_button` |  | New tab | ImageButton | [2011, 63, 2148, 210] | 137×147 | clickable |
| `tab_switcher_button` |  | See 2 tabs | ImageButton | [2148, 63, 2274, 210] | 126×147 | clickable |
| `menu_button` |  | Customize and control Google Chrome | ImageButton | [2274, 63, 2400, 210] | 126×147 | clickable |

## 4. Brief की पूरी checklist: क्या देखा गया, क्या नहीं

| क्षेत्र | इस capture में screens | स्थिति |
|---|---|---|
| app launch / welcome / terms / default-browser / sign-in expectations | 01_first_run | आंशिक रूप से देखा (Chrome 133.0.6943.137, emulator) |
| normal startup / home / new tab, logo/search, top/bottom toolbar | 02_ntp | आंशिक रूप से देखा (Chrome 133.0.6943.137, emulator) |
| omnibox focus, suggestions, autocomplete, clipboard, clear, mic, incognito marks | 03_omnibox_focused, 04_omnibox_suggestions | आंशिक रूप से देखा (Chrome 133.0.6943.137, emulator) |
| back/forward/reload/stop/share/translate/bookmark/site-info/secure states | 05_page_loaded, 06_page_info, 07_app_menu | आंशिक रूप से देखा (Chrome 133.0.6943.137, emulator) |
| tabs, incognito, groups, create/reorder/close/restore, long-press, empty state | 08_second_tab_ntp, 09_tab_switcher, 10_incognito_ntp, 10b_tab_switcher_incognito | आंशिक रूप से देखा (Chrome 133.0.6943.137, emulator) |
| menu, More/overflow actions, settings hierarchy and all core screens | 07_app_menu, 11_settings, 11b_settings_scrolled | आंशिक रूप से देखा (Chrome 133.0.6943.137, emulator) |
| history / synced tabs / downloads / bookmarks / passwords / autofill / privacy / languages / accessibility | 12_history, 13_bookmarks, 14_downloads | आंशिक रूप से देखा (Chrome 133.0.6943.137, emulator) |
| site permissions / page info / pop-ups, camera/mic/location, file chooser, media/fullscreen/print/share | 06_page_info | आंशिक रूप से देखा (Chrome 133.0.6943.137, emulator) |
| home-screen shortcuts, PWAs, external intents/app links, Custom Tabs, back gestures | — | **NOT OBSERVED** |
| light/dark, portrait/landscape, IME open, gesture nav-bar, status bar, cutout/edge-to-edge | 15_dark_page, 16_landscape, 03_omnibox_focused | आंशिक रूप से देखा (Chrome 133.0.6943.137, emulator) |
| accessibility labels, TalkBack, switch access, touch targets, large text, contrast | — | **NOT OBSERVED** |
| offline/retry, renderer crash recovery, background/restore, rotation, memory pressure | — | **NOT OBSERVED** |

**Stable 155 के लिए हर पंक्ति: NOT OBSERVED।** Animation, latency, transition और TalkBack का अवलोकन अभी दर्ज नहीं हुआ है; journey में इन्हें मापने के steps जोड़ने बाकी हैं।

## 5. Chromium 155 artifact से अंतर

Chromium 155.0.8059.0 snapshot के वही screens इसी run में capture हुए हैं। Screen-दर-screen अंतर (missing/extra resource-ids, text, a11y labels, pixel MAD, side-by-side PNG) `reports/ui-compare/<target>/COMPARISON.md` में हैं। मुख्य देखे गए अंतर: 155 में नीचे का toolbar (`bottom_bar_*`, Home / Ask Gemini / New tab / Tabs / Menu), NTP पर `composeplate_button` "AI Mode" chip, omnibox में security status icon का न होना (page info केवल menu → Site controls से), और FRE का अलग क्रम। 133 में ये controls ऊपर toolbar में हैं और `location_bar_status_icon` मौजूद है। ये Stable 155 में भी ऐसे ही हैं या नहीं (field trials), यह Stable 155 reference के बिना **अज्ञात** है।
