"""Lightweight unit tests (CI gate 1). Run: python3 -m unittest discover -s tests -v"""
import base64, hashlib, io, json, os, sys, tempfile, unittest, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fetch_snapshot as fs
import ui_capture as uc
import compare_ui as cu

class TestCrc32c(unittest.TestCase):
    def test_known_vector(self):                      # RFC 3720 check value
        self.assertEqual(fs.crc32c([b"123456789"]), 0xE3069283)
    def test_chunking_invariant(self):
        data = os.urandom(5000)
        self.assertEqual(fs.crc32c([data]), fs.crc32c([data[:1], data[1:2500], data[2500:]]))
    def test_empty(self):
        self.assertEqual(fs.crc32c([b""]), 0)

class TestNodeParsing(unittest.TestCase):
    XML = ('<?xml version="1.0"?><hierarchy><node text="" resource-id="com.x:id/menu_button" content-desc="More" '
           'class="android.widget.ImageButton" package="com.x" clickable="true" enabled="true" focused="false" '
           'selected="false" checked="false" bounds="[900,2180][1035,2337]"/>'
           '<node text="Ask Google or type URL" resource-id="com.x:id/search_box_text" content-desc="" class="android.widget.EditText" '
           'package="com.x" clickable="true" enabled="true" focused="false" selected="false" checked="false" bounds="[203,591][883,780]"/>'
           '<node text="" resource-id="com.x:id/search_box_plus_button" content-desc="Open the context popup" class="android.widget.ImageView" '
           'package="com.x" clickable="true" enabled="true" focused="false" selected="false" checked="false" bounds="[103,651][171,719]"/></hierarchy>')
    def test_parse(self):
        ns = uc.Device.nodes(self.XML)
        self.assertEqual(len(ns), 3)
        self.assertEqual(ns[0]["bounds"], [900, 2180, 1035, 2337]); self.assertEqual(ns[0]["w"], 135)
    def test_exact_omnibox_regex_never_hits_plus_button(self):
        d = uc.Device("com.x", tempfile.mkdtemp(), lambda m: None)
        n = d.find(r":id/(search_box_text|url_bar)$", ("id",), xml=self.XML)
        self.assertTrue(n["id"].endswith("search_box_text"))
    def test_bad_xml(self):
        self.assertEqual(uc.Device.nodes("garbage"), [])

class TestCompare(unittest.TestCase):
    def test_jaccard(self):
        self.assertEqual(cu.jac(set(), set()), 1.0); self.assertEqual(cu.jac({"a"}, {"a", "b"}), 0.5)
    def test_brand_normalisation(self):
        self.assertEqual(cu.norm({"Welcome to Chrome", "Welcome to Chromium"}), {"Welcome to <BRAND>"})
    def test_sig_ignores_other_packages(self):
        nodes = [{"pkg": "com.android.systemui", "id": "x:id/clock", "text": "6:57", "desc": ""},
                 {"pkg": "com.x", "id": "com.x:id/menu_button", "text": "", "desc": "More"}]
        ids, texts, descs = cu.sig(nodes, {"com.x"})
        self.assertEqual(ids, {"menu_button"}); self.assertEqual(texts, set()); self.assertEqual(descs, {"More"})

if __name__ == "__main__":
    unittest.main()

class TestCompareLoader(unittest.TestCase):
    def test_load_skips_non_screen_json(self):
        # regression: chat_fixture.json (no "key") crashed compare_ui.load with KeyError
        with tempfile.TemporaryDirectory() as d:
            json.dump({"package": "p"}, open(os.path.join(d, "meta.json"), "w"))
            json.dump({"platform": "x", "results": None}, open(os.path.join(d, "chat_fixture.json"), "w"))
            json.dump({"key": "02_ntp", "nodes": [], "png": "02_ntp.png"}, open(os.path.join(d, "02_ntp.json"), "w"))
            meta, screens = cu.load(d)
            self.assertEqual(list(screens), ["02_ntp"])
