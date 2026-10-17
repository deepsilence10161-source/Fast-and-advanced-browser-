"""scripts/ui_capture.py settings crawler: toggle वाली rows कभी tap न हों (setting बदलना = test state बिगाड़ना)।"""
import importlib.util
import os
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
spec = importlib.util.spec_from_file_location("uic", os.path.join(ROOT, "scripts", "ui_capture.py"))
uic = importlib.util.module_from_spec(spec); spec.loader.exec_module(uic)

XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation="0">
<node text="" class="android.widget.FrameLayout" package="p" bounds="[0,0][1080,2400]" checkable="false">
<node text="Privacy and security" resource-id="" class="android.widget.TextView" package="p" bounds="[160,120][700,200]" checkable="false"/>
<node text="Safe Browsing" resource-id="android:id/title" class="android.widget.TextView" package="p" bounds="[60,400][800,457]" checkable="false"/>
<node text="Lock Incognito tabs" resource-id="android:id/title" class="android.widget.TextView" package="p" bounds="[60,600][800,657]" checkable="false"/>
<node text="" resource-id="android:id/switch_widget" class="android.widget.Switch" package="p" bounds="[900,610][1020,690]" checkable="true"/>
<node text="Standard protection" resource-id="android:id/title" class="android.widget.TextView" package="p" bounds="[160,900][800,957]" checkable="false"/>
<node text="" resource-id="p:id/radio" class="android.widget.RadioButton" package="p" bounds="[40,890][120,990]" checkable="true"/>
</node></hierarchy>"""


class Crawler(unittest.TestCase):
    def setUp(self):
        self.ns = uic.Device.nodes(XML) if hasattr(uic, "Device") else None
        if self.ns is None:
            cls = [v for v in vars(uic).values() if isinstance(v, type) and hasattr(v, "nodes")][0]
            self.ns = cls.nodes(XML)
        self.by = {n["text"]: n for n in self.ns if n["text"]}

    def test_toggle_rows_detected(self):
        self.assertFalse(uic.row_has_toggle(self.ns, self.by["Safe Browsing"]))
        self.assertTrue(uic.row_has_toggle(self.ns, self.by["Lock Incognito tabs"]))     # switch
        self.assertTrue(uic.row_has_toggle(self.ns, self.by["Standard protection"]))     # radio

    def test_skip_rules(self):
        import re
        for t in ("Sign in to Swiftra", "Terms of Service", "Privacy notice", "Safety check"):
            self.assertRegex(t, uic.SUBPAGE_SKIP)
        for t in ("Safe Browsing", "Site settings", "Delete browsing data"):
            self.assertIsNone(re.search(uic.SUBPAGE_SKIP, t))
        self.assertRegex("Privacy and security", uic.SETTINGS_DEEP)
        self.assertIsNone(re.search(uic.SETTINGS_DEEP, "Search engine"))               # radio सूची


class CurrentList(unittest.TestCase):
    def test_last_recycler_wins(self):
        """असली x64 dump (20_set_04): पुराने main list की rows subpage में न गिनी जाएँ।"""
        xml = """<hierarchy><node class="F" package="p" bounds="[0,0][1080,2400]">
<node resource-id="p:id/recycler_view" class="RecyclerView" package="p" bounds="[0,275][1080,2337]">
<node text="Search engine" resource-id="android:id/title" class="T" package="p" bounds="[84,1008][996,1065]"/></node>
<node resource-id="p:id/recycler_view" class="RecyclerView" package="p" bounds="[0,275][1080,2337]">
<node text="Safe Browsing" resource-id="android:id/title" class="T" package="p" bounds="[84,1716][354,1773]"/></node>
</node></hierarchy>"""
        cls = [v for v in vars(uic).values() if isinstance(v, type) and hasattr(v, "nodes")][0]

        class D:
            nodes = staticmethod(cls.nodes)
        self.assertEqual([n["text"] for n in uic.current_list_titles(D, xml, "p")], ["Safe Browsing"])
