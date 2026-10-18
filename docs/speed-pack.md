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

Desktop component check (evidence/speed-2026-10-18/desktop-harness-cft156.json; CfT 156, same harness server,
24 MiB at 1 MiB/s per connection): defaults (3 connections) **8.08 s**, Swiftra values (5) **4.87 s** (1.66x), single
connection would be 24 s. File complete in both.

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
