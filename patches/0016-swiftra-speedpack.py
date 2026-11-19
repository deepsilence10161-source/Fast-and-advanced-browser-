#!/usr/bin/env python3
"""Swiftra Speed Pack (transform, see scripts/ci/patches.py; design: docs/speed-pack.md).

Why: Chrome stable receives many performance features from Google's Finch server. Swiftra must not contact that
server, and patches/args.gn used to disable the whole field-trial testing config (it also contains studies that
ping Google, e.g. MaliciousApkDownloadCheck). Result: Swiftra ran with plain code defaults only -- slower than it
could be.

What: rewrite src/testing/variations/fieldtrial_testing_config.json so it contains ONLY the audited
performance studies below (first experiment = the one the testing config applies, platform android only),
plus Swiftra's own studies (SWIFTRA). patches/args.gn then sets disable_fieldtrial_testing_config = false.
The testing config is compiled into the binary and applied at startup instead of a seed
(components/variations/service/variations_field_trial_creator.cc @155: ApplyFieldTrialTestingConfig,
used_testing_config -> no seed); nothing is downloaded.

Audit rules for ALLOW (docs/speed-pack.md lists every study with its group reason):
  * performance / responsiveness / memory only; no UI change;
  * no request to Google or any third party (excluded: PreconnectFromKeyedService = periodic pings,
    IncreaseHttp3Usage = google.com hints, OptimizationGuide*, DsePreload*, ZeroSuggest*, Omnibox*, Glic*);
  * no new storage engine / experimental compiler tier (excluded: DiskCacheBackendExperiment sql,
    UsePersistentCacheForCodeCache, DomStorageSqliteInMemory, V8Turbolev, JavalessRenderer, SkiaGraphite);
  * no change to the Secure DNS path (excluded: ChromeEnableDnsPlatform).
Every entry pins (experiment name, enable_features, disable_features). If upstream changes a pinned study the
transform fails -- it never builds a silently different pack.
"""
import json
import os
import sys

CONFIG = "testing/variations/fieldtrial_testing_config.json"

