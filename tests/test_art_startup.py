import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "ci"))
import art_startup as a  # noqa: E402


def test_parse_total():
    out = "Starting: Intent { cmp=com.swiftra.app/.Main }\nStatus: ok\nLaunchState: COLD\nTotalTime: 728\nWaitTime: 733\n"
    assert a.parse_total(out) == 728
    assert a.parse_total("Error: Activity not started") is None
    assert a.parse_total(None) is None


def test_parse_status_old_and_art_service():
    old = "Dexopt state:\n  [com.swiftra.app]\n    path: /data/app/x/base.apk\n      arm64: [status=verify] [reason=install]\n"
    new = ("Dexopt state:\n  [com.swiftra.app]\n    path: /data/app/x/base.apk\n"
           "      x86_64: [status=speed-profile] [reason=cmdline] [primary-abi]\n")
    assert a.parse_status(old) == ["verify"]
    assert a.parse_status(new) == ["speed-profile"]
    assert a.parse_status("") == []


def test_median_ignores_failed_launches():
    assert a.median([700, None, 710, 690]) == 700
    assert a.median([None]) is None


def test_states_order_and_reset():
    names = [n for n, _ in a.STATES]
    assert names == ["install", "profile", "speed"]
    assert a.STATES[0][1] == ["--reset"]
    assert "speed-profile" in a.STATES[1][1] and "speed" in a.STATES[2][1]


def test_wired_after_startup_trace():
    sh = open(os.path.join(os.path.dirname(__file__), "..", "scripts", "ci", "run_capture.sh")).read()
    assert sh.index("startup_trace.py") < sh.index("art_startup.py") < sh.index("logcat -d")
