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


def test_arm64_pgo_and_orderfile_are_wired_and_guarded():
    """arm64 (not a1, not x64): Chrome's android-arm64 PGO profile + orderfile, and a hard stop if they are missing."""
    s = open(os.path.join(ROOT, "scripts", "ci", "chromium_stage.sh"), encoding="utf-8").read()
    assert 'if [ "$CPU" = arm64 ] && [[ "$STATE" != *-a1 ]]; then' in s
    assert "'chrome_pgo_phase = 2'" in s
    assert '\'chrome_orderfile_path = "//chrome/android/orderfiles/arm64/orderfile.arm64.out"\'' in s
    guard = s.index("PGO input missing")
    assert s.index("pgo_profile.arm64.profdata", s.index("2c0.")) < guard < s.index("# ---------- 2c. args.gn")
    # the base heredoc stays untouched (official build stays off; privacy relies on it)
    base = s.split("ARGS=$(cat <<EOF\n", 1)[1].split("\nEOF\n", 1)[0]
    assert "is_official_build = false" in base and "chrome_pgo_phase" not in base


def test_speed_e2e_bench_summary():
    sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
    import speed_e2e as se
    assert "swiftraBench(5)" in se.BENCH_HTML and "BENCH:done" in se.BENCH_HTML
    js = open(os.path.join(ROOT, "tools", "speedpack", "bench.js"), encoding="utf-8").read()
    for api in ("fetch(", "XMLHttpRequest", "import(", "WebSocket", "sendBeacon", ".src", "navigator."):
        assert api not in js, api   # no network, no device APIs: pure CPU work

    def mode(total, dl):
        page = {"load": 1000, "lcp": 500, "fcp": 300, "dcl": 200}
        srv = {"requests": 47, "bytes": 900 * 1024, "ad_requests": 15}
        return {"loads": [{"page": page, "server": srv}],
                "download": {"server": {"complete": True, "seconds": dl, "requests": 3}},
                "bench": {"result": {"total": total, "ms": {"json": total / 2, "dom": total / 2}}}}
    res = {"cycles": [{"chromium_defaults": mode(1000, 8.0), "swiftra": mode(800, 4.0)},
                      {"chromium_defaults": mode(1200, 8.2), "swiftra": mode(900, 4.2)}]}
    s = se.summarize(res)
    assert s["chromium_defaults"]["bench_ms"] == 1100 and s["swiftra"]["bench_ms"] == 850   # statistics.median
    assert s["swiftra"]["bench_runs"] == 2 and s["swiftra"]["bench_parts"]["json"] == 425
    assert s["speedup"]["bench"] == 1.29 and s["speedup"]["download"] == round(8.1 / 4.1, 2)
    # an older run without the bench still summarises
    for c in res["cycles"]:
        for m in c.values():
            m.pop("bench")
    assert se.summarize(res)["speedup"]["bench"] is None


def test_compare_runs_ratio_and_noise():
    sys.path.insert(0, os.path.join(ROOT, "tools", "speedpack"))
    import compare_runs as cr

    def run(totals):
        return {"cycles": [{"swiftra": {"bench": {"result": {"total": t, "ms": {"json": t / 2}}},
                                        "loads": [{"page": {"load": 1000, "lcp": 400}}],
                                        "download": {"server": {"complete": True, "seconds": 4.0}}}} for t in totals]}
    rows = {r["metric"]: r for r in cr.compare(cr.bench_values(run([1000, 1040]), "swiftra"),
                                               cr.bench_values(run([800, 820]), "swiftra"))}
    assert rows["total"]["ratio"] == round(1020 / 810, 3) and rows["total"]["note"] == "new faster"
    rows = {r["metric"]: r for r in cr.compare(cr.page_values(run([1]), "swiftra"), cr.page_values(run([1]), "swiftra"))}
    assert rows["load_ms"]["note"] == "within noise" and rows["download_s"]["ratio"] == 1.0
    assert cr.compare({"total": [1]}, {})[0]["note"] == "no data"


def test_speed_restart_verifies_new_process_and_exact_flags(monkeypatch):
    sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
    import speed_e2e as se
    base = f' _ --host-resolver-rules="{se.RULES}" --ignore-certificate-errors'
    cd = base + " " + se.MODES["chromium_defaults"]
    assert se.flags_ok(cd, "chromium_defaults") and not se.flags_ok(cd, "swiftra")   # the A/A bug: stale cmdline
    assert se.flags_ok(base, "swiftra") and not se.flags_ok(base, "chromium_defaults")
    assert not se.flags_ok("", "swiftra")

    state = {"pid": "100", "starts": 0, "cmd": ""}

    def fake_adb(*a, timeout=None):
        if a[:2] == ("shell", "pidof"):
            return state["pid"]
        if a[:2] == ("shell", "am") and a[2] == "force-stop":
            state["pid"] = ""
        if a[:2] == ("shell", "am") and a[2] == "start":
            state["starts"] += 1
            state["pid"] = str(200 + state["starts"])
        if len(a) == 2 and a[0] == "shell" and "chrome-command-line" in a[1]:
            state["cmd"] = a[1].split("'")[1]
        return ""
    ready = {"n": 0}

    def fake_targets(_):
        ready["n"] += 1
        return [] if state["starts"] == 1 else [{"url": state.get("url", ""), "type": "page"}]   # 1st start: no DevTools
    monkeypatch.setattr(se, "adb", fake_adb)
    monkeypatch.setattr(se, "targets", fake_targets)
    monkeypatch.setattr(se, "open_internal", lambda d, u: state.__setitem__("url", u))
    monkeypatch.setattr(se, "page_text", lambda d, u, e: " " + state["cmd"].replace('"', '"'))
    monkeypatch.setattr(se, "close_targets", lambda s: 0)
    clock = [0.0]
    monkeypatch.setattr(se, "time", type("T", (), {"time": staticmethod(lambda: clock[0]),
                                                  "sleep": staticmethod(lambda x: clock.__setitem__(0, clock[0] + x))}))
    r = se.restart("com.swiftra.app", "com.swiftra.app/.Main", "swiftra", "sock")
    assert r["flags_applied"] and r["pid"] == "202" and len(r["tries"]) == 2 and not r["tries"][0]["ready"]
    assert "--disable-field-trial-config" not in r["cmdline"]


def test_screenshot_never_raises(monkeypatch, tmp_path):
    sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
    import shield_e2e as sh
    import subprocess as sp

    def hang(*a, **k):
        raise sp.TimeoutExpired(a[0], 20)
    monkeypatch.setattr(sh.subprocess, "run", hang)
    assert sh.screenshot(str(tmp_path / "x.png")) is False
    for f in ("shield_e2e.py", "advanced_e2e.py", "speed_e2e.py"):
        body = open(os.path.join(ROOT, "scripts", "ci", f), encoding="utf-8").read()
        calls = body.count('"screencap", "-p"') + body.count("screencap -p")
        assert calls == (1 if f == "shield_e2e.py" else 0), f   # only the guarded helper runs screencap
