"""Source-level checks of 0110 guard + 0111 patch (no AI Mode eligibility fetch, no network-time query). Host only."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/personal_browser"))
import source_fixture as fixture_tools  # noqa: E402

PERSONAL = ROOT / "patches/personal"
AIM = "components/omnibox/browser/aim_eligibility_service_features.cc"
NT = "components/network_time/network_time_tracker.cc"


def guard():
    spec = importlib.util.spec_from_file_location("egress_guard", PERSONAL / "0110-personal-google-egress-source-guard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stage(tmp_path):
    srcs = fixture_tools.load_sources()
    for rel in (AIM, NT):
        t = tmp_path / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(srcs[rel])
    guard().check(tmp_path)
    subprocess.run(["patch", "-d", str(tmp_path), "-p1", "--forward", "--batch", "--no-backup-if-mismatch",
                    "-i", str(PERSONAL / "0111-personal-google-egress.patch")], check=True, capture_output=True)
    return srcs


def test_ai_mode_kill_switch_is_off(tmp_path):
    srcs = _stage(tmp_path)
    out = (tmp_path / AIM).read_text()
    assert "BASE_FEATURE(kAimEnabled, base::FEATURE_ENABLED_BY_DEFAULT);" in srcs[AIM]
    assert "BASE_FEATURE(kAimEnabled, base::FEATURE_DISABLED_BY_DEFAULT);" in out
    assert "BASE_FEATURE(kAimEnabled, base::FEATURE_ENABLED_BY_DEFAULT);" not in out
    # nothing else in the file flips
    assert out.count("FEATURE_ENABLED_BY_DEFAULT") == srcs[AIM].count("FEATURE_ENABLED_BY_DEFAULT") - 1


def test_network_time_query_is_off_on_every_platform(tmp_path):
    srcs = _stage(tmp_path)
    out = (tmp_path / NT).read_text()
    assert "BASE_FEATURE(kNetworkTimeServiceQuerying, base::FEATURE_ENABLED_BY_DEFAULT);" in srcs[NT]
    assert "BASE_FEATURE(kNetworkTimeServiceQuerying, base::FEATURE_ENABLED_BY_DEFAULT);" not in out
    assert out.count("BASE_FEATURE(kNetworkTimeServiceQuerying, base::FEATURE_DISABLED_BY_DEFAULT);") == 1


def test_guard_refuses_drifted_source(tmp_path):
    srcs = fixture_tools.load_sources()
    for rel in (AIM, NT):
        t = tmp_path / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(srcs[rel] + "// drift\n")
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        guard().check(tmp_path)
