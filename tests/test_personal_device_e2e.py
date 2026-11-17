"""Host tests for the PURE helpers of scripts/ci/personal_e2e.py and the safety of its workflow.
Host results here are NOT Android PASS; the device run is the acceptance evidence."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import personal_e2e as P  # noqa: E402


def test_retention_requires_all_three_stores():
    tok = "abc"
    hits = [{"path": "/echo", "cookie": "x=1; pe_cookie=abc"}]
    assert all(P.retention_ok({"ls": "abc", "idb": "abc"}, hits, tok).values())
    assert not P.retention_ok({"ls": "", "idb": "abc"}, hits, tok)["localStorage"]
    assert not P.retention_ok({"ls": "abc", "idb": "ERR:x"}, hits, tok)["indexedDB"]
    assert not P.retention_ok({"ls": "abc", "idb": "abc"}, [{"path": "/echo", "cookie": ""}], tok)["cookie"]
    assert not any(P.retention_ok(None, [], tok).values())


DUMP = """  Window #3 Window{1a2b u0 com.swiftra.personaldev/org.chromium.chrome.browser.ChromeTabbedActivity}:
    mAttrs={(0,0)(fillxfill) sim={adjust=resize} ty=BASE_APPLICATION fl=ALLOW_LOCK_WHILE_SCREEN_ON SECURE HARDWARE_ACCELERATED}
  Window #4 Window{3c4d u0 other.app/other.Main}:
    mAttrs={ fl=ALLOW_LOCK_WHILE_SCREEN_ON }"""


def test_secure_flag_parser_is_per_package():
    assert P.secure_flag_in_window_dump(DUMP, "com.swiftra.personaldev")
    assert not P.secure_flag_in_window_dump(DUMP, "other.app")
    assert not P.secure_flag_in_window_dump(DUMP.replace(" SECURE", ""), "com.swiftra.personaldev")
    assert not P.secure_flag_in_window_dump("", "com.swiftra.personaldev")


def test_top_package_parser():
    d = "  topResumedActivity=ActivityRecord{12 u0 com.android.dialer/.DialtactsActivity t5}"
    assert P.top_package(d) == "com.android.dialer"
    assert P.top_package("  mResumedActivity: ActivityRecord{9 u0 com.swiftra.personaldev/org.x.Main t3}") == "com.swiftra.personaldev"
    assert P.top_package("nothing") == ""


def test_not_run_is_never_counted_as_pass():
    c = P.summarize([{"status": "PASS"}, {"status": "NOT_RUN"}, {"status": "FAIL"}])
    assert c == {"PASS": 1, "FAIL": 1, "NOT_RUN": 1}


def test_workflow_never_publishes_and_refuses_ordinary_packages():
    wf = (ROOT / ".github/workflows/personal-device-e2e.yml").read_text()
    for banned in ("publish-latest", "gh release upload", "gh release create", "gh workflow run", "swiftra-update"):
        assert banned not in wf, banned
    assert re.search(r"on:\s+workflow_dispatch:", wf)
    run = (ROOT / "scripts/ci/personal_e2e_run.sh").read_text()
    assert "com.swiftra.app" in run and "REFUSED" in run


def test_external_measurement_control_labels():
    pkg = "com.swiftra.personaldev"
    assert P.control_label("com.android.dialer", pkg) == "OBSERVED(com.android.dialer)"
    assert P.control_label(pkg, pkg).startswith("UNAVAILABLE")
    assert P.control_label("", pkg).startswith("UNAVAILABLE")
    # a control that only observed the browser itself must never read as an observed hand-off
    assert not P.control_label(pkg, pkg).startswith("OBSERVED")


def test_device_loss_is_a_harness_error_not_a_quiet_not_run(monkeypatch):
    monkeypatch.setattr(P, "adb", lambda *a, **k: "adb: device 'emulator-5554' not found")
    assert P.device_up() is False
    try:
        P.require_device("unit")
    except RuntimeError as e:
        assert "device lost unit" in str(e)
    else:
        raise AssertionError("device loss was swallowed")
    monkeypatch.setattr(P, "adb", lambda *a, **k: "device\n")
    assert P.device_up() is True


def test_launcher_on_top_is_not_an_observed_hand_off():
    pkg = "com.swiftra.personaldev"
    out = "priority=0 ... \ncom.android.launcher3/.uioverrides.QuickstepLauncher\n"
    ign = P.home_packages(out) | {"com.android.systemui"}
    assert "com.android.launcher3" in ign
    assert P.control_label("com.android.launcher3", pkg, ign).startswith("UNAVAILABLE")
    assert P.control_label("com.android.systemui", pkg, ign).startswith("UNAVAILABLE")
    assert P.control_label("com.google.android.dialer", pkg, ign) == "OBSERVED(com.google.android.dialer)"
    # without the ignore set a launcher would wrongly read as an observed hand-off (the ARM64 Redroid case)
    assert P.control_label("com.android.launcher3", pkg).startswith("OBSERVED")
