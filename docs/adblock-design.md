# Swiftra built-in Ad & Tracker Blocker: design + implementation (18-10-2026, Chromium 155.0.8059.80)

Status: **implemented as patches 0012 + 0013; device build NOT RUN yet** (it is queued after the 0011 builds).
Desktop-component check: PASS (see Verification). PLAN step 5.

## Engine: Chromium's own subresource_filter (no new matching engine)
All references are to the @155 source.

- **Preset.** `subresource_filter_features.cc` gets the preset `swiftra_adblock_on_all_sites`:
  `Configuration(kEnabled, ActivationScope::ALL_SITES)`, priority 900. It is enabled by the new feature
  `kSwiftraAdBlock` (ENABLED_BY_DEFAULT).
  - Phishing activation (1000) keeps priority, so its warning flag is unchanged.
  - Better Ads (800) is a subset of the new preset.
  - `SafeBrowsingPageActivationThrottle::DoesRootFrameURLSatisfyActivationConditions` returns true for ALL_SITES,
    so no Google list is needed.
  - The throttle exists whenever `database_manager` exists; in Swiftra the Shield SafeBrowsingService provides it
    (`content_subresource_filter_throttle_manager.cc`).
- **Ruleset in the APK.** `chrome/browser/browser_resources.grd` includes
  `IDR_SWIFTRA_ADBLOCK_RULESET` (`resources/swiftra/adblock_ruleset.pb`, `compress="gzip"`).
  - Grit gzips it (`grit/node/base.py`), and `ResourceBundle::LoadDataResourceString` decompresses it
    (`DecompressIfNeeded`).
  - `BrowserProcessImpl::CreateSubresourceFilterRulesetService` calls `IndexAndStoreAndPublishRulesetIfNeeded` with
    `UnindexedRulesetInfo.resource_id`.
  - The ruleset is indexed once in the background after startup; the same version is never re-indexed.
  - `chrome/browser/BUILD.gn` `source_set("core")` gets an explicit dep on `:resources` (the grit target).
    No file in `core` included `chrome/grit/browser_resources.h` before, so without this dep ninja could compile
    `browser_process_impl.cc` before the header is regenerated.
  - The file comes from `adblock/swiftra-ruleset.pb.gz` through the transform `patches/0013-swiftra-adblock-ruleset.py`.
    That script pins the SHA-256 and sets the version `swiftra.<sha256[:16]>`.
- **No Google ruleset download.** `RegisterSubresourceFilterComponent` returns early when `kSwiftraAdBlock` is on.
  Otherwise the component updater could replace the Swiftra ruleset, and it would also add a Google request.
- **UI.**
  - The per-page Android "Ads blocked" message (`ProfileInteractionManager::MaybeShowNotification`) is suppressed
    when `kSwiftraAdBlock` is on. `ActivationOptions` @155 has no suppress flag; `kSuppressNotificationsParameterName`
    is a declared but unused constant.
  - `OnContentBlocked(ADS)` and the activation metadata are kept. Page Info therefore still shows the ads state, and
    the per-site switch (ADS content setting = allow) still exempts a site through `OnPageActivationComputed`.
  - Privacy note: the activation metadata is a local per-site website-settings entry, the same as Chrome writes on
    activated sites. It is cleared with site data.
- **Known gap: the first page after install is unfiltered.** The ruleset is published only after background
  indexing. The desktop check shows the first load unfiltered and the next load blocked. Faster first activation is
  a possible improvement (for example, indexing at first run before the first navigation), but it is not done yet.

## Ruleset build (`tools/adblock/convert.py`, Python, no host tool needed)
- The output format is `unindexed_ruleset.cc`: `varint32 size + FilteringRules` chunks of 1000 rules.
- Parsing follows `tools/rule_parser/{rule_parser,rule}.cc`:
  - anchors `|`, `||` and right `|`;
  - wildcard trimming;
  - pattern type;
  - element / activation types, `third-party`, `domain=` (sorted the same way), and `match-case`.
- Skipped, as Chromium does: unknown or unsupported options, regexp, `$document` on block rules, and element hiding.
- Hosts files become `||host^$third-party`, so visiting the host directly still works.

## Lists and licences (attribution required, no non-commercial lists)
| List | Licence | Obligation |
|---|---|---|
| EasyList, EasyPrivacy | GPLv3 or CC BY-SA 3.0 (dual), https://easylist.to/pages/licence.html | credit; the converted ruleset is published under CC BY-SA 3.0 (`adblock/README.md`, snapshots in `adblock/sources/`) |
| AdAway default hosts | CC BY 3.0 (file header) | credit |
| Excluded | DuckDuckGo TDS (CC BY-NC-SA), uBlock filters (GPLv3 only), Peter Lowe (unclear) | - |

Pending: in-app attribution (an about/credits entry), which is NOT DONE yet.

## Verification
1. **Unit tests** (`tests/test_adblock.py`) cover:
   - parser semantics against the Chromium rule_parser behaviour;
   - unsupported rules being skipped;
   - hosts conversion and the ruleset round trip;
   - the pinned SHA and series order;
   - the E2E hosts being present in the bundled ruleset;
   - the verdict logic.
2. **Desktop component, real Chromium 156 matcher** (`tools/adblock/desktop_sanity.py`, Chrome for Testing
   156.0.8078.4, headless). The ruleset is pre-installed as the "Subresource Filter Rules" component, and activation
   is forced with `--enable-features=SubresourceFilter:activation_scope/all_sites/activation_state/enabled`.
   - The ruleset indexed without error: 4.7 MB became 8.5 MB indexed, and Local State `ruleset_version.format` = 38.
   - Baseline (no ruleset): `no_blocker`. All 3 ad/tracker hosts were requested.
   - With the ruleset: load 1 was unfiltered (indexing not finished); load 2 was `blocked`. `ib.adnxs.com`,
     `www.google-analytics.com` and `sb.scorecardresearch.com` got 0 server hits, while the first-party script and
     the control third-party script loaded.
   - Evidence: `evidence/adblock-2026-10-18/desktop_sanity_chromium156.json`.
   - Pitfall: `--force-fieldtrials` + `--enable-features=SubresourceFilter<Trial` did not attach the params in this
     binary. The `Feature:k/v` form did.
3. **Device E2E** (`scripts/ci/advanced_e2e.py` section 4, prints `ADBLOCK_E2E PASS|FAIL|NOT_RUN`) is NOT RUN yet.
   - A page on `news.example.com` loads scripts and a pixel from the 3 listed hosts (mapped to the runner, so
     nothing leaves it), plus 2 controls.
   - PASS = 0 server hits on all ad hosts while both controls load.
   - It makes up to 3 attempts (because of the startup indexing), and all of them are recorded.
