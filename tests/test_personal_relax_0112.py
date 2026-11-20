"""Source-level checks of patch 0112 (clipboard/share/open-file restored, web sign-in, delete scrub). Host only."""
import subprocess, sys, pathlib, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/personal_browser"))
import source_fixture as sf

def tree(tmp):
    d = pathlib.Path(tmp)
    for n, t in sf.load_sources().items():
        p = d / n; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t)
    sf.apply_strict(d, include_relax=True)
    return d

def test_strict_apply_and_effects():
    with tempfile.TemporaryDirectory() as tmp:
        d = tree(tmp)
        base = d / "chrome/android/java/src/org/chromium/chrome/browser"
        assert "BrowserContainedClipboard" not in (d / "ui/android/java/src/org/chromium/ui/base/Clipboard.java").read_text()
        assert "ClipboardImpl" in (d / "ui/android/java/src/org/chromium/ui/base/Clipboard.java").read_text()
        du = (base / "download/DownloadUtils.java").read_text()
        assert "openFileWithExternalApps(" in du and "allowExternalAppHandlers= */ false" not in du
        assert "private_downloads" in (d / "chrome/android/java/res_template/xml/file_paths.xml").read_text()
        assert "SwiftraDeleteScrub.run();" in (base / "browsing_data/ClearBrowsingDataFragment.java").read_text()
        assert "accounts.google.com" in (d / "chrome/browser/ui/android/signin/java/src/org/chromium/chrome/browser/ui/signin/SigninAndHistorySyncCoordinator.java").read_text()
        assert "SwiftraDeleteScrub.java" in (d / "chrome/android/chrome_java_sources.gni").read_text()
        # containment that must remain: private download root and external-navigation closure, FLAG_SECURE, no-learning IME
        assert "browser_contained_download_path.h" in (d / "chrome/browser/download/BUILD.gn").read_text()
        assert "Installed WebAPK/PWA handoffs" in (d / "components/external_intents/android/java/src/org/chromium/components/external_intents/ExternalNavigationHandler.java").read_text()
