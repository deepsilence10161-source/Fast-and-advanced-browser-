# Swiftra Speed Pack (patch 0016) and speed measurement

Status 2026-10-18: patch, tests (tests/test_speedpack.py) and harness written; desktop component check PASS;
**device build/E2E NOT RUN yet** (next build after the 0011 builds).

## Honest scope
"100x faster than Chrome" is not physically possible for page loads or downloads: both are bounded by the network
(latency x round trips, link bandwidth). What a browser can do, and Swiftra does, measurably:
1. **Fewer bytes / requests**: the ad & tracker blocker (0012/0013) removes whole request chains.
2. **More parallelism**: parallel downloading with 5 connections (Chromium/Chrome default: 3).
3. **Chrome's own performance experiments**: Chrome stable gets them from Google's Finch server; Swiftra cannot
   contact that server, so before 0016 it ran plain code defaults. 0016 compiles the audited subset in.
Every claim must come from scripts/ci/speed_e2e.py results on the device (evidence/speed-*/).

## Mechanism (source facts @155.0.8059.80, gitiles)
* components/variations/service/BUILD.gn: `fieldtrial_testing_enabled = force_enable || (!disable_fieldtrial_testing_config && !(is_android && is_chrome_branded))`.
* variations_field_trial_creator.cc: non-branded builds apply the testing config unless `--disable-field-trial-config`
  / `--variations-server-url`; `used_testing_config` -> no seed is used. Nothing is downloaded.
* tools/variations/fieldtrial_to_struct.py compiles the JSON into fieldtrial_testing_config.cc
  (verified in the sandbox with the @155 generator + schema: upstream 474 KB -> pack 65 KB, PASS).
* 0016 keeps 80 audited upstream studies (first experiment, android only, pinned name + features: drift = build error)
  + `SwiftraParallelDownloading`. Upstream has 1128 studies (532 with android).
* args.gn: `disable_fieldtrial_testing_config = false` (was true since c2c because the FULL config contains
  Google-contacting studies such as MaliciousApkDownloadCheck).
