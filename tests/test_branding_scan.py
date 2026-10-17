"""scripts/ci/branding_scan.py — uiautomator xml में app-UI branding leaks (b2)।"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
import branding_scan as bs  # noqa: E402

P = "com.swiftra.app"


def node(text="", desc="", pkg=P, cls="android.widget.TextView", rid="", children=""):
    a = f'<node index="0" text="{text}" resource-id="{rid}" class="{cls}" package="{pkg}" content-desc="{desc}"'
    return a + (f">{children}</node>" if children else " />")


def doc(*nodes):
    return "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation=\"0\">" + \
        node(cls="android.widget.FrameLayout", children="".join(nodes)) + "</hierarchy>"


class Scan(unittest.TestCase):
    def test_real_leaks_from_b1_capture(self):
        x = doc(node("Make Chrome your own", rid=P + ":id/title"),
                node(desc="Customize and control Google Chrome", cls="android.widget.ImageButton"),
                node("Chromium won’t save:&#10;Your browsing history"),
                node("The Chromium Projects `", rid=P + ":id/tile_view_title"))
        self.assertEqual(len(bs.scan_xml(x, P)), 4)

    def test_swiftra_and_allowed_are_clean(self):
        x = doc(node("Make Swiftra your own"), node("chrome://flags"), node("Visit Chrome Web Store"),
                node("Cast to Chromecast"), node("Copyright The Chromium Authors"), node("monochrome mode"),
                node("Google Chrome and ChromeOS Additional Terms of Service"))
        self.assertEqual(bs.scan_xml(x, P), [])

    def test_web_content_and_other_packages_ignored(self):
        web = node(cls="android.webkit.WebView", children=node("Download Chrome today", cls="android.view.View")
                   + node(cls="android.view.View", children=node("Chromium blog")))
        x = doc(web, node("Chrome", pkg="com.android.systemui"), node("Chrome after webview"), node("open in chromium"))
        l = bs.scan_xml(x, P)
        self.assertEqual([i["value"] for i in l], ["Chrome after webview", "open in chromium"])   # WebView के बाद का sibling फिर गिना जाए

    def test_truth_claims_from_real_settings_capture(self):
        """1f2788f crawl (38989202816) में मिले तीनों असत्य दावे पकड़े जाएँ; सही text 'expected' में गिने।"""
        x = doc(node("Copyright 2026 Google LLC. All rights reserved.", rid="android:id/summary"),
                node("Automatically sends usage statistics and crash reports to Google", rid="android:id/summary"),
                node("Swiftra is up to date", rid="android:id/title"),
                node(cls="android.webkit.WebView", children=node("Chrome is up to date", cls="android.view.View")))
        bad, seen = bs.scan_claims(x, P)
        self.assertEqual(sorted(b["claim"] for b in bad),
                         ["copyright_google_llc", "metrics_sends_to_google", "update_up_to_date"])
        self.assertEqual(seen, set())
        good = doc(node("Copyright 2026 The Chromium Authors. All rights reserved."),
                   node("Can’t check Swiftra version"), node("Version 155.0.8059.80"),
                   node("Make searches and browsing better"), node("Google Terms of Service"))
        bad, seen = bs.scan_claims(good, P)
        self.assertEqual(bad, [])
        self.assertEqual(seen, set(bs.EXPECTED))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as t:
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "ci", "branding_scan.py"), t], capture_output=True)
            self.assertEqual(r.returncode, 2)
            open(os.path.join(t, "a.xml"), "w").write(doc(node("About Swiftra")))
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "ci", "branding_scan.py"), t], capture_output=True)
            self.assertEqual(r.returncode, 0)
            open(os.path.join(t, "b.xml"), "w").write(doc(node("About Chrome")))
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "ci", "branding_scan.py"), t,
                                "--json", os.path.join(t, "o.json")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 3); self.assertIn("1 leaks", r.stdout)


if __name__ == "__main__":
    unittest.main()
