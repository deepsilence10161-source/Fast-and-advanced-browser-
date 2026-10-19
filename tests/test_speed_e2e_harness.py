"""speed_e2e.py control flow with adb/device stubbed: mode order, per-mode budget, PARTIAL marking, diag files."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))

import speed_e2e as se  # noqa: E402


def _stub(monkeypatch, budget, calls):
    monkeypatch.setattr(se, "adb", lambda *a, timeout=30: (calls.append(a) or ""))
    monkeypatch.setattr(se, "resolve_launcher", lambda p: "p/.A")
    monkeypatch.setattr(se, "start_server", lambda d: None)
    monkeypatch.setattr(se, "restart", lambda pkg, comp, mode, sock, attempts=3: (
        calls.append(("restart", mode)) or {"flags_applied": True, "cmdline": "", "pid": "1", "tries": []}))
    page = {"open": "ok", "page": {"load": 1, "lcp": 1, "fcp": 1, "dcl": 1},
            "server": {"requests": 1, "bytes": 1024, "ad_requests": 0}}
    monkeypatch.setattr(se, "load_page", lambda rid, shot=None: page)
    monkeypatch.setattr(se, "run_download", lambda r: {"server": {"complete": True, "seconds": 2, "requests": 5}})
    monkeypatch.setattr(se, "run_download_h2", lambda r: {"server": {"complete": True, "seconds": 3, "connections": 5,
                                                                     "requests": 5, "alpn": ["h2"]}})
    monkeypatch.setattr(se, "run_bench", lambda r: {"result": {"total": 10, "ms": {"a": 10}}})
    monkeypatch.setattr(se, "screenshot", lambda p: None)
    monkeypatch.setattr(se, "MODE_BUDGET_S", budget)
    monkeypatch.setattr(se, "RECOVERY", [])


def test_full_run_alternates_order_and_is_measured(monkeypatch, tmp_path, capsys):
    calls = []
    _stub(monkeypatch, 1000, calls)
    monkeypatch.setattr(sys, "argv", ["x", "--package", "p", "--out", str(tmp_path)])
    assert se.main() == 0
    assert [c[1] for c in calls if c[0] == "restart"] == ["swiftra", "chromium_defaults", "chromium_defaults",
                                                          "swiftra"]
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last.startswith("SPEED_E2E MEASURED") and "skipped none" in last


def test_mode_budget_skips_and_marks_partial(monkeypatch, tmp_path, capsys):
    calls = []
    _stub(monkeypatch, -1, calls)
    monkeypatch.setattr(sys, "argv", ["x", "--package", "p", "--out", str(tmp_path)])
    se.main()
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last.startswith("SPEED_E2E NOT_RUN") or last.startswith("SPEED_E2E PARTIAL")


def test_devtools_diag_writes_stacks_and_logcat(monkeypatch, tmp_path):
    def fake_adb(*a, timeout=30):
        if a[:2] == ("shell", "pidof"):
            return "4242\n"
        if a[:2] == ("shell", "debuggerd"):
            return f"----- pid 4242 ({a[2]}) -----\n\"main\" tid=1 Native\n"
        if a[0] == "get-state":
            return "device\n"
        if a[0] == "logcat":
            return "10-19 02:03:50.000 E chromium: something\n"
        return ""
    monkeypatch.setattr(se, "adb", fake_adb)
    monkeypatch.setattr(se, "OUT", str(tmp_path))
    monkeypatch.setattr(se, "PKG", "com.swiftra.app")
    monkeypatch.setattr(se, "RECOVERY", [])
    d = se.devtools_diag("c0s0")
    assert d["pid"] == "4242" and d["stacks"] and d["adb"] == "device"
    st = (tmp_path / "stacks_c0s0.txt").read_text()
    assert "debuggerd -j" in st and "-b" in st and '"main" tid=1' in st
    assert (tmp_path / "logcat_c0s0.txt").exists() and (tmp_path / "diag_c0s0.txt").exists()
