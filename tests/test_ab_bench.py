import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
import ab_bench as ab  # noqa: E402


def test_order_alternates_and_balanced():
    assert ab.ORDER == ("new", "base", "new", "base")
    assert all(ab.ORDER[i] != ab.ORDER[i + 1] for i in range(len(ab.ORDER) - 1))


def test_identical_apks_not_run(tmp_path, monkeypatch, capsys):
    f = tmp_path / "a.apk"
    f.write_bytes(b"same")
    monkeypatch.setattr(sys, "argv", ["ab", "--package", "p", "--new", str(f), "--base", str(f), "--out", str(tmp_path)])
    assert ab.main() == 0
    assert "AB_BENCH NOT_RUN" in capsys.readouterr().out
    assert json.load(open(tmp_path / "ab_bench.json"))["rounds"] == []


def test_device_sha_parses_base_apk(monkeypatch):
    h = "a" * 64

    def fake(*args, timeout=30):
        if args[:3] == ("shell", "pm", "path"):
            return "package:/data/app/~~x/com.swiftra.app-y/split_a.apk\npackage:/data/app/~~x/com.swiftra.app-y/base.apk\n"
        if args[:2] == ("shell", "sha256sum"):
            assert args[2].endswith("/base.apk")
            return f"{h}  {args[2]}\n"
        return ""
    monkeypatch.setattr(ab, "adb", fake)
    assert ab.device_sha("com.swiftra.app") == h


def test_ratio():
    assert ab.ratio(110, 100) == 1.1
    assert ab.ratio(None, 100) is None


def test_workflow_step_is_optional_and_before_device_checks():
    wf = open(os.path.join(ROOT, ".github", "workflows", "arm64-device-e2e.yml")).read()
    assert "ab_baseline_release:" in wf
    assert "if: ${{ inputs.ab_baseline_release != '' && inputs.checks != 'safety_update' }}" in wf
    assert wf.index("scripts/ci/ab_bench.py") < wf.index("bash scripts/ci/device_checks.sh")
