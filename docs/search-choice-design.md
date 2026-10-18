# Swiftra search engine choice: design (research 18-10-2026, Chromium 155.0.8059.80)

Status: **research only; not implemented** (PLAN step 6). It will be a separate build after the ad blocker, because
it adds a First Run page and every device harness has to learn that page.

## What Chrome does
- On desktop, the search engine choice screen exists only in the EEA:
  - `SearchEngineChoiceService::GetStaticChoiceScreenConditions` returns `kNotInRegionalScope` unless
    `IsInSearchEngineChoiceScreenRegion()`.
- On Android, Chrome has no in-browser choice screen:
  - `components/search_engines/search_engine_choice/buildflags.gni` sets
    `choice_screen_in_chrome = !(is_android || is_fuchsia)`, with the comment "On Android the choice screen is
    displayed by the OS". In India the user never gets a choice; Google is pre-selected.

## What already exists in the Android tree (reuse, no new UI)
- `chrome/browser/search_engines/android/.../DefaultSearchEngineDialogCoordinator` and `DefaultSearchEngineDialogHelper`:
  - a dialog with one radio entry per engine;
  - **`Collections.shuffle(engines)`**, so the order is fair.
- `chrome/android/.../firstrun/DefaultSearchEngineFirstRunFragment` is the same chooser as a First Run page.
  `FirstRunFlowSequencer.shouldShowSearchEnginePage()` turns it on when the promo type is `SHOW_NEW` or
  `SHOW_EXISTING`.
- `LocaleManagerDelegate` (`chrome/browser/locale/...`) is the switch point:
  - `getSearchEnginePromoShowType()` returns `DONT_SHOW` in Chromium (only the Sogou special locale is handled).
  - `getSearchEnginesForPromoDialog()` throws `IllegalStateException` in Chromium. The engine list is supplied
    downstream in Chrome.
  - `onUserSearchEngineChoiceFromPromoDialog()` already calls `TemplateUrlService.setSearchEngine(keyword)` and
    stores `SearchEnginePromoState.CHECKED_AND_SHOWN`.

## Plan (patch 0014, Java only)
1. `getSearchEnginePromoShowType()` returns `SHOW_EXISTING` until the promo state is `CHECKED_AND_SHOWN`, and
   `DONT_SHOW` after that. It also returns `DONT_SHOW` when the default search engine is managed by policy (already
   checked by the caller).
2. `getSearchEnginesForPromoDialog()` returns the prepopulated engines of the current country, taken from
   `TemplateUrlService.getTemplateUrls()` and filtered to prepopulated entries. The dialog shuffles them.
3. Result: on first run, every user in every region picks the engine; nothing is pre-selected by Swiftra.
   Settings > Search engine still allows changing it later.

## E2E plan
- The First Run page appears exactly once, and the shown engine list is in a different order across fresh installs
  (several installs).
- After picking engine X, an omnibox search goes to X (the URL host is checked through the mapped local server).
- On the second launch the page does not appear again.
- Harness change: `device_checks.sh` / `run_capture.sh` FRE handling must pick an engine (a fixed choice for
  repeatability).
