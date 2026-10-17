"""Offline tests for scripts/ci/shield_e2e.py (classification, honesty verdict, Settings-UI parsing).
The device part itself is verified in CI (ui-capture / arm64-device-e2e)."""
import importlib.util
import json
import os
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("shield_e2e", os.path.join(HERE, "..", "scripts", "ci", "shield_e2e.py"))
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

PHISH = ("Dangerous site\nAttackers on the site you tried visiting might trick you into installing software or "
         "revealing things like your passwords. Swiftra strongly recommends going back to safety.")
HARMFUL = ("Dangerous site\nAttackers on the site you tried visiting might trick you into installing harmful software "
           "that affects the way you browse. Swiftra strongly recommends going back to safety.")
MALWARE = "Dangerous site\nAttackers on the site you tried visiting might install harmful software that steals"


class Classify(unittest.TestCase):
    def test_types(self):
        self.assertEqual(E.classify(PHISH, ""), "blocked_phishing")
        self.assertEqual(E.classify(HARMFUL, ""), "blocked_harmful")   # must not be read as phishing
        self.assertEqual(E.classify(MALWARE, ""), "blocked_malware")
        self.assertEqual(E.classify("Not Found\nThe requested URL was not found", ""), "loaded")
        self.assertEqual(E.classify("Example Domain", E.MARKERS["example_com"]), "loaded")

    def test_case_tables(self):
        ids = [c[0] for c in E.CASES]
        self.assertEqual(len(ids), len(set(ids)))
        for cid, _, _ in E.CASES:
            self.assertIn(cid, E.MARKERS)
        for cid, url, exp in E.ESB_CASES:
            self.assertTrue(cid.startswith("esb_"))
            self.assertIn(cid[4:], E.MARKERS, cid)
        esb = {c[0]: c for c in E.ESB_CASES}
        self.assertEqual(esb["esb_google_test_unwanted"][2], "blocked_harmful")
        self.assertEqual(esb["esb_public_shield_canary"][2], "blocked_phishing")
        std = {c[0]: c for c in E.CASES}
        self.assertEqual(std["google_test_unwanted"][2], "loaded")     # Shield has no unwanted list
        self.assertIn("swiftra_shield_canary", std["public_shield_canary"][1])


class NativeUi(unittest.TestCase):
    def test_chrome_word(self):
        """Enhanced-protection message banner (native UI) must not name Chrome (E2E 39022805609 screenshot)."""
        self.assertTrue(E.CHROME_WORD.search("You have Chrome\u2019s strongest security against harmful websites"))
        self.assertFalse(E.CHROME_WORD.search("You have Swiftra\u2019s strongest security against harmful websites"))
        self.assertFalse(E.CHROME_WORD.search("Chrome Web Store"))
        self.assertFalse(E.CHROME_WORD.search("Chromium"))


class Honesty(unittest.TestCase):
    def run_h(self, d):
        with mock.patch.object(E, "page_text", return_value=json.dumps(d)):
            return E.honesty("http://x", "https://u/")

    def test_clean_page(self):
        h = self.run_h({"chrome_word": False, "swiftra_word": True, "google_safe_browsing": False,
                        "diagnostic_link": False, "report_error_link": False, "google_sb_urls": False,
                        "final_paragraph": "Only visit this unsafe site if you're sure you understand the risks."})
        self.assertTrue(h["pass"], h)

    def test_upstream_page(self):
        h = self.run_h({"chrome_word": True, "swiftra_word": False, "google_safe_browsing": True,
                        "diagnostic_link": True, "report_error_link": True, "google_sb_urls": True,
                        "final_paragraph": "Only visit this unsafe site if you're sure you understand the risks."})
        self.assertFalse(h["pass"])
        for k in ("chrome_word", "google_safe_browsing", "diagnostic_link", "report_error_link", "google_sb_urls",
                  "no_swiftra_word"):
            self.assertIn(k, h["problems"])

    def test_no_final_paragraph_or_unreadable(self):
        h = self.run_h({"swiftra_word": True, "final_paragraph": ""})
        self.assertIn("final_paragraph_missing", h["problems"])
        with mock.patch.object(E, "page_text", return_value=None):
            self.assertIsNone(E.honesty("http://x", "https://u/"))
        with mock.patch.object(E, "page_text", return_value="devtools error"):
            self.assertIsNone(E.honesty("http://x", "https://u/"))


