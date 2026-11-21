# Gemini in Swiftra personal (patch 0114, 158 line)

## What was asked
"Chrome's Gemini, used in our own way": many chats, ChatGPT-like interface, the chats are not wiped like in Chrome, Gemini remembers them.
Google sign-in is accepted, with ONE account that the browser is linked to.

## Why not Chrome's own built-in Gemini
Chrome's Gemini (Android) is a Google service tied to Chrome sign-in (US, English-US, 18+, Android 12+, 4 GB RAM) and its chats are kept in
Gemini Apps Activity of the signed-in account. Chrome sign-in needs Google's API keys, which open-source Chromium does not have (see
`docs/google-signin.md`), and the feature is switched on by Google's servers. A patch cannot switch it on, and it could not be measured
without a real account. So Swiftra uses the web Gemini that is available to any browser.

## What 0114 does
* **Settings (top of the main page):** "Gemini chat" opens `https://gemini.google.com/app` in a normal browser tab.
  "Gemini chat history" opens `https://myactivity.google.com/product/gemini` (review / delete saved chats).
* **Account:** the normal Google web sign-in in the browser, one account. Swiftra does not read, store or send the chats; there is no
  Swiftra-side copy, no API key and no new network code in the patch (test `tests/test_personal_gemini_0114.py`).
* **Chats, memory, history:** kept by Google in that account (Gemini Apps Activity; Google's default retention is 18 months, and the
  account can turn history off, which also turns off saved chats). The interface is Google's own (chat list in the side menu, new chat,
  rename, pin, delete); Swiftra does not restyle it.
* **"Stay signed in to Google after deleting data" (default ON):** `BrowsingDataBridge.clearBrowsingDataExcludingDomains` adds
  `google.com` to the excluded domains. The important-sites remover then keeps cookies, site storage AND cached pages of google.com;
  history, tabs, passwords, form data and every other site are still deleted (the history backend ignores the domain filter). Chats are never
  touched by Delete browsing data either way, because they are not in the browser. Turning the switch OFF signs you out of Google on every
  deletion. Cost of ON: cached google.com pages (their URLs) stay in the HTTP cache.

## Measured / not measured
`scripts/ci/personal_gemini_e2e.py` (workflow `personal-clipboard-e2e.yml`, script = personal_gemini_e2e.py), synthetic probe cookies only, no account:
M00 rows present, M01 gemini.google.com opens and is not refused, M02 switch ON keeps a google.com probe cookie and deletes another site's,
M03 switch OFF deletes both, I01 which files mention gemini.google.com afterwards. NOT measured: a real sign-in, a real Gemini answer,
voice input, file upload, Gemini in a signed-in session after Delete.

## Limits
* gemini.google.com must accept the browser; a Google block would show in M01.
* The microphone permission is still declared (0101 keeps RECORD_AUDIO); photo/file upload goes through the system picker (storage permissions are removed).
* The Face Guard lock covers browser tabs, so it covers the Gemini tab too; FLAG_SECURE (0113) hides it in Recents.
* 155 line: not ported (the 155 build stays as published).
