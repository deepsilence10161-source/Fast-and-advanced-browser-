"""Swiftra Speed Pack (patches/0016-swiftra-speedpack.py) + device check (scripts/ci/speedpack_check.py)
+ pure helpers of scripts/ci/speed_e2e.py. Offline: upstream testing config @155.0.8059.80 is in tools/speedpack/."""
import copy
import gzip
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
import speedpack_check  # noqa: E402

UPSTREAM_GZ = os.path.join(ROOT, "tools", "speedpack", "fieldtrial_testing_config_155.0.8059.80.json.gz")


@pytest.fixture(scope="module")
def upstream():
    with gzip.open(UPSTREAM_GZ, "rt", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def mod():
    return speedpack_check.load_pack()


def test_pack_builds_android_only(upstream, mod):
    pack = mod.build(upstream)
    assert len(pack) == len(mod.ALLOW) + len(mod.SWIFTRA) == 81
    for study, cfgs in pack.items():
        assert len(cfgs) == 1 and cfgs[0]["platforms"] == ["android"], study
        assert len(cfgs[0]["experiments"]) == 1, study


# Name matches a banned word but the feature is local only: it starts a spare renderer process 500 ms after the
# omnibox is focused (components/omnibox/common/omnibox_features.cc:318 @155: "Override the delay to create a
# spare renderer when the omnibox is focused on Android"), a local process, no network request.
LOCAL_OK = {"OverrideAndroidOmniboxSpareRendererDelay"}


def test_no_google_contact_or_ui_studies(upstream, mod):
    pack = mod.build(upstream)
    banned_prefixes = ("OptimizationGuide", "OptGuide", "Glic", "Omnibox", "DsePreload", "ZPS", "ZeroSuggest", "AIM",
                       "Aim", "Feed", "Safe", "MaliciousApk", "UploadReport", "Prewarm", "Instant", "IPH")
    banned = {"PreconnectFromKeyedService", "IncreaseHttp3Usage", "DiskCacheBackendExperiment",
              "UsePersistentCacheForCodeCache", "DomStorageSqliteInMemory", "V8Turbolev", "JavalessRendererExperimentOn",
              "SkiaGraphite", "ChromeEnableDnsPlatform", "PreconnectCreateNewTab", "HttpsFirstModeV2ForTypicallySecureUsers"}
    for study, cfgs in pack.items():
        assert study not in banned
        assert not study.startswith(banned_prefixes), study
        e = cfgs[0]["experiments"][0]
        for f in e.get("enable_features", []) + e.get("disable_features", []):
            if f in LOCAL_OK:
                continue
            assert not any(w in f for w in ("Google", "Glic", "Omnibox", "SafeBrowsing", "SearchPrefetch", "Aim")), (study, f)
        for v in e.get("params", {}).values():
            assert "google" not in v.lower(), (study, v)


def test_swiftra_parallel_download(upstream, mod):
    pack = mod.build(upstream)
    e = pack["SwiftraParallelDownloading"][0]["experiments"][0]
    assert e["enable_features"] == ["ParallelDownloading"]
    # keys of components/download/public/common/parallel_download_configs.h @155
    assert e["params"] == {"request_count": "5", "min_slice_size": "524288",
                           "parallel_request_remaining_time": "1", "parallel_request_delay": "0"}
    assert "ParallelDownloading" not in json.dumps(upstream)   # not driven by any upstream study


def test_narrowed_study_drops_search_prefetch(upstream, mod):
    pack = mod.build(upstream)
    assert pack["HttpCacheNoVarySearch"][0]["experiments"][0]["enable_features"] == ["HttpCacheNoVarySearch"]


def test_upstream_drift_fails(upstream, mod):
    changed = copy.deepcopy(upstream)
    cfg = [c for c in changed["AsyncDnsQuicJob"] if "android" in c["platforms"]][0]
    cfg["experiments"][0]["enable_features"].append("SomethingNew")
    with pytest.raises(SystemExit):
        mod.build(changed)
    missing = copy.deepcopy(upstream)
    del missing["V8SparkplugPlus"]
    with pytest.raises(SystemExit):
        mod.build(missing)


def test_transform_writes_file(tmp_path, upstream, mod, capsys):
    d = tmp_path / "testing" / "variations"
    d.mkdir(parents=True)
    (d / "fieldtrial_testing_config.json").write_text(json.dumps(upstream))
    mod.main(str(tmp_path))
    assert "TOUCHED testing/variations/fieldtrial_testing_config.json" in capsys.readouterr().out
    out = json.loads((d / "fieldtrial_testing_config.json").read_text())
    assert out == mod.build(upstream)


def test_upstream_study_list_matches_snapshot(upstream):
    names = {s for s, c in upstream.items() if any("android" in x.get("platforms", []) for x in c)}
    assert names == speedpack_check.upstream_studies()


def test_args_gn_enables_testing_config():
    args = open(os.path.join(ROOT, "patches", "args.gn"), encoding="utf-8").read()
    assert "disable_fieldtrial_testing_config = false" in args
    assert "disable_fieldtrial_testing_config = true" not in args
    series = open(os.path.join(ROOT, "patches", "series"), encoding="utf-8").read().splitlines()
    assert "0016-swiftra-speedpack.py" in series


def test_parse_and_verdict():
    cmd = '--force-fieldtrials="*AsyncDnsQuicJob/Enabled/SwiftraParallelDownloading/Swiftra/ClientOnlyTrial/On/"'
    t = speedpack_check.parse_force_fieldtrials(cmd)
    assert t == {"AsyncDnsQuicJob": "Enabled", "SwiftraParallelDownloading": "Swiftra", "ClientOnlyTrial": "On"}
    v = speedpack_check.verdict("Field trial testing config (field-trial-config)", cmd)
    assert v["verdict"] == "speedpack_only" and v["client_side_trials"] == ["ClientOnlyTrial"]
    assert v["swiftra_parallel_download"] == "Swiftra"
    bad = cmd.replace("ClientOnlyTrial/On", "MaliciousApkDownloadCheck/Enabled")
    assert speedpack_check.verdict("field-trial-config", bad)["verdict"] == "unexpected_studies"
    assert speedpack_check.verdict("", "")["verdict"] == "no_testing_config"
    assert speedpack_check.verdict("field-trial-config", "--force-fieldtrials=X/Y/")["verdict"] == "pack_not_seen"


def test_speed_e2e_helpers():
    import speed_e2e as s
    recs = [{"range_start": 0, "bytes": 600}, {"range_start": 500, "bytes": 300}, {"range_start": 900, "bytes": 100}]
    assert s.coverage(recs, 1000) == 900
    assert s.coverage(recs + [{"range_start": 800, "bytes": 100}], 1000) == 1000
    assert s.max_concurrent([{"t0": 0, "t1": 5}, {"t0": 1, "t1": 2}, {"t0": 3, "t1": 4}]) == 2
    html = s.news_html("abc")
    assert html.count("?r=abc") >= 30 and "SPEED:done" in html
    assert set(s.MODES) == {"chromium_defaults", "swiftra"}
    assert "--disable-field-trial-config" in s.MODES["chromium_defaults"]
    assert "SwiftraAdBlock" in s.MODES["chromium_defaults"]
    for h in s.HOSTS:
        assert h.endswith((".example.com", ".example.net")) or h in s.ADS