SB_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation="0">
<node text="Safe Browsing" resource-id="" checkable="false" checked="false" bounds="[0,100][1080,200]"/>
<node text="" resource-id="com.swiftra.app:id/radio_button" checkable="true" checked="{esb}" bounds="[40,420][120,500]"/>
<node text="Enhanced protection" resource-id="com.swiftra.app:id/title" checkable="false" checked="false" bounds="[160,400][900,450]"/>
<node text="" resource-id="com.swiftra.app:id/radio_button" checkable="true" checked="{std}" bounds="[40,720][120,800]"/>
<node text="Standard protection" resource-id="com.swiftra.app:id/title" checkable="false" checked="false" bounds="[160,700][900,750]"/>
</hierarchy>"""


class SettingsUi(unittest.TestCase):
    def fake_adb(self, xml):
        def adb(*args, timeout=30):
            if args[:2] == ("exec-out", "cat"):
                return xml
            if args[:3] == ("shell", "dumpsys", "window"):
                return "  mCurrentFocus=Window{1 u0 com.swiftra.app/org.chromium.chrome.browser.settings.SettingsActivity}"
            return ""
        return adb

    def test_nodes_and_focus(self):
        with mock.patch.object(E, "adb", self.fake_adb(SB_XML.format(esb="true", std="false"))):
            ns, _ = E.ui_nodes()
            self.assertEqual(len(ns), 5)
            t = [n for n in ns if n["text"] == "Enhanced protection"][0]
            self.assertEqual((t["cx"], t["cy"]), (530, 425))
            self.assertTrue(E.focused_window().endswith("SettingsActivity"))

    def test_radio_state(self):
        """set_safe_browsing must read the radio of the selected row, not its neighbour."""
        for esb, std, want in (("true", "false", True), ("false", "true", False)):
            with mock.patch.object(E, "adb", self.fake_adb(SB_XML.format(esb=esb, std=std))), \
                 mock.patch.object(E, "time") as t, \
                 mock.patch.object(E, "find_text", side_effect=lambda s, **k: ({"cx": 1, "cy": 1}, [])), \
                 mock.patch.object(E, "to_browser", return_value=True), \
                 mock.patch.object(E, "ui_nodes", wraps=E.ui_nodes) as un, \
                 mock.patch.object(E.subprocess, "run") as run, \
                 mock.patch("builtins.open", mock.mock_open()):
                t.sleep = lambda *_: None
                run.return_value.stdout = b""
                ns, xml = E.ui_nodes()
                menu = {"text": "", "desc": "", "id": "com.swiftra.app:id/menu_button", "checkable": False,
                        "checked": False, "cx": 1, "cy": 1, "h": 50}
                un.side_effect = [([menu], ""), (ns, xml)]
                r = E.set_safe_browsing("com.swiftra.app", "Enhanced protection", "/tmp")
                self.assertEqual(r["set"], want, r)



class C2cTruthAndNetwork(unittest.TestCase):
    def test_sb_page_truth(self):
        upstream = ["Enhanced protection", "Real-time, AI-powered protection against dangerous sites, downloads, and "
                    "extensions that's based on your browsing data getting sent to Google", "Standard protection",
                    "Protects against sites, downloads, and extensions that are known to be dangerous. If a page does "
                    "something suspicious, URLs and bits of page content are sent to Google Safe Browsing."]
        r = E.sb_page_truth(upstream)
        self.assertFalse(r["pass"]); self.assertEqual(len(r["false_claims"]), 2); self.assertEqual(len(r["missing_expected"]), 2)
        fixed = ["Enhanced protection", E.SB_PAGE_EXPECT[1], "Standard protection", E.SB_PAGE_EXPECT[0]]
        self.assertTrue(E.sb_page_truth(fixed)["pass"])
        self.assertFalse(E.sb_page_truth(None)["pass"])

    def test_google_hosts(self):
        for h in ("safebrowsing.google.com", "optimizationguide-pa.googleapis.com", "www.gstatic.com", "redirector.gvt1.com"):
            self.assertTrue(E.is_google(h), h)
        for h in ("example.com", "github.com", "notgoogle.com", "googleapis.com.evil.net", "release-assets.githubusercontent.com"):
            self.assertFalse(E.is_google(h), h)

    def test_host_regex_on_netlog_args(self):
        blob = json.dumps({"params": {"url": "https://safebrowsing.google.com/safebrowsing/clientreport/realtime?x=1",
                                      "host": "example.com", "other": "wss://a.b.c:443/x", "n": "http://127.0.0.1:8001/p"}})
        hosts = {(a or b) for a, b in E.HOST_RX.findall(blob)}
        self.assertEqual(hosts, {"safebrowsing.google.com", "example.com", "a.b.c", "127.0.0.1"})
        self.assertIn("safebrowsing.google.com", E.SB_HOSTS)


if __name__ == "__main__":
    unittest.main()