# study -> (experiment name, enable_features, disable_features); params are copied from upstream verbatim.
ALLOW = {
    # --- network ---
    'AsyncDnsQuicJob': ('Enabled', ['AsyncDnsQuicJob'], []),
    'OptimisticDnsForQuic': ('Enabled', ['AdjustQuicSlowTimerDelay', 'OptimisticDnsForQuic', 'QuicSlowTimerBasedOnRTT'], []),
    'OptimisticDnsForTcp': ('Enabled_20260709', ['AdjustIPv6FallbackTime', 'EnableIntermediateDnsResults', 'IPv6FallbackBasedOnRTT', 'OptimisticDnsForTcp'], []),
    'EnableQuicReadMultipleAndUdpGRO': ('EnabledQuicUseReadMultipleAndUdpGro_20260729', ['EnableUdpGro', 'QuicUseReadMultiple'], []),
    'QuicSocketSendBufferSize': ('Enabled', ['QuicSocketSendBufferSize'], []),
    'NetTaskScheduler': ('Enabled_SpdyDrainFix', ['DrainSpdySessionSynchronouslyOnRemoteEndpointDisconnect', 'NetTaskScheduler'], ['NetTaskScheduler2', 'NetTaskSchedulerHostResolver', 'NetworkServicePerPriorityTaskQueues']),
    'NetworkServiceIncreasedPriorityWhileLoading': ('WhileLoading', ['NetworkServiceIncreasedPriorityWhileLoading'], []),
    'EarlyCookieLoadOnPreconnect': ('Enabled', ['EarlyCookieLoadOnPreconnect'], []),
    'SQLitePersistentCookieStoreEarlyInit': ('Enabled', ['SQLitePersistentCookieStoreEarlyInit'], []),
    'SimpleCachePrefetchExperiment2': ('Enabled_64KiB', ['SimpleCachePrefetchExperiment2'], []),
    'HttpCacheNoVarySearch': ('Enabled_NVS_HttpCache_And_Omnibox_Prefetch', ['HttpCacheNoVarySearch'], []),
    'NoVarySearchCacheLoadOnSeparateTaskRunner': ('Enabled', ['NoVarySearchCacheLoadOnSeparateTaskRunner'], []),
    'AddressSorterConnectCache': ('Enabled', ['AddressSorterConnectCache'], []),
    'DnsHttpsSvcbTimeout': ('Enabled', ['UseDnsHttpsSvcb'], []),
    'CloseQuicSessionsOnPreFreeze': ('Enabled_20260601', ['CloseQuicSessionsOnPreFreeze'], []),
    'NetworkQualityEstimatorAsyncNotifyHeadersReceived': ('Experiment', ['NetworkQualityEstimatorAsyncNotifyHeadersReceived'], []),
    'OffloadAcceptCHFrameCheck': ('Enabled', ['OffloadAcceptCHFrameCheck'], []),
    'IgnoreQuicCryptoConfigMemoryPressure': ('Enabled', ['IgnoreQuicCryptoConfigMemoryPressure'], []),
    'QuicIgnoreRedundantOnNetworkMadeDefault': ('Enabled_20260603', ['QuicIgnoreRedundantOnNetworkMadeDefault'], []),
    # --- loading ---
    'LCPPDeferUnusedPreload': ('EnableWithPostTask_20240426', ['LCPPDeferUnusedPreload'], []),
    'LCPPLazyLoadImagePreload': ('EnableWithNativeLazyLoading_20231113', ['LCPPLazyLoadImagePreload'], []),
    'LCPTimingPredictorPrerender2': ('Enabled', ['LCPTimingPredictorPrerender2'], []),
    'SpeculativeImageDecodes': ('Enabled', ['PreventDuplicateImageDecodes', 'SpeculativeImageDecodes'], []),
    'DecodeScriptsInBlink': ('Enabled_20260714', ['DecodeScriptsInBlink'], []),
    'PaintHoldingOOPIF': ('Enabled', ['PaintHoldingForIframes'], []),
    'Path2DPaintCache': ('Enabled', ['Path2DPaintCache'], []),
    'SpeculativeServiceWorkerWarmUp': ('Enabled_05m_05c_20250214', ['SpeculativeServiceWorkerWarmUp'], []),
    'ServiceWorkerSyntheticResponse': ('EnabledWithNetworkServiceDelegation', ['ServiceWorkerSyntheticResponse', 'URLLoaderUseProvidedResponseBodyStream'], []),
    'StreamlineRendererInit': ('Enabled', ['StreamlineRendererInit'], []),
    'AndroidSpareRendererCreation_V3': ('FilterNTPNoMemoryThresholdWithKill', ['AndroidWarmUpSpareRendererWithTimeout', 'OverrideAndroidOmniboxSpareRendererDelay', 'ResumeNavigationWithSpeculativeRFHProcessGone', 'SpareRendererProcessPriority'], []),
    'PreferWarmRendererProcess': ('Enabled', ['PreferWarmRendererProcess'], []),
    'AutoSpeculationRules': ('Enabled_20231201', ['AutoSpeculationRules'], []),
    'Prerender2FallbackPrefetchSpecRules': ('Enabled_NoTimeout_Burst', ['Prerender2FallbackPrefetchSpecRules'], []),
    'PrefetchPrerenderIntegration': ('Enabled', ['PrefetchPrerenderIntegration'], []),
    'PrefetchCancelUnrelatedPrefetch': ('Enabled_Cancel_NotServable', ['PrefetchCancelUnrelatedPrefetch', 'PrefetchMatchResolverUnblockAsync'], []),
    'SpeculationRulesPrefetchLimitsForEagerModerateAndroid': ('Enabled_6', ['PrefetchEagerLimit', 'PrefetchModerateLimit'], []),
    'ZstdForCrossSiteSpeculationRulesPrefetch': ('Enabled', ['ZstdForCrossSiteSpeculationRulesPrefetch'], []),
    'ReactivePrefetchAndroidDiscardBody': ('Enabled', ['LoadingPredictorPrefetchUseReadAndDiscardBody'], []),
    'PrefetchMultipleActiveSetSizeLimitForBase': ('Enabled_2', ['PrefetchMultipleActiveSetSizeLimitForBase'], []),
    'ProcessReuseOnPrerenderCOOPSwapAndroid': ('Enabled', ['ProcessReuseOnPrerenderCOOPSwap'], []),
    # --- bfcache ---
    'BFCachePerformanceManagerPolicy': ('EnabledPolicy_CacheSize6_20230525', ['BFCachePerformanceManagerPolicy', 'BackForwardCacheSize'], []),
    'BackForwardCacheMemoryControls': ('Enabled', ['BackForwardCacheMemoryControls'], []),
    'AllowDatapipeDrainedAsBytesConsumerInBFCache': ('Enabled', ['AllowDatapipeDrainedAsBytesConsumerInBFCache'], []),
    'BackForwardCacheCCNSIgnoreUnchangedCookies': ('Enabled_20260401', ['BackForwardCacheCCNSIgnoreUnchangedCookies'], []),
    'BackForwardCachePauseMicrotasks': ('Enabled', ['BackForwardCachePauseMicrotasks'], []),
    'AsyncBeforeUnload': ('Enabled', ['AsyncBeforeUnload'], []),
    # --- scheduling ---
    'AndroidStartupImprovements': ('Enabled', ['AndroidStartupImprovements'], []),
    'AndroidSystemFontPrewarming': ('Enabled', ['AndroidSystemFontPrewarming'], []),
    'AndroidThreadPriority': ('RaiseDisplayCriticalThreadPriorityV2', ['AndroidThreadPriority'], []),
    'BrowserThreadPoolAdjustmentForAndroid': ('thread_pool_default_20230920', ['BrowserThreadPoolAdjustment'], []),
    'BackgroundThreadPoolPIGeneral': ('Enabled_20260106', ['BackgroundThreadPoolFieldTrial'], []),
    'ThreadPoolForegroundBlockingTimeouts': ('Enabled_Moderate', ['ThreadPoolForegroundBlockingTimeouts'], []),
    'BusyLoopLessWhenCompositorGesture': ('WithOptimization', ['BusyLoopAggressiveAfterCommittedLoad', 'BusyLoopLessWhenCompositorGesture', 'BusyLoopOnMainThread'], []),
    'YieldWithInputHint': ('EnabledThrottling0ms', ['YieldWithInputHint'], []),
    'RestrictPendingInputEventTypeToBlockMainThread': ('Enabled', ['RestrictPendingInputEventType'], []),
    'EnableADPFSeparateRendererMainSession': ('Enabled', ['EnableADPFSeparateRendererMainSession'], []),
    'EnableADPFWorkloadReset': ('Enabled', ['EnableADPFWorkloadReset'], []),
    'EarlyTopAppForSandboxedRenderer': ('Enabled', ['EarlyTopAppForSandboxedRenderer'], []),
    'ShutdownPreNativeThreadPoolAfterStartupInBackground': ('Enabled', ['ShutdownPreNativeThreadPoolAfterStartup'], []),
    'TweakApplicationPreload': ('Enabled_MoveWarmUp', ['TweakApplicationPreloadMoveWarmUp'], ['TweakApplicationPreloadLoadNativeFirst', 'TweakApplicationPreloadSkipNewInstance', 'TweakApplicationPreloadSkipWarmUp']),
    'PMLoadingPageVoter': ('Enabled', ['PMLoadingPageVoter'], []),
    # --- cpu_gpu ---
    'UtfConversionAsciiFastPath': ('Enabled_20260810', ['UtfConversionAsciiFastPath'], []),
    'CacheGurlSchemeIsHttpOrHttpsResult': ('Enabled_20260629', ['CacheGurlSchemeIsHttpOrHttpsResult'], []),
    'MojoDirectSharedMemoryAllocation': ('Enabled', ['MojoDirectSharedMemoryAllocation'], []),
    'ReduceMojoURLLoaderFactoryCloning': ('Enabled', ['ReduceMojoURLLoaderFactoryCloning'], []),
    'GrCacheLimits': ('cache_96_256_8_default_20230911', ['GrCacheLimitsFeature'], []),
    'GpuPersistentCacheMetadata': ('Enabled', ['GpuPersistentCacheMetadata'], []),
    'PruneOldTransferCacheEntries': ('Enabled', ['PruneOldTransferCacheEntries'], []),
    # --- v8 ---
    'V8HomomorphicIC': ('Enabled', ['V8Flag_homomorphic_ic'], []),
    'V8MaxValidPolymorphicMapCount': ('Enabled', ['V8MaxValidPolymorphicMapCount'], []),
    'V8PreconfigureOldGen': ('Enabled', ['V8PreconfigureOldGen'], []),
    'V8SideStepTransitions': ('Enabled', ['V8SideStepTransitions'], []),
    'V8SparkplugPlus': ('Enabled', ['V8Flag_sparkplug_plus'], []),
    'V8SqrtAllocationLimits': ('Enabled', ['V8Flag_sqrt_allocation_limits'], []),
    'V8DateTimePatternGeneratorCacheEviction': ('Enabled', ['V8Flag_intl_date_time_pattern_generator_cache_eviction'], []),
    # --- memory ---
    'PartitionAllocMemoryReclaimer': ('Interval_8sec', ['PartitionAllocMemoryReclaimer', 'PartitionAllocSortSmallerSlotSpanFreeLists', 'PartitionAllocStraightenLargerSlotSpanFreeLists'], ['PartitionAllocSortActiveSlotSpans']),
    'PartitionAllocParameterTuningAndroid': ('Enabled_20250305', ['BlinkUseLargeEmptySlotSpanRingForBufferRoot', 'PartitionAllocAdjustSizeWhenInForeground', 'PartitionAllocLargeEmptySlotSpanRing'], []),
    'StatefulMemoryPressure': ('Enabled', ['StatefulMemoryPressure'], []),
    'AndroidResourceMemoryOptimization': ('Enabled', ['AndroidResourceMemoryOptimization'], []),
    'InhibitSQLReleaseCacheMemoryIfNeeded': ('InhibitSQLReleaseCacheMemoryIfNeeded', ['InhibitSQLReleaseCacheMemoryIfNeeded'], []),
}

