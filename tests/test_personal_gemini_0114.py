"""Source-level checks of patch 0114 (Gemini chat entry + keep the Google web sign-in). Host only; no device claims."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = (ROOT / "patches/personal/0114-personal-gemini-chat.patch").read_text()
GUARD = ROOT / "patches/personal/0114-personal-gemini-source-guard.py"


def test_series_order():
    names = [n for n in (ROOT / "patches/personal/series").read_text().splitlines() if n and not n.startswith("#")]
    assert names[-2:] == ["0114-personal-gemini-source-guard.py", "0114-personal-gemini-chat.patch"]


def test_patch_touches_only_expected_files():
    files = set(re.findall(r"(?m)^\+\+\+ b/(\S+)", PATCH))
    assert files == {
        "chrome/android/chrome_java_sources.gni",
        "chrome/android/java/res/values/ids.xml",
        "chrome/android/java/res/xml/main_preferences.xml",
        "chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java",
        "chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java",
        "chrome/android/java/src/org/chromium/chrome/browser/settings/MainSettings.java",
        "chrome/android/java/src/org/chromium/chrome/browser/swiftra/gemini/SwiftraGemini.java",
        "chrome/browser/browsing_data/android/BUILD.gn",
        "chrome/browser/browsing_data/android/java/src/org/chromium/chrome/browser/browsing_data/BrowsingDataBridge.java",
        "chrome/browser/browsing_data/android/java/src/org/chromium/chrome/browser/browsing_data/SwiftraKeepSignin.java",
    }


def test_no_chat_content_is_stored_or_sent_by_the_patch():
    # Gemini runs on the website; the patch must not add its own network, storage or key handling.
    added = "\n".join(l[1:] for l in PATCH.splitlines() if l.startswith("+") and not l.startswith("+++"))
    for forbidden in ("HttpURLConnection", "OkHttp", "apiKey", "x-goog-api-key", "FileOutputStream", "SQLite"):
        assert forbidden not in added
    assert "https://gemini.google.com/app" in added


def test_only_google_com_is_kept_and_default_is_on():
    assert 'DOMAIN = "google.com"' in PATCH
    assert 'getBoolean(PREF, true)' in PATCH
    assert 'excludedDomains = SwiftraKeepSignin.withKeptDomains(excludedDomains);' in PATCH
    assert '"//base:base_java"' in PATCH


def test_guard_script_is_valid_python_and_pins_eight_files():
    spec = importlib.util.spec_from_file_location("g0114", GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert len(m.EXPECTED) == 8 and len(m.NEW_PATHS) == 2
    assert all(re.fullmatch(r"[0-9a-f]{64}", v) for v in m.EXPECTED.values())


def test_three_dot_menu_has_gemini_row_before_settings_in_every_menu_mode():
    assert PATCH.count("+        modelList.add(buildSwiftraGeminiItem());") == 4
    assert 'model.set(AppMenuItemProperties.TITLE, "Gemini chat");' in PATCH
    assert "R.id.swiftra_gemini_menu_id" in PATCH and 'name="swiftra_gemini_menu_id"' in PATCH
    assert "+        } else if (id == R.id.swiftra_gemini_menu_id) {" in PATCH
    assert "SwiftraGemini.openGemini();" in PATCH
