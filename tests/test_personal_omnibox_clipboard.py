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


PINNED = (
    REL,
    "chrome/android/java/src/org/chromium/chrome/browser/findinpage/FindToolbar.java",
    "components/browser_ui/widget/android/java/src/org/chromium/components/browser_ui/widget/text/AlertDialogEditText.java",
    "components/browser_ui/widget/android/java/res/layout/radio_button_with_edit_text.xml",
)


def _stage(tmp_path):
    srcs = fixture_tools.load_sources()
    for rel in PINNED:
        t = tmp_path / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(srcs[rel])
    guard().check(tmp_path)
    subprocess.run(["patch", "-d", str(tmp_path), "-p1", "--forward", "--batch", "--no-backup-if-mismatch",
                    "-i", str(PERSONAL / "0109-personal-omnibox-clipboard.patch")], check=True, capture_output=True)
    return srcs


def _apply(tmp_path):
    srcs = _stage(tmp_path)
    return srcs[REL], (tmp_path / REL).read_text()


def test_patch_removes_both_fall_through_paths_to_the_platform_clipboard(tmp_path):
    pristine, out = _apply(tmp_path)
    assert "if (replacementCutCopyText == null) break;" in pristine
    assert "if (replacementCutCopyText == null) break;" not in out
    assert "if (mTextContextMenuDelegate == null) return super.onTextContextMenuItem(id);" not in out
    assert out.count("Clipboard.getInstance().setText(") == pristine.count("Clipboard.getInstance().setText(") + 1


FIND = "chrome/android/java/src/org/chromium/chrome/browser/findinpage/FindToolbar.java"


def test_find_in_page_copy_cut_use_the_contained_clipboard(tmp_path):
    srcs = _stage(tmp_path)
    out = (tmp_path / FIND).read_text()
    assert "android.R.id.copy || id == android.R.id.cut" in out
    assert "Clipboard.getInstance().setText(query.subSequence" in out
    assert out.count("setPrimaryClip") == srcs[FIND].count("setPrimaryClip")


DIALOG = PINNED[2]
RADIO = PINNED[3]


def test_dialog_and_settings_edit_text_copy_cut_use_the_contained_clipboard(tmp_path):
    srcs = _stage(tmp_path)
    out = (tmp_path / DIALOG).read_text()
    assert "public boolean onTextContextMenuItem(int id)" in out
    assert "id == android.R.id.copy || id == android.R.id.cut" in out
    assert "Clipboard.getInstance().setText(text.subSequence" in out
    assert "setPrimaryClip" not in out and "getSystemService" not in out
    assert "import org.chromium.ui.base.Clipboard;" in out
    assert "onTextContextMenuItem" not in srcs[DIALOG]


def test_settings_homepage_edit_text_is_the_patched_class(tmp_path):
    srcs = _stage(tmp_path)
    out = (tmp_path / RADIO).read_text()
    assert "<EditText" in srcs[RADIO] and "<EditText" not in out
    assert out.count("widget.text.AlertDialogEditText") == 1
    assert 'android:id="@+id/edit_text"' in out