* Device check: shield_e2e variations step (chrome://version/?show-variations-cmd) -> speedpack_check.py:
  `speedpack_only` required; any upstream study outside the pack = FAIL. The shield_e2e network audit still fails on
  any Google host contact.

## Download acceleration (SwiftraParallelDownloading)
components/download/internal/common/parallel_download_utils.cc @155 defaults: request_count 3, min_slice_size
1365333, remaining time 2 s; kParallelDownloading is enabled by default on Android. Parallel requests need HTTP/1.1
(or H2/QUIC flags), ETag or Last-Modified, Accept-Ranges, Content-Length (download_job_factory.cc).
Swiftra: request_count 5 (HTTP/1.1 allows 6 per host, one stays free), min_slice_size 512 KiB, remaining 1 s.
Helps on servers that cap per-connection speed; it cannot exceed the link's bandwidth.

HTTP/2 and QUIC (checked @155): `kUseParallelRequestsForHTTP2` and `kUseParallelRequestsForQUIC` are both
`FEATURE_ENABLED_BY_DEFAULT` (`download_features.cc`), so the slices are also requested from H2/QUIC servers. The
"HTTP/1.1 only" comment in `download_job_factory.cc` is stale. But on H2/QUIC the slices are streams on the **same**
connection (same session key), not extra TCP/QUIC connections. So the measured 1.66x applies to HTTP/1.1 servers or
servers that limit each request. On a CDN serving H2/QUIC the gain can be small or zero. The device harness uses an
HTTP/1.1 server, so its number must be reported as "HTTP/1.1 server, 1 MiB/s per connection", not as a general claim.

Desktop component check (evidence/speed-2026-10-18/desktop-harness-cft156.json; CfT 156, same harness server,
24 MiB at 1 MiB/s per connection): defaults (3 connections) **8.08 s**, Swiftra values (5) **4.87 s** (1.66x), single
connection would be 24 s. File complete in both.

## Turbo Download: one connection per slice on HTTP/2 and QUIC (patch 0017; build and device run pending)
- Gap (above): on H2/QUIC the slices share one connection. 0017 gives every slice request its own `net::SocketTag`
  on Android (own uid, a traffic-accounting label; feature `SwiftraSliceConnections`, default on). The tag is part of
  the HTTP/1.1 pool group, `SpdySessionKey` and `QuicSessionKey`, so each slice opens its own connection. Path checked
  @155: `ParallelDownloadJob::CreateRequest` -> `DownloadUrlParameters` -> `CreateResourceRequest` ->
  `ResourceRequest::socket_tag` -> `url_loader_util.cc` `set_socket_tag`. Tagged requests never enter the
  HappyEyeballsV3 pool, whose `HttpStreamKey` CHECKs for an empty tag.
- Load on the server is the same as Chromium's HTTP/1.1 behaviour (same number of connections), and only for
  downloads that Chromium already splits (strong validator, ranges, size).
- Device measurement: `scripts/ci/h2_dl_server.py`, an HTTP/2-only TLS server (ALPN h2) that paces each connection to
  1 MiB/s, shared by its streams. It records the connection id of every stream. `speed_e2e.py` downloads the same
  24 MiB file from it in both modes (`chromium_defaults` adds `--disable-features=SwiftraSliceConnections`) and
  reports `h2_download_s` and `h2_conns`. Local check of the server with curl (2026-10-18): 4 ranges on 1 connection
  3.99 s, on 4 connections 1.00 s (4 MiB), bytes identical.
- Expected on the device: defaults about 24 s on 1 connection; Swiftra 5 connections. This is a model of a
  per-connection limit, so the device number must be reported with that condition. On a link that is already full
  with one connection there is no gain. `SocketTag` is a no-op off Android, so there is no desktop proof.

## Excluded (examples, reason)
PreconnectFromKeyedService (periodic pings to the search engine), IncreaseHttp3Usage (google.com QUIC hints),
PreconnectCreateNewTab, OptimizationGuide*/OptGuide* (Google hint fetches), DsePreload*/ZeroSuggest*/Omnibox*/AIM*/Glic*
(search-provider or Google features), MaliciousApkDownloadCheck (APK pings), DiskCacheBackendExperiment (new SQL cache
backend), UsePersistentCacheForCodeCache, DomStorageSqliteInMemory, V8Turbolev, JavalessRendererExperimentOn,
SkiaGraphite (experimental engines), ChromeEnableDnsPlatform (Secure-DNS path), all UI/IPH studies.

## Measurement harness: scripts/ci/speed_e2e.py
Same APK, same device, modes alternated A B A B: `chromium_defaults` (`--disable-field-trial-config
--disable-features=SwiftraAdBlock`) vs `swiftra`. Local HTTPS server (adb reverse, mapped hosts, nothing leaves
the runner) with 60 ms latency per response (ad servers 150 ms) and 250 KiB/s per connection. Page: 4 CSS, 8 JS,
hero image (LCP), 18 images, ad chain (adnxs loader -> 3 ad iframes, GA, scorecardresearch). Fresh ?r= per load.
Output: medians of load/LCP/FCP/DCL, server requests/bytes/ad requests; download seconds, connections, coverage,
file on /sdcard/Download. `chromium_defaults` is NOT Google Chrome (no Finch); a Chrome comparison is only claimed from
a real Chrome run.

## ART compilation of the Java code (researched 2026-10-18; measurement running, nothing built yet)
- A sideloaded APK (GitHub release, `adb install`, tapping the file) is installed with `[status=verify]`. Java runs
  interpreted/JIT until background dexopt (idle + charging) compiles from the app's own JIT profile. Play Store
  installs get a cloud or baseline profile compiled at install time
  (developer.android.com/topic/performance/baselineprofiles/manually-create-measure and .../debug-baseline-profiles).
  So on day one a sideloaded Swiftra can start slower than a Play-installed Chrome. This is a parity gap, not a lead.
- A `baseline.prof` inside the APK is **not** used by a sideloaded install on its own. The Jetpack ProfileInstaller
  library has to copy it into the ART profile (compiled at the next background dexopt), or the profile must be
  installed together with the APK as a `.dm` (`adb install-multiple`).
- Chromium @155: `enable_baseline_profiles` / `enable_startup_profiles` are declared false in
  `build/config/android/config.gni`. `build/android/gyp/binary_baseline_profile.py` (profgen wrapper) exists, but no GN
  template calls it, and profgen is not in the checkout (`third_party/android_build_tools`). R8 still accepts
  `--art-profile` (`proguard.py`). `third_party/androidx:androidx_profileinstaller_profileinstaller_java` (1.5.0) is in
  the tree, visibility-restricted, and not used by Chrome.
- profgen source: AOSP `platform/tools/base/profgen` (+ `profgen-cli`), Apache-2.0. It is not published as its own
  Maven artifact. The library classes (`com/android/tools/profgen/*`, 99 entries) are inside
  `com.android.tools.build:gradle:9.4.1` (checked 2026-10-18). A small driver plus kotlin-stdlib could produce
  baseline.prof/.profm at build time. It is a build tool only; nothing of it ships in the APK.
- Profile input: `art_startup.py` dumps the JIT profile ART collected (`pm dump-profiles --dump-classes-and-methods`,
  `jit_profile.txt.gz`, this APK's R8 names). For a new build, map it with that build's R8 mapping or collect it again.
- Gate: `scripts/ci/art_startup.py` measures cold start in the install, speed-profile and speed states on the
  device. Wiring a profile in (HRF profile from the startup trace -> R8 `--art-profile` -> profgen -> assets/dexopt +
  ProfileInstaller) is done only if that gap is clearly larger than the noise.

## Compiler-level options (researched, not applied)
* `is_high_end_android = true` for arm64/x64 (build/config/android/config.gni:33) -> `optimize_for_size = false`:
  Swiftra already compiles for speed.
* PGO: DEPS has profile hooks for android-arm32 and android-desktop-x64 only, and `chrome/build/android-arm64.pgo.txt`
  does not exist at the tag -> no public arm64 profile; not applied.
* ThinLTO (`use_thin_lto`, settable without official build): full rebuild of every object + long link on the free
  4-core runner, gain a few percent; deferred until a build-time budget exists. `is_official_build` stays false
  (privacy: UMA/crash upload paths).

## Pack contents (80 upstream studies)
| group | study | experiment | features |
|---|---|---|---|
| network | `AsyncDnsQuicJob` | Enabled | AsyncDnsQuicJob |
| network | `OptimisticDnsForQuic` | Enabled | AdjustQuicSlowTimerDelay, OptimisticDnsForQuic, QuicSlowTimerBasedOnRTT |
| network | `OptimisticDnsForTcp` | Enabled_20260709 | AdjustIPv6FallbackTime, EnableIntermediateDnsResults, IPv6FallbackBasedOnRTT, OptimisticDnsForTcp |
| network | `EnableQuicReadMultipleAndUdpGRO` | EnabledQuicUseReadMultipleAndUdpGro_20260729 | EnableUdpGro, QuicUseReadMultiple |
| network | `QuicSocketSendBufferSize` | Enabled | QuicSocketSendBufferSize |
| network | `NetTaskScheduler` | Enabled_SpdyDrainFix | DrainSpdySessionSynchronouslyOnRemoteEndpointDisconnect, NetTaskScheduler / off: NetTaskScheduler2, NetTaskSchedulerHostResolver, NetworkServicePerPriorityTaskQueues |
| network | `NetworkServiceIncreasedPriorityWhileLoading` | WhileLoading | NetworkServiceIncreasedPriorityWhileLoading |
| network | `EarlyCookieLoadOnPreconnect` | Enabled | EarlyCookieLoadOnPreconnect |
| network | `SQLitePersistentCookieStoreEarlyInit` | Enabled | SQLitePersistentCookieStoreEarlyInit |
| network | `SimpleCachePrefetchExperiment2` | Enabled_64KiB | SimpleCachePrefetchExperiment2 |
| network | `HttpCacheNoVarySearch` | Enabled_NVS_HttpCache_And_Omnibox_Prefetch | HttpCacheNoVarySearch |
| network | `NoVarySearchCacheLoadOnSeparateTaskRunner` | Enabled | NoVarySearchCacheLoadOnSeparateTaskRunner |
| network | `AddressSorterConnectCache` | Enabled | AddressSorterConnectCache |
| network | `DnsHttpsSvcbTimeout` | Enabled | UseDnsHttpsSvcb |
| network | `CloseQuicSessionsOnPreFreeze` | Enabled_20260601 | CloseQuicSessionsOnPreFreeze |
| network | `NetworkQualityEstimatorAsyncNotifyHeadersReceived` | Experiment | NetworkQualityEstimatorAsyncNotifyHeadersReceived |
| network | `OffloadAcceptCHFrameCheck` | Enabled | OffloadAcceptCHFrameCheck |
| network | `IgnoreQuicCryptoConfigMemoryPressure` | Enabled | IgnoreQuicCryptoConfigMemoryPressure |
| network | `QuicIgnoreRedundantOnNetworkMadeDefault` | Enabled_20260603 | QuicIgnoreRedundantOnNetworkMadeDefault |
| loading | `LCPPDeferUnusedPreload` | EnableWithPostTask_20240426 | LCPPDeferUnusedPreload |
| loading | `LCPPLazyLoadImagePreload` | EnableWithNativeLazyLoading_20231113 | LCPPLazyLoadImagePreload |
| loading | `LCPTimingPredictorPrerender2` | Enabled | LCPTimingPredictorPrerender2 |
| loading | `SpeculativeImageDecodes` | Enabled | PreventDuplicateImageDecodes, SpeculativeImageDecodes |
| loading | `DecodeScriptsInBlink` | Enabled_20260714 | DecodeScriptsInBlink |
| loading | `PaintHoldingOOPIF` | Enabled | PaintHoldingForIframes |
| loading | `Path2DPaintCache` | Enabled | Path2DPaintCache |
| loading | `SpeculativeServiceWorkerWarmUp` | Enabled_05m_05c_20250214 | SpeculativeServiceWorkerWarmUp |
| loading | `ServiceWorkerSyntheticResponse` | EnabledWithNetworkServiceDelegation | ServiceWorkerSyntheticResponse, URLLoaderUseProvidedResponseBodyStream |
| loading | `StreamlineRendererInit` | Enabled | StreamlineRendererInit |
| loading | `AndroidSpareRendererCreation_V3` | FilterNTPNoMemoryThresholdWithKill | AndroidWarmUpSpareRendererWithTimeout, OverrideAndroidOmniboxSpareRendererDelay, ResumeNavigationWithSpeculativeRFHProcessGone, SpareRendererProcessPriority |
| loading | `PreferWarmRendererProcess` | Enabled | PreferWarmRendererProcess |
| loading | `AutoSpeculationRules` | Enabled_20231201 | AutoSpeculationRules |
| loading | `Prerender2FallbackPrefetchSpecRules` | Enabled_NoTimeout_Burst | Prerender2FallbackPrefetchSpecRules |
| loading | `PrefetchPrerenderIntegration` | Enabled | PrefetchPrerenderIntegration |
| loading | `PrefetchCancelUnrelatedPrefetch` | Enabled_Cancel_NotServable | PrefetchCancelUnrelatedPrefetch, PrefetchMatchResolverUnblockAsync |
| loading | `SpeculationRulesPrefetchLimitsForEagerModerateAndroid` | Enabled_6 | PrefetchEagerLimit, PrefetchModerateLimit |
| loading | `ZstdForCrossSiteSpeculationRulesPrefetch` | Enabled | ZstdForCrossSiteSpeculationRulesPrefetch |
| loading | `ReactivePrefetchAndroidDiscardBody` | Enabled | LoadingPredictorPrefetchUseReadAndDiscardBody |
| loading | `PrefetchMultipleActiveSetSizeLimitForBase` | Enabled_2 | PrefetchMultipleActiveSetSizeLimitForBase |
| loading | `ProcessReuseOnPrerenderCOOPSwapAndroid` | Enabled | ProcessReuseOnPrerenderCOOPSwap |
| bfcache | `BFCachePerformanceManagerPolicy` | EnabledPolicy_CacheSize6_20230525 | BFCachePerformanceManagerPolicy, BackForwardCacheSize |
| bfcache | `BackForwardCacheMemoryControls` | Enabled | BackForwardCacheMemoryControls |
| bfcache | `AllowDatapipeDrainedAsBytesConsumerInBFCache` | Enabled | AllowDatapipeDrainedAsBytesConsumerInBFCache |
| bfcache | `BackForwardCacheCCNSIgnoreUnchangedCookies` | Enabled_20260401 | BackForwardCacheCCNSIgnoreUnchangedCookies |
| bfcache | `BackForwardCachePauseMicrotasks` | Enabled | BackForwardCachePauseMicrotasks |
| bfcache | `AsyncBeforeUnload` | Enabled | AsyncBeforeUnload |
| scheduling | `AndroidStartupImprovements` | Enabled | AndroidStartupImprovements |
| scheduling | `AndroidSystemFontPrewarming` | Enabled | AndroidSystemFontPrewarming |
| scheduling | `AndroidThreadPriority` | RaiseDisplayCriticalThreadPriorityV2 | AndroidThreadPriority |
| scheduling | `BrowserThreadPoolAdjustmentForAndroid` | thread_pool_default_20230920 | BrowserThreadPoolAdjustment |
| scheduling | `BackgroundThreadPoolPIGeneral` | Enabled_20260106 | BackgroundThreadPoolFieldTrial |
| scheduling | `ThreadPoolForegroundBlockingTimeouts` | Enabled_Moderate | ThreadPoolForegroundBlockingTimeouts |
| scheduling | `BusyLoopLessWhenCompositorGesture` | WithOptimization | BusyLoopAggressiveAfterCommittedLoad, BusyLoopLessWhenCompositorGesture, BusyLoopOnMainThread |
| scheduling | `YieldWithInputHint` | EnabledThrottling0ms | YieldWithInputHint |
| scheduling | `RestrictPendingInputEventTypeToBlockMainThread` | Enabled | RestrictPendingInputEventType |
| scheduling | `EnableADPFSeparateRendererMainSession` | Enabled | EnableADPFSeparateRendererMainSession |
| scheduling | `EnableADPFWorkloadReset` | Enabled | EnableADPFWorkloadReset |
| scheduling | `EarlyTopAppForSandboxedRenderer` | Enabled | EarlyTopAppForSandboxedRenderer |
| scheduling | `ShutdownPreNativeThreadPoolAfterStartupInBackground` | Enabled | ShutdownPreNativeThreadPoolAfterStartup |
| scheduling | `TweakApplicationPreload` | Enabled_MoveWarmUp | TweakApplicationPreloadMoveWarmUp / off: TweakApplicationPreloadLoadNativeFirst, TweakApplicationPreloadSkipNewInstance, TweakApplicationPreloadSkipWarmUp |
| scheduling | `PMLoadingPageVoter` | Enabled | PMLoadingPageVoter |
| cpu_gpu | `UtfConversionAsciiFastPath` | Enabled_20260810 | UtfConversionAsciiFastPath |
| cpu_gpu | `CacheGurlSchemeIsHttpOrHttpsResult` | Enabled_20260629 | CacheGurlSchemeIsHttpOrHttpsResult |
| cpu_gpu | `MojoDirectSharedMemoryAllocation` | Enabled | MojoDirectSharedMemoryAllocation |
| cpu_gpu | `ReduceMojoURLLoaderFactoryCloning` | Enabled | ReduceMojoURLLoaderFactoryCloning |
| cpu_gpu | `GrCacheLimits` | cache_96_256_8_default_20230911 | GrCacheLimitsFeature |
| cpu_gpu | `GpuPersistentCacheMetadata` | Enabled | GpuPersistentCacheMetadata |
| cpu_gpu | `PruneOldTransferCacheEntries` | Enabled | PruneOldTransferCacheEntries |
| v8 | `V8HomomorphicIC` | Enabled | V8Flag_homomorphic_ic |
| v8 | `V8MaxValidPolymorphicMapCount` | Enabled | V8MaxValidPolymorphicMapCount |
| v8 | `V8PreconfigureOldGen` | Enabled | V8PreconfigureOldGen |
| v8 | `V8SideStepTransitions` | Enabled | V8SideStepTransitions |
| v8 | `V8SparkplugPlus` | Enabled | V8Flag_sparkplug_plus |
| v8 | `V8SqrtAllocationLimits` | Enabled | V8Flag_sqrt_allocation_limits |
| v8 | `V8DateTimePatternGeneratorCacheEviction` | Enabled | V8Flag_intl_date_time_pattern_generator_cache_eviction |
| memory | `PartitionAllocMemoryReclaimer` | Interval_8sec | PartitionAllocMemoryReclaimer, PartitionAllocSortSmallerSlotSpanFreeLists, PartitionAllocStraightenLargerSlotSpanFreeLists / off: PartitionAllocSortActiveSlotSpans |
| memory | `PartitionAllocParameterTuningAndroid` | Enabled_20250305 | BlinkUseLargeEmptySlotSpanRingForBufferRoot, PartitionAllocAdjustSizeWhenInForeground, PartitionAllocLargeEmptySlotSpanRing |
| memory | `StatefulMemoryPressure` | Enabled | StatefulMemoryPressure |
| memory | `AndroidResourceMemoryOptimization` | Enabled | AndroidResourceMemoryOptimization |
| memory | `InhibitSQLReleaseCacheMemoryIfNeeded` | InhibitSQLReleaseCacheMemoryIfNeeded | InhibitSQLReleaseCacheMemoryIfNeeded |

Group reasons:
* **network**: Connection set-up and transfer: faster DNS/QUIC/TCP fallback, earlier cookie load, cache read-ahead, higher network-service priority while a page loads
* **loading**: Page rendering: LCP-critical-path prediction, speculative image decode, off-thread script decode, warm/spare renderer, same-site speculation-rules prefetch limits
* **bfcache**: Back/forward: more pages eligible for the back-forward cache, i.e. instant Back
* **scheduling**: Startup and input responsiveness: thread priorities, Android ADPF performance hints, thread-pool sizing, yielding to input
* **cpu_gpu**: CPU/GPU hot paths: ASCII UTF fast path, fewer Mojo clones, GPU cache limits / persistent shader metadata
* **v8**: JavaScript engine (V8) tuning: Sparkplug+, homomorphic inline caches, heap sizing
* **memory**: Memory: PartitionAlloc reclaim/tuning, memory-pressure handling (fewer tab reloads on low-RAM phones)

## arm64 PGO + orderfile (2026-10-18; build pending, device measurement NOT RUN)
- Build fix (2026-10-18): the first PGO builds (39133494814, 39145340622) stopped in `gn gen` at
  `assert(use_lld)` in `chrome_orderfile_config` (build/config/compiler/BUILD.gn:3207). @155, non-official Android
  builds link with mold by default (`use_mold` requires `!is_official_build`, compiler.gni), so `use_lld` is false. The
  arm64 PGO args now add `use_mold = false` (lld, as in official Chrome). `chromium_stage.sh` now prints the whole
  `gn gen` output on failure (before, `| tail -2` hid the error line).
  The next attempt (39146588456) passed that point and stopped at `build/timestamp.gni`'s default-toolchain assert
  in `android_clang_arm64_webview`: with `chrome_pgo_phase = 2`, android_webview/variables.gni adds a separate
  standalone-WebView toolchain, and official builds pass the assert only because they enable the 32-bit secondary
  ABI. The args now also set `chrome_pgo_phase_default_toolchain = 0` (read only by the WebView toolchain choice;
  the PGO compiler flags read `chrome_pgo_phase`). Swiftra does not ship WebView, so nothing else changes.
- Baseline kept: the 0011 arm64 APK (no PGO, no orderfile; build 39127525981, sha256
  `8954118e4f902086bd8b4c8267e8b8c9e327241ec60c9979d948080f4a3714fd`) is copied to the draft release
  `apk-b1-0011-arm64` before the PGO build replaces the state release asset.
- Method: `arm64-device-e2e.yml` input `ab_baseline_release=apk-b1-0011-arm64` runs `scripts/ci/ab_bench.py`. That
  installs new and baseline alternately (new, base, new, base) on the same Redroid, checks the sha256 of the installed
  base.apk each round, and measures cold start, bench.js and page load. Prints `AB_BENCH` with base/new ratios.
  The x64 build gets no PGO change and stays the control.
- **What:** arm64 builds (all variants except the a1 baseline) are compiled with `chrome_pgo_phase = 2` and linked with
  `chrome_orderfile_path = "//chrome/android/orderfiles/arm64/orderfile.arm64.out"` (`scripts/ci/chromium_stage.sh`).
- **Source of the profile (gitiles @155):** `tools/update_pgo_profiles.py` `_get_profile_path`: for target
  `android-arm64` official Chrome uses `chrome/android/orderfiles/arm64/pgo_profile.arm64.profdata`, "the PGO profile
  that is generated at the same commit as the orderfile" (crbug.com/372686816). It ships in the public CIPD package
  `chromium/chrome/android/orderfiles/arm64` (version `ow77FKiXziccanhdbAino-fPWdR4jHXcA1SJT58Q8cEC` pinned by
  `chrome/build/android-arm64.orderfile.txt`), which `gclient sync` already fetches (DEPS condition
  `checkout_android and non_git_source`). Package contents: `orderfile.arm64.out` (10.4 MB, 86,228 symbols) and
  `pgo_profile.arm64.profdata` (242.5 MB).
- **Why it was missing:** `pgo.gni` turns PGO on only for official builds, and `compiler.gni` picks the orderfile only
  when `enable_chrome_android_internal`. Swiftra stays non-official (privacy), so both are set explicitly.
- **What GN adds with it:** `-fprofile-use`, `-mllvm -pgo-cold-func-opt=minsize` (cold code smaller),
  `-enable-ext-tsp-block-placement=1`, `--call-graph-profile-sort`, and lld `--symbol-ordering-file`.
  `enable_separate_renderer_binary` is false @155, so no separate renderer profile is needed.
- **Guard:** the stage script stops with "PGO input missing" if either file is absent, and records their size, hash
  prefix and package version in the stage evidence. It never silently builds without PGO.
- **x64** has no android-x64 profile (GN would ask for `android-arm32`), so x64 stays unoptimised. It is the
  emulator target, and the non-PGO control.
- **Status:** this is parity with official Chrome arm64 (Chrome is built the same way), not a lead over it. The gain
  must be measured on arm64 against the non-PGO 0011 APK before any number is claimed.
