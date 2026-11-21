"""Personal input lane tests use real shell/preparer, no remote/native build/device."""
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TAG = "158.0.8127.42"
PACKAGE = "org.example.containmentdev"
HELPER = ROOT / "scripts/ci/personal_bundle.sh"


def configure(tmp_path, *, package=PACKAGE, tag=TAG, cpu="x64", variant="personal-test", state=None):
    pk, outputs = tmp_path / "pk", tmp_path / "outputs"
    pk.mkdir(exist_ok=True)
    outputs.mkdir(exist_ok=True)
    state = state or f"crstate-{tag}-{cpu}-{variant}"
    script = '''set -euo pipefail
source "$1"
configure_personal_bundle "$2" "$3" "$4" "$5" "$6" "$7"
printf '\\nPERSONAL_MARKER=%s\\nSELECTED_PATCHES=%s\\n' "$PERSONAL_SOURCE_ONLY" "$PDIR"
'''
    return subprocess.run(
        ["bash", "-c", script, "personal-test", str(HELPER), str(ROOT), str(pk), str(outputs), tag, cpu, state],
        env=dict(os.environ, PERSONAL_PACKAGE=package, PERSONAL_SOURCE_ONLY="untrusted-inherited-value"),
        text=True, capture_output=True, timeout=30)


@pytest.mark.parametrize("variant", ["a1", "b1"])
def test_default_lane_remains_ordinary_without_a_personal_package(tmp_path, variant):
    run = configure(tmp_path, package="", variant=variant)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "PERSONAL_MARKER=0" in run.stdout
    assert "SELECTED_PATCHES=" + str(ROOT / "patches") in run.stdout
    assert list((tmp_path / "pk").iterdir()) == []
    assert not (tmp_path / "outputs/PERSONAL_SOURCE_ONLY.json").exists()


@pytest.mark.parametrize("cpu", ["x64", "arm64"])
def test_personal_lane_selects_real_separate_bundle_without_building(tmp_path, cpu):
    before = {p: (ROOT / "patches" / p).read_bytes() for p in ("args.gn", "series", "signing_cert_sha256.txt")}
    run = configure(tmp_path, cpu=cpu)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "PERSONAL_MARKER=1" in run.stdout
    selected = next(line.split("=", 1)[1] for line in run.stdout.splitlines() if line.startswith("SELECTED_PATCHES="))
    folder = Path(selected)
    assert folder.is_relative_to(tmp_path / "pk")
    receipt = json.loads((tmp_path / "outputs/PERSONAL_SOURCE_ONLY.json").read_text())
    assert receipt["package"] == PACKAGE and receipt["variant"] == "personal-test"
    assert not receipt["release_ready"] and not receipt["apk_built"]
    assert receipt["product_containment"] == "NOT RUN / NOT CERTIFIED"
    assert "0103-personal-egress-and-storage.patch" in (folder / "series").read_text()
    assert PACKAGE in (folder / "args.gn").read_text()
    assert {p: (ROOT / "patches" / p).read_bytes() for p in before} == before


@pytest.mark.parametrize("arguments", [
    {"variant": "a1"}, {"variant": "b1"}, {"variant": "personal-"},
    {"package": "", "variant": "personal-test"}, {"package": "com.swiftra.app"},
    {"package": "com.android.chrome"}, {"tag": "other-tag"}, {"cpu": "unsupported"},
    {"state": "crstate-other-x64-personal-test"},
])
def test_invalid_personal_inputs_refuse_before_any_remote_or_runner_work(tmp_path, arguments):
    run = configure(tmp_path, **arguments)
    assert run.returncode != 0
    assert "REFUSED" in run.stdout + run.stderr
    assert not (tmp_path / "outputs/PERSONAL_SOURCE_ONLY.json").exists()
    assert not list(tmp_path.rglob("*.apk"))


def test_manual_workflow_is_distinct_opt_in_free_and_not_an_autopublish_trigger():
    workflow = yaml.load((ROOT / ".github/workflows/personal-source-build.yml").read_text(), Loader=yaml.BaseLoader)
    after = yaml.load((ROOT / ".github/workflows/after-build.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["name"] not in after["on"]["workflow_run"]["workflows"]
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert inputs["package"]["required"] == "true" and "default" not in inputs["package"]
    assert inputs["confirm_development_only"]["type"] == "boolean"
    assert inputs["confirm_development_only"]["default"] == "false"
    assert workflow["jobs"]["validate"]["runs-on"] == "ubuntu-24.04"
    assert workflow["jobs"]["validate"]["permissions"]["contents"] == "read"
    assert "publish" not in workflow["jobs"]
    assert set(workflow["jobs"]) == {"validate", *(f"s{i}" for i in range(8))}
    for i in range(8):
        job = workflow["jobs"][f"s{i}"]
        assert job["uses"] == "./.github/workflows/chromium-stage.yml"
        assert job["with"]["personal_package"] == "${{ inputs.package }}"
        assert job["with"]["variant"] == "${{ inputs.variant }}"
        assert job["with"]["tag"] == TAG and job["with"]["stage"] == str(i)
        assert job["needs"] == ("validate" if i == 0 else f"s{i-1}")
    reusable = yaml.load((ROOT / ".github/workflows/chromium-stage.yml").read_text(), Loader=yaml.BaseLoader)
    assert reusable["on"]["workflow_call"]["inputs"]["personal_package"]["default"] == ""
    assert reusable["jobs"]["stage"]["runs-on"] == "ubuntu-24.04"
    steps = reusable["jobs"]["stage"]["steps"]
    build = next(step for step in steps if step.get("id") == "s")
    assert build["env"]["PERSONAL_PACKAGE"] == "${{ inputs.personal_package }}"
    assert not any("SIGNING" in key for key in build["env"])


def test_input_selection_precedes_runner_cleanup_and_metadata_preserves_marker():
    stage = (ROOT / "scripts/ci/chromium_stage.sh").read_text()
    assert stage.index("configure_personal_bundle ") < stage.index("sudo rm -rf")
    assert "EXP_NONDEBUG PERSONAL_SOURCE_ONLY >" in stage
    finalize = (ROOT / "scripts/ci/finalize_apk.sh").read_text()
    assert 'echo "personal_source_only=${PERSONAL_SOURCE_ONLY:-0}"' in finalize
    assert 'echo "product_containment=NOT RUN / NOT CERTIFIED"' in finalize
    assert "DEVELOPMENT ONLY" in finalize
    # No production patch series or GN package changes are used to switch this lane on.
    assert "0101-persistent-account-boundary.patch" not in (ROOT / "patches/series").read_text()
    assert 'chrome_public_manifest_package = "com.swiftra.app"' in (ROOT / "patches/args.gn").read_text()
