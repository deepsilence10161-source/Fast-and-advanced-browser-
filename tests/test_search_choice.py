"""Patch 0014 (search engine choice) + the harness handler for its First Run page / dialog."""
import os, sys, subprocess, tempfile, shutil

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import ui_capture as uc

PATCH = os.path.join(ROOT, "patches", "0014-swiftra-search-choice.patch")


def node(text, bounds, checkable=False, checked=False, enabled=True, clickable=True):
    return (f'<node text="{text}" content-desc="" resource-id="" class="android.widget.RadioButton" '
            f'package="com.swiftra.app" checkable="{str(checkable).lower()}" checked="{str(checked).lower()}" '
            f'clickable="{str(clickable).lower()}" enabled="{str(enabled).lower()}" focused="false" selected="false" '
            f'bounds="{bounds}"/>')


def screen(selected=None):
    engines = ["DuckDuckGo", "Bing", "Google", "Yahoo! India"]
    body = node("Choose your search engine", "[40,200][1040,300]", clickable=False)
    for i, e in enumerate(engines):
        body += node(e, f"[40,{400 + i * 150}][1040,{520 + i * 150}]", checkable=True, checked=(e == selected))
    body += node("Set as default", "[600,2000][1040,2100]", enabled=selected is not None)
    return f'<?xml version="1.0"?><hierarchy rotation="0">{body}</hierarchy>'


class FakeDevice(uc.Device):
    def __init__(self):
        super().__init__("com.swiftra.app", tempfile.mkdtemp(), lambda m: None)
        self.selected, self.taps = None, []

    def dump(self, retries=4):
        return screen(self.selected)

    def tap_node(self, n):
        self.taps.append(n["text"])
        if n["checkable"]:
            self.selected = n["text"]

    def foreground_activity(self):
        return "com.swiftra.app/org.chromium.chrome.browser.firstrun.FirstRunActivity"


def test_handler_picks_fixed_engine_and_confirms(monkeypatch):
    monkeypatch.setattr(uc.time, "sleep", lambda s: None)
    d = FakeDevice()
    assert uc.handle_search_choice(d, d.dump()) is True
    assert d.taps == ["Google", "Set as default"]
    rec = d.search_choice[0]
    assert rec["options"] == ["DuckDuckGo", "Bing", "Google", "Yahoo! India"]
    assert rec["picked"] == "Google" and rec["confirmed"] is True


def test_handler_ignores_other_screens():
    d = FakeDevice()
    assert uc.handle_search_choice(d, '<?xml version="1.0"?><hierarchy rotation="0"></hierarchy>') is False


def test_patch_0014_applies_and_has_the_switch_points():
    text = open(PATCH).read()
    assert "getSwiftraSearchChoiceShowType" in text and "SearchEnginePromoType.SHOW_EXISTING" in text
    assert "getPrepopulatedId() > 0 && templateUrl.getStarterPackId() == 0" in text
    assert "mSearchEnginePromoCompleted || mSearchEnginePromoShownThisSession" in text
    assert "isDefaultSearchManaged()" in text and "isRetailDemoMode()" in text
    # patch must not touch anything but LocaleManagerDelegate (Java only, no native rebuild)
    files = [l.split()[1] for l in text.splitlines() if l.startswith("+++ ")]
    assert files == ["b/chrome/browser/locale/java/src/org/chromium/chrome/browser/locale/LocaleManagerDelegate.java"]
