"""Swiftra product-logo overlay (tools/brand/swiftra_logo.py) — committed assets generator से मेल खाएँ और
Chromium 155 मूल assets के आयाम/Lottie ढाँचे जैसे हों (FRE inflate पर Lottie parse विफल = crash का जोखिम)।"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageChops

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BASE = "components/browser_ui/styles/android/java/res_chromium"
OV = os.path.join(ROOT, "patches", "overlay", BASE)
FRE = {"mdpi": 130, "hdpi": 194, "xhdpi": 260, "xxhdpi": 390, "xxxhdpi": 520}   # Chromium 155 मूल आकार
NAME_H = {"mdpi": 21, "hdpi": 32, "xhdpi": 42, "xxhdpi": 63, "xxxhdpi": 84}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


class LogoAssets(unittest.TestCase):
    def test_dimensions_and_full_canvas_circle(self):
        for d, s in FRE.items():
            with Image.open(os.path.join(OV, f"drawable-{d}", "fre_product_logo.png")) as im:
                self.assertEqual(im.size, (s, s), d)
                im = im.convert("RGBA")
                self.assertEqual(im.getpixel((0, 0))[3], 0, d)                    # कोना पारदर्शी
                self.assertEqual(im.getpixel((s // 2, 1))[3], 255, d)             # गोला किनारे तक
                self.assertEqual(im.getpixel((s * 48 // 100, s // 2))[:3], (255, 255, 255), d)  # पहली chevron सफ़ेद
            with Image.open(os.path.join(OV, f"drawable-{d}", "product_logo_name.png")) as im:
                self.assertEqual(im.size[1], NAME_H[d], d)
                self.assertGreater(im.size[0], 3 * NAME_H[d], d)

    def test_lottie_structure(self):
        j = json.load(open(os.path.join(OV, "raw", "signin_spin.json"), encoding="utf-8"))
        self.assertEqual((j["w"], j["h"], j["fr"], j["ip"], j["op"]), (180, 180, 30, 0, 30))
        inds = {l["ind"] for l in j["layers"]}
        for l in j["layers"]:
            self.assertIn(l["ty"], (3, 4))
            if "parent" in l:
                self.assertIn(l["parent"], inds)
        null = j["layers"][0]
        self.assertAlmostEqual(null["ks"]["s"]["k"][0] * 2 * 48 / 100, 180, delta=0.5)    # frame 0 = पूरा canvas (static logo जैसा)
        ell = [it for l in j["layers"] if l["ty"] == 4 for g in l["shapes"] for it in g["it"] if it["ty"] == "el"]
        self.assertEqual(ell[0]["s"]["k"], [96.0, 96.0])   # त्रिज्या 48
        for l in j["layers"][1:]:
            kf = l["ks"]["s"]["k"]
            self.assertEqual(kf[0]["s"][:2], [100, 100]); self.assertEqual(kf[-1]["s"][:2], [0, 0])

    @unittest.skipUnless(os.path.isfile(FONT), "DejaVu font नहीं")
    def test_committed_assets_match_generator(self):
        with tempfile.TemporaryDirectory() as t:
            subprocess.run([sys.executable, os.path.join(ROOT, "tools", "brand", "swiftra_logo.py"), t], check=True)
            for dp, _, fns in os.walk(os.path.join(t, BASE)):
                for f in fns:
                    rel = os.path.relpath(os.path.join(dp, f), os.path.join(t, BASE))
                    if f.endswith(".json"):
                        with open(os.path.join(dp, f), "rb") as a, open(os.path.join(OV, rel), "rb") as b:
                            self.assertEqual(a.read(), b.read(), rel)
                        continue
                    # PNG: Pillow/FreeType version के अनुसार bytes बदल सकते हैं -> decoded pixels छूट के साथ
                    with Image.open(os.path.join(dp, f)) as a, Image.open(os.path.join(OV, rel)) as b:
                        self.assertEqual(a.size, b.size, rel)
                        diff = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA"))
                        hist = diff.convert("L").histogram()
                        bad = sum(hist[24:])
                        self.assertLessEqual(bad, a.size[0] * a.size[1] // 100, rel)


if __name__ == "__main__":
    unittest.main()


class PopularSitesOverlay(unittest.TestCase):
    """पहली NTP के tiles: Chromium-dev सूची (chromium.org, codereview, freenode, chrome://flags) की जगह
    gstatic suggested_sites_DEFAULT_7.json (वही जो fetch के बाद दिखती है)।"""
    def test_no_chromium_dev_tiles(self):
        p = os.path.join(ROOT, "patches", "overlay", "components", "ntp_tiles", "resources", "default_popular_sites.json")
        j = json.load(open(p, encoding="utf-8"))
        self.assertEqual(len(j), 8)
        for x in j:
            self.assertTrue(x["url"].startswith(("https://", "http://")), x)
            self.assertNotRegex(x["title"] + x["url"], r"(?i)chrom|freenode")
            self.assertTrue(set(x) <= {"title", "url", "favicon_url", "large_icon_url", "title_source"}, x)
