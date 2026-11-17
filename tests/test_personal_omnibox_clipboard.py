"""Source-level checks of 0108 guard + 0109 patch (omnibox copy/cut stay out of the system clipboard). Host only."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/personal_browser"))
import source_fixture as fixture_tools  # noqa: E402

PERSONAL = ROOT / "patches/personal"
REL = "chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/UrlBar.java"


def guard():
    spec = importlib.util.spec_from_file_location("omni_guard", PERSONAL / "0108-personal-omnibox-source-guard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _apply(tmp_path):
    target = tmp_path / REL
    target.parent.mkdir(parents=True)
    pristine = fixture_tools.load_sources()[REL]
    target.write_text(pristine)
    guard().check(tmp_path)
    subprocess.run(["patch", "-d", str(tmp_path), "-p1", "--forward", "--batch", "--no-backup-if-mismatch",
                    "-i", str(PERSONAL / "0109-personal-omnibox-clipboard.patch")], check=True, capture_output=True)
    return pristine, target.read_text()


def test_patch_removes_both_fall_through_paths_to_the_platform_clipboard(tmp_path):
    pristine, out = _apply(tmp_path)
    assert "if (replacementCutCopyText == null) break;" in pristine
    assert "if (replacementCutCopyText == null) break;" not in out
    assert "if (mTextContextMenuDelegate == null) return super.onTextContextMenuItem(id);" not in out
    assert out.count("Clipboard.getInstance().setText(") == pristine.count("Clipboard.getInstance().setText(") + 1


def test_guard_refuses_drifted_source(tmp_path):
    target = tmp_path / REL
    target.parent.mkdir(parents=True)
    target.write_text(fixture_tools.load_sources()[REL] + "\n// drift\n")
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        guard().check(tmp_path)
