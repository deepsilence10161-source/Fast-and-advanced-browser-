import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "release"))
import e2e_gate as g

SHA = "a" * 64

def _mk(tmp_path, lines, sha=SHA, dev="DEVICE_CHECKS: 9 pass, 0 fail"):
    d = tmp_path / "t"; d.mkdir()
    (d / "BUILD_INFO.txt").write_text(f"x\n--- sha256\n{sha}\n")
    (d / "shield_e2e.txt").write_text("\n".join(lines) + "\n")
    (d / "device_checks.txt").write_text(dev + "\n")
    return str(d)

ALL = [k + " PASS" for k in g.REQUIRED] + ["SPEED_E2E PARTIAL"]

def test_pass(tmp_path):
    assert g.gate(_mk(tmp_path, ALL), SHA) == []

def test_other_apk_blocked(tmp_path):
    assert g.gate(_mk(tmp_path, ALL, sha="b" * 64), SHA)

def test_fail_marker_blocked(tmp_path):
    assert g.gate(_mk(tmp_path, ALL + ["ADBLOCK_E2E FAIL"]), SHA)

def test_not_run_blocked(tmp_path):
    assert g.gate(_mk(tmp_path, [l for l in ALL if not l.startswith("CREDITS")] + ["CREDITS_E2E NOT_RUN"]), SHA)

def test_device_check_failure_blocked(tmp_path):
    assert g.gate(_mk(tmp_path, ALL, dev="DEVICE_CHECKS: 8 pass, 1 fail"), SHA)


def test_update_e2e_required_only_with_0020(tmp_path):
    d = tmp_path / "u"; d.mkdir()
    (d / "BUILD_INFO.txt").write_text(f"x\n--- patches\n0016-swiftra-speedpack.py\n0020-swiftra-update-channel.patch\n--- sha256\n{SHA}\n")
    (d / "e.txt").write_text("\n".join(ALL) + "\nDEVICE_CHECKS: 9 pass, 0 fail\n")
    assert any("UPDATE_E2E" in r for r in g.gate(str(d), SHA))
    (d / "e.txt").write_text("\n".join(ALL) + "\nUPDATE_E2E PASS\nDEVICE_CHECKS: 9 pass, 0 fail\n")
    assert g.gate(str(d), SHA) == []