# Studies whose enable_features are deliberately narrowed (search-prefetch part dropped: DSE related).
NARROWED = {"HttpCacheNoVarySearch"}

# Swiftra's own studies (not in upstream). Download acceleration:
# components/download/internal/common/parallel_download_utils.cc @155 defaults: request_count 3,
# min_slice_size 1365333, parallel_request_remaining_time 2 s (Chrome's values unless Finch overrides).
# Swiftra: 5 connections (HTTP/1.1 allows 6 per host; one stays free for the page), 512 KiB slices and
# parallel requests already when >= 1 s of transfer remains.
SWIFTRA = {
    "SwiftraParallelDownloading": {
        "platforms": ["android"],
        "experiments": [{
            "name": "Swiftra",
            "params": {"request_count": "5", "min_slice_size": "524288",
                       "parallel_request_remaining_time": "1", "parallel_request_delay": "0"},
            "enable_features": ["ParallelDownloading"],
        }],
    },
}


def build(upstream):
    out, seen = {}, {}
    for study, (exp_name, enable, disable) in ALLOW.items():
        if study not in upstream:
            raise SystemExit(f"[speedpack] study missing upstream: {study}")
        cfgs = [c for c in upstream[study] if "android" in c.get("platforms", [])]
        if not cfgs:
            raise SystemExit(f"[speedpack] study has no android config: {study}")
        exp = cfgs[0]["experiments"][0]
        up_enable = exp.get("enable_features", [])
        if exp.get("name") != exp_name or exp.get("disable_features", []) != disable or (
                up_enable != enable and not (study in NARROWED and set(enable) <= set(up_enable))):
            raise SystemExit(f"[speedpack] upstream changed {study}: {exp.get('name')} {up_enable} "
                             f"{exp.get('disable_features', [])}")
        new_exp = {"name": exp_name}
        if exp.get("params"):
            new_exp["params"] = dict(exp["params"])
        if enable:
            new_exp["enable_features"] = list(enable)
        if disable:
            new_exp["disable_features"] = list(disable)
        cfg = {"platforms": ["android"], "experiments": [new_exp]}
        for k in ("form_factors", "is_low_end_device", "min_os_version"):
            if k in cfgs[0]:
                cfg[k] = cfgs[0][k]
        for f in enable + disable:
            if f in seen:
                raise SystemExit(f"[speedpack] feature {f} in {study} and {seen[f]}")
            seen[f] = study
        out[study] = [cfg]
    for study, cfg in SWIFTRA.items():
        if study in upstream or study in out:
            raise SystemExit(f"[speedpack] name clash: {study}")
        for e in cfg["experiments"]:
            for f in e.get("enable_features", []) + e.get("disable_features", []):
                if f in seen:
                    raise SystemExit(f"[speedpack] feature {f} in {study} and {seen[f]}")
                seen[f] = study
        out[study] = [cfg]
    return dict(sorted(out.items()))


def main(src):
    path = os.path.join(src, CONFIG)
    with open(path, encoding="utf-8") as f:
        upstream = json.load(f)
    pack = build(upstream)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=4, sort_keys=False)
        f.write("\n")
    print(f"[speedpack] {len(pack)} studies kept of {len(upstream)}", file=sys.stderr)
    print(f"TOUCHED {CONFIG}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: 0016-swiftra-speedpack.py <src>")
    main(sys.argv[1])
