"""Host functional/unit checks; these are not native Android performance acceptance."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/ci"))
import startup_ablation as a


def valid_sample(ms=100):
    return {"total_ms": ms, "wait_ms": ms + 1, "launch_state": "COLD", "status_ok": True,
            "old_pid": None, "pid": "42", "pid_gone_before": True, "flags_file_matches": True,
            "cache_before_ok": True, "cache_after_ok": True}


@pytest.mark.parametrize("mode", list(a.MODES))
def test_only_one_allowlisted_performance_flag_and_no_security_switch(mode):
    raw = a.mode_flags(mode, "receipt1")
    assert a.flags_ok(raw.decode(), mode, "receipt1")
    for banned in ["SwiftraAdBlock", "SafeBrowsing", "KeyStore", "ignore-certificate", "no-sandbox",
                   "disable-field-trial-config", "disable-background-networking"]:
        assert banned not in raw.decode()
    assert raw.decode().count("--disable-features=") == (mode != "shipped")


@pytest.mark.parametrize("suffix", [" --disable-features=SafeBrowsing", " --enable-features=SomeFeature",
                                      " --ignore-certificate-errors", " --no-sandbox",
                                      " --disable-field-trial-config", " --disable-background-networking"])
def test_flag_receipt_rejects_security_or_nonidentical_overrides(suffix):
    assert not a.flags_ok(a.mode_flags("shipped", "n").decode().strip() + suffix, "shipped", "n")


def test_modes_receipt_and_order_are_explicit_and_counterbalanced():
    with pytest.raises(ValueError):
        a.mode_flags("disable_keystore", "n")
    with pytest.raises(ValueError):
        a.mode_flags("shipped", "x;bad")
    assert not a.flags_ok(a.mode_flags("shipped", "a").decode(), "shipped", "b")
    orders = [a.block_order(i) for i in range(4)]
    assert orders[1] == list(reversed(orders[0]))
    assert orders[3] == list(reversed(orders[2]))
    for mode in a.MODES:
        assert all(row.count(mode) == 1 for row in orders)
        assert sum(row.index(mode) for row in orders) == 12


def cache_xml(mode, crash=0, safe=0):
    return ('<map><string name="unrelated">never-export-this-fixture</string>' + ''.join(
        '<boolean name="%s%s" value="%s" />' % (a.CACHE_PREFIX, f, str(a.MODES[mode] != f).lower())
        for f in a.CACHED) + '<int name="%s" value="%d"/><int name="%s" value="%d"/></map>' %
        (a.CRASH, crash, a.SAFE, safe)).encode()


@pytest.mark.parametrize("mode", list(a.MODES))
def test_java_cache_receipt_is_next_run_and_selected_values_only(mode):
    receipt = a.cache_receipt(cache_xml(mode))
    assert set(receipt) == set(a.CACHED) | {"crash_streak", "safe_runs_left"}
    assert "never-export" not in json.dumps(receipt)
    assert a.cache_ok(receipt, mode)
    assert not a.cache_ok(a.cache_receipt(cache_xml(mode, crash=1)), mode)
    assert not a.cache_ok(a.cache_receipt(cache_xml(mode, safe=1)), mode)
    assert not a.cache_ok(a.cache_receipt(b'<map />'), mode)


def test_native_cli_is_not_enough_for_java_cached_flags():
    mode = "without_AndroidStartupImprovements"
    assert a.flags_ok(a.mode_flags(mode, "x").decode(), mode, "x")
    assert not a.cache_ok(a.cache_receipt(cache_xml("shipped")), mode)


def test_activate_rewarms_until_the_next_run_java_cache_matches(monkeypatch):
    mode='without_AndroidStartupImprovements';writes=[]
    monkeypatch.setattr(a,'stop_browser',lambda *x:None)
    monkeypatch.setattr(a,'write_flags',lambda b:writes.append(b))
    monkeypatch.setattr(a,'launch',lambda *x:'')
    monkeypatch.setattr(a,'pid_of',lambda *x:'17')
    monkeypatch.setattr(a,'socket_up',lambda *x:True)
    monkeypatch.setattr(a,'checked_adb',lambda *x,**kw:b'')
    monkeypatch.setattr(a,'targets',lambda *x:[{'id':'1'}])
    monkeypatch.setattr(a,'open_internal',lambda *x:True)
    monkeypatch.setattr(a,'page_text',lambda *x:writes[-1].decode())
    monkeypatch.setattr(a,'close_all_tabs',lambda *x:{'closed':1,'pages':1})
    receipts=iter([a.cache_receipt(cache_xml('shipped')),a.cache_receipt(cache_xml(mode))])
    monkeypatch.setattr(a,'receipt',lambda *x:next(receipts))
    monkeypatch.setattr(a.time,'sleep',lambda *x:None)
    got=a.activate('com.swiftra.app','com.swiftra.app/Main',mode,'n','socket',6)
    assert got['receipt_verified'] and len(got['attempts'])==2
    assert len(writes)==2 and all(x==a.mode_flags(mode,'n') for x in writes)


def test_cold_result_must_not_be_warm_pid_stale_or_zero():
    text = 'Status: ok\nLaunchState: COLD\nTotalTime: 750\nWaitTime: 751\nComplete\n'
    assert a.parse_launch(text)["total_ms"] == 750
    assert a.sample_ok(valid_sample())
    for key, value in [("launch_state", "HOT"), ("total_ms", 0), ("total_ms", None),
                       ("pid_gone_before", False), ("flags_file_matches", False),
                       ("cache_before_ok", False), ("cache_after_ok", False), ("pid", None),
                       ("old_pid", "42")]:
        s = valid_sample();s[key] = value
        assert not a.sample_ok(s)


def full_result():
    rows = []
    for b in range(4):
        for mode in a.block_order(b):
            rows.append({"block": b, "mode": mode, "warmup": {"receipt_verified": True},
                         "samples": [valid_sample(100 if mode == "shipped" else 90) for _ in range(3)]})
    return {"blocks": 4, "runs": 3, "rows": rows, "flags_restored": True,
            "shipped_cache_reprimed": True, "compile_reset": True, "same_apk": True, "compile_ok": True,
            "compilation": "speed", "dexopt_before": ["speed"], "dexopt_after": ["speed"], "apk_sha256": "a" * 64,
            "installed_sha_before": "a" * 64, "installed_sha_after": "a" * 64}


def test_statistics_keep_raw_counts_block_effect_and_do_not_promote():
    r = full_result();s = a.summarize(r['rows'], 4, 3)
    assert s['shipped']['valid_n'] == 12
    for mode in list(a.MODES)[1:]:
        assert s[mode]['median_ms'] == 90
        assert s[mode]['block_delta_pct'] == [-10.0] * 4
        assert s[mode]['block_bootstrap_95_pct'] == [-10.0, -10.0]
    assert a.complete(r)
    for key in ['flags_restored', 'compile_reset', 'same_apk', 'shipped_cache_reprimed']:
        x = copy.deepcopy(r);x[key] = False
        assert not a.complete(x)
    x = copy.deepcopy(r);x['rows'].pop();assert not a.complete(x)
    x = copy.deepcopy(r);x['rows'][0]['samples'][0]['cache_after_ok'] = False;assert not a.complete(x)
    x = copy.deepcopy(r);x['installed_sha_after'] = 'b' * 64;assert not a.complete(x)
    x = copy.deepcopy(r);x['dexopt_after'] = ['verify'];assert not a.complete(x)
    x = copy.deepcopy(r);x['rows'][0] = copy.deepcopy(x['rows'][1]);assert not a.complete(x)
    x = copy.deepcopy(r);x.update(compilation='verify',dexopt_before=['verify'],dexopt_after=['verify']);assert a.complete(x)
    x['dexopt_after']=['speed-profile'];assert not a.complete(x)
    x = copy.deepcopy(r);x['compilation']='unknown';assert not a.complete(x)


def host_transport(monkeypatch, drop=False):
    calls = []
    def fake(*args, raw_input=None, timeout=45):
        calls.append(args)
        assert 'fixture-original-private' not in ' '.join(args)
        if args[:2] == ('exec-out', 'cat'):
            return Path(args[2]).read_bytes()
        if args[:2] == ('shell', '-T'):
            p = subprocess.run(['bash', '-c', args[2]], input=b'' if drop else raw_input,
                               capture_output=True, timeout=timeout)
        elif args[:3] == ('shell', 'ls', '-Zd'):
            return b'? file\n'
        elif args[0] == 'shell' and args[1] in ('stat', 'mv', 'rm'):
            p = subprocess.run(args[1:], capture_output=True, timeout=timeout)
        else:
            raise AssertionError('unexpected transport')
        if p.returncode:
            raise RuntimeError('host fixture command failed')
        return p.stdout
    monkeypatch.setattr(a, 'checked_adb', fake)
    monkeypatch.setattr(a, 'file_exists', lambda p: Path(p).is_file())
    return calls


def test_flags_restore_exact_original_bytes_mode_and_no_argv_private_data(tmp_path, monkeypatch):
    f = tmp_path/'flags';f.write_bytes(b'_ fixture-original-private\n');f.chmod(0o600)
    monkeypatch.setattr(a, 'CMDLINE_FILE', str(f));calls = host_transport(monkeypatch)
    snapshot = a.snapshot_flags()
    a.write_flags(a.mode_flags('shipped', 'n'))
    assert f.stat().st_mode & 0o777 == 0o644
    assert a.restore_flags(snapshot)
    assert f.read_bytes() == b'_ fixture-original-private\n'
    assert f.stat().st_mode & 0o777 == 0o600
    assert not any(c[0]=='exec-in' for c in calls)
    assert not Path(str(f)+'.startup-ablation.tmp').exists()


def test_dropped_stdin_cannot_truncate_original_flags(tmp_path, monkeypatch):
    f=tmp_path/'flags';f.write_bytes(b'_ fixture-original-private\n')
    monkeypatch.setattr(a,'CMDLINE_FILE',str(f));host_transport(monkeypatch, drop=True)
    with pytest.raises(RuntimeError, match='round-trip'):
        a.write_flags(a.mode_flags('shipped','n'))
    assert f.read_bytes()==b'_ fixture-original-private\n'
    assert not Path(str(f)+'.startup-ablation.tmp').exists()


def test_original_absence_is_restored(tmp_path, monkeypatch):
    f=tmp_path/'flags';monkeypatch.setattr(a,'CMDLINE_FILE',str(f));host_transport(monkeypatch)
    snapshot=a.snapshot_flags();assert snapshot is None
    a.write_flags(a.mode_flags('shipped','n'));assert f.exists()
    assert a.restore_flags(snapshot) and not f.exists()


def test_physical_refusal_never_installs_compiles_or_cleans_flags(tmp_path, monkeypatch):
    apk=tmp_path/'a.apk';apk.write_bytes(b'fixture')
    info=tmp_path/'BUILD_INFO.txt';info.write_text('0016-swiftra-speedpack.py\n0021-swiftra-keystore-oscrypt.patch\n--- sha256\n'+hashlib.sha256(apk.read_bytes()).hexdigest()+'\n')
    monkeypatch.setattr(sys,'argv',['ablation','--package','com.swiftra.app','--apk',str(apk),
                                  '--build-info',str(info),'--out',str(tmp_path/'out')])
    def refuse():raise RuntimeError('physical refused')
    monkeypatch.setattr(a,'root_device',refuse)
    monkeypatch.setattr(a,'checked_adb',lambda *x,**kw:pytest.fail('must not mutate refused device'))
    monkeypatch.setattr(a,'prepare_browser',lambda *x:pytest.fail('must not install'))
    assert a.main()==2
    result=json.loads((tmp_path/'out/startup_ablation.json').read_text())
    assert result['verdict']=='not_run' and result['rows']==[] and 'physical refused' in result['error']


def test_focused_workflows_are_full_only_for_publish_foreign_apk_and_baseline():
    root=Path(__file__).resolve().parents[1]
    import yaml
    for name in ['ui-capture.yml','arm64-device-e2e.yml']:
        wf=yaml.safe_load((root/'.github/workflows'/name).read_text())
        assert wf['jobs']['publish']['if']=="always() && (inputs.checks == 'full' || inputs.checks == '')"
        text=(root/'.github/workflows'/name).read_text()
        assert 'startup_ablation, update_download]' in text
        assert "inputs.checks != 'safety_update'" not in text
    wrapper=(root/'scripts/ci/run_capture.sh').read_text()
    section=wrapper.split('if [ "$MODE" = startup_ablation ]; then',1)[1].split('if [ "$MODE" = safety_update ]; then',1)[0]
    assert 'startup_ablation.py' in section and 'keystore_probe_passed "$kr"' in section
    assert 'exit "$rc"' in section


def test_unknown_check_mode_cannot_touch_adb(tmp_path):
    root=Path(__file__).resolve().parents[1]
    bindir=tmp_path/'bin';bindir.mkdir();marker=tmp_path/'touched'
    f=bindir/'adb';f.write_text('#!/bin/sh\ntouch "'+str(marker)+'"\n');f.chmod(0o700)
    r=subprocess.run(['bash',str(root/'scripts/ci/run_capture.sh'),'chromium_source_x64','unknown'],
                     cwd=tmp_path,env=dict(os.environ,PATH=str(bindir)+':'+os.environ['PATH']),capture_output=True)
    assert r.returncode==2 and not marker.exists()
