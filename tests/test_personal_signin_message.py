"""Source-level checks of the personal sign-in message layer (0106 guard + 0107 patch).

Host/source only: it proves the patch applies to the pinned Chromium 155 file and what the
resulting Java says. It does NOT prove any behaviour on a device.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/personal_browser"))
import source_fixture as fixture_tools  # noqa: E402

PERSONAL = ROOT / "patches/personal"
REL = ("chrome/browser/ui/android/signin/java/src/org/chromium/chrome/browser/ui/signin/"
       "SigninAndHistorySyncCoordinator.java")


def guard():
    spec = importlib.util.spec_from_file_location("signin_guard", PERSONAL / "0106-personal-signin-source-guard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_patch_changes_only_the_error_toast(tmp_path):
    src = fixture_tools.load_sources()
    pristine = src[REL]
    target = tmp_path / REL
    target.parent.mkdir(parents=True)
    target.write_text(pristine)
    guard().check(tmp_path)
    import subprocess
    subprocess.run(["patch", "-d", str(tmp_path), "-p1", "--forward", "--batch", "--no-backup-if-mismatch",
                    "-i", str(PERSONAL / "0107-personal-signin-message.patch")], check=True, capture_output=True)
    out = target.read_text()
    assert "Browser sign-in is turned off in this private build." in out
    assert "Sign in on the website instead." in out
    assert "R.string.signin_account_picker_bottom_sheet_error_title" not in out
    removed = [l for l in pristine.splitlines() if l not in out.splitlines()]
    assert len(removed) == 2          # only the getString(...) lines are replaced
    assert out.count("Toast.makeText(") == pristine.count("Toast.makeText(")


def test_guard_refuses_drifted_source(tmp_path):
    target = tmp_path / REL
    target.parent.mkdir(parents=True)
    target.write_text(fixture_tools.load_sources()[REL] + "\n// drift\n")
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        guard().check(tmp_path)
