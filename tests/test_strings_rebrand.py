"""b2 string rebrand (patches/0002-swiftra-strings.py) + patches.py की ".py" series प्रविष्टि।

Grit वाले tests: GRIT_DIR (Chromium का tools/grit) हो तो चलते हैं, वरना skip — unit-tests.yml उसे 155.0.8059.80 tag से लाता है।
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCRIPT = os.path.join(ROOT, "patches", "0002-swiftra-strings.py")
spec = importlib.util.spec_from_file_location("rebrand", SCRIPT)
rb = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
GRIT_DIR = os.environ.get("GRIT_DIR", "")


class Rules(unittest.TestCase):
    def test_english_rules(self):
        cases = {
            "About Chrome": "About Swiftra", "Customize and control Google Chrome": "Customize and control Swiftra",
            "Chromium won't save": "Swiftra won't save", "Chrome's tips": "Swiftra's tips", "&Chromium": "&Swiftra",
            # सुरक्षित
            "Chrome Web Store": "Chrome Web Store", "ChromeOS": "ChromeOS", "Chrome OS": "Chrome OS", "Chromebook": "Chromebook",
            "Chromecast": "Chromecast", "ChromiumOS": "ChromiumOS", "chrome://flags": "chrome://flags",
            "the Chromium open source project": "the Chromium open source project", "The Chromium Authors": "The Chromium Authors",
            "Google Chrome and ChromeOS Additional Terms of Service": "Google Chrome and ChromeOS Additional Terms of Service",
            "Chrome Privacy Notice": "Chrome Privacy Notice", "monochrome": "monochrome",
        }
        for a, b in cases.items():
            self.assertEqual(rb.brand_markup(a), b, a)

    def test_placeholders_untouched(self):
        s = 'Open <ph name="LINK">Chrome<ex>Chrome</ex></ph> in Chrome <ph name="X"/> Chrome'
        self.assertEqual(rb.brand_markup(s), 'Open <ph name="LINK">Chrome<ex>Chrome</ex></ph> in Swiftra <ph name="X"/> Swiftra')

    def test_translation_inflections_and_prefixes(self):
        tr = {"Chromen": "Swiftran", "Chromiumu": "Swiftrau", "ስለChromium": "ስለSwiftra", "seChromium": "seSwiftra",
              "IChromium": "ISwiftra", "Chrome में": "Swiftra में", "Chromecastiin": "Chromecastiin",
              "Chromebookilla": "Chromebookilla", "Chrome 网上应用店": "Swiftra 网上应用店"}
        for a, b in tr.items():
            self.assertEqual(rb.brand_markup(a, tr=True), b, a)


GRD = textwrap.dedent('''\
    <?xml version="1.0" encoding="UTF-8"?>
    <grit base_dir="." latest_public_release="0" current_release="1" source_lang_id="en" enc_check="möl">
      <outputs>
        <output filename="values/t.xml" type="android" lang="en" />
        <output filename="values-hi/t.xml" type="android" lang="hi" />
      </outputs>
      <translations>
        <file path="translations/t_hi.xtb" lang="hi" />
      </translations>
      <release seq="1">
        <messages fallback_to_english="true">
          <message name="IDS_ABOUT" desc="About Chrome page title">About Chrome</message>
          <message name="IDS_STORE" desc="x">Visit Chrome Web Store</message>
          <message name="IDS_PLAIN" desc="x">Settings</message>
          <message name="IDS_LINK" desc="x">Open <ph name="BEGIN_LINK">&lt;link&gt;</ph>Chrome<ph name="END_LINK">&lt;/link&gt;</ph> help</message>
          <if expr="is_android">
            <message name="IDS_QUIT" desc="x">Press to quit</message>
          </if>
        </messages>
      </release>
    </grit>
''')


@unittest.skipUnless(GRIT_DIR and os.path.isfile(os.path.join(GRIT_DIR, "grit.py")), "GRIT_DIR नहीं")
class TransformWithRealGrit(unittest.TestCase):
    def setUp(self):
        self.src = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.src, "tools"))
        os.symlink(os.path.abspath(GRIT_DIR), os.path.join(self.src, "tools", "grit"))
        sys.path.insert(0, GRIT_DIR)

    def tearDown(self):
        shutil.rmtree(self.src)

    def _mk(self, rel):
        d = os.path.join(self.src, os.path.dirname(rel)); os.makedirs(os.path.join(d, "translations"), exist_ok=True)
        p = os.path.join(self.src, rel); open(p, "w", encoding="utf-8").write(GRD)
        ids = {}
        for i, txt in rb.message_ids(self.src, p):
            ids[txt] = i
        xtb = ['<?xml version="1.0" ?>', '<!DOCTYPE translationbundle>', '<translationbundle lang="hi">']
        xtb += [f'<translation id="{ids["About Chrome"]}">Chrome के बारे में</translation>',
                f'<translation id="{ids["Visit Chrome Web Store"]}">Chrome वेब स्टोर पर जाएं</translation>',
                f'<translation id="{ids["Settings"]}">सेटिंग</translation>',
                f'<translation id="{ids["Press to quit"]}">Chrome बंद करने के लिए दबाएं</translation>',
                '<translation id="111">दूसरी grd का Chrome</translation>', '</translationbundle>']
        open(os.path.join(d, "translations", "t_hi.xtb"), "w", encoding="utf-8").write("\n".join(xtb) + "\n")
        return ids

    def test_remap_keeps_translations_and_ids_match_grit(self):
        rels = rb.GRDS
        old = {r: self._mk(r) for r in rels}
        out = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        touched = [l[8:] for l in out.stdout.splitlines() if l.startswith("TOUCHED ")]
        self.assertEqual(len(touched), 2 * len(rels), touched)          # हर grd + उसका xtb
        for r in rels:
            p = os.path.join(self.src, r)
            g = open(p, encoding="utf-8").read()
            self.assertIn(">About Swiftra</message>", g)
            self.assertIn('desc="About Chrome page title"', g)              # desc नहीं छूता
            self.assertIn("Visit Chrome Web Store", g)
            self.assertIn('&lt;link&gt;</ph>Swiftra<ph name="END_LINK">', g)
            new = {txt: i for i, txt in rb.message_ids(self.src, p)}       # असली grit से नए IDs
            x = open(os.path.join(os.path.dirname(p), "translations", "t_hi.xtb"), encoding="utf-8").read()
            tr = dict(re.findall(r'<translation id="(\d+)">(.*?)</translation>', x))
            self.assertEqual(tr[new["About Swiftra"]], "Swiftra के बारे में")
            self.assertNotIn(old[r]["About Chrome"], tr)
            self.assertEqual(tr[new["Visit Chrome Web Store"]], "Chrome वेब स्टोर पर जाएं")   # सुरक्षित message: अनुवाद नहीं छूता
            self.assertEqual(tr[new["Press to quit"]], "Swiftra बंद करने के लिए दबाएं")       # ID वही, अनुवाद में नाम बदला
            self.assertEqual(tr[new["Settings"]], "सेटिंग")
            self.assertEqual(tr["111"], "दूसरी grd का Chrome")                          # दूसरी grd का message नहीं छूता

    def test_deterministic(self):
        for r in rb.GRDS: self._mk(r)
        a = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True).stdout
        snap = {r: open(os.path.join(self.src, r), encoding="utf-8").read() for r in rb.GRDS}
        for r in rb.GRDS: self._mk(r)
        b = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True).stdout
        self.assertEqual(a, b)
        for r in rb.GRDS: self.assertEqual(snap[r], open(os.path.join(self.src, r), encoding="utf-8").read())

    def test_missing_grd_fails(self):
        out = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)


class PatchesPyEntry(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "ci")); import patches; self.p = patches
        self.d = tempfile.mkdtemp(); self.src = os.path.join(self.d, "src"); self.pd = os.path.join(self.d, "p")
        os.makedirs(os.path.join(self.src, "a")); os.makedirs(self.pd)
        open(os.path.join(self.src, "a", "f.txt"), "w").write("Chrome\n")

    def tearDown(self):
        shutil.rmtree(self.d)

    def _run(self, body):
        open(os.path.join(self.pd, "x.py"), "w").write(body)
        open(os.path.join(self.pd, "series"), "w").write("x.py\n")
        out = os.path.join(self.d, "o.json")
        rc = self.p.apply(self.src, self.pd, "-", out, now=1000)
        return rc, (json.load(open(out)) if rc == 0 else None)

    def test_touched_files_recorded_and_hash_includes_script(self):
        rc, j = self._run("import sys,os\np=os.path.join(sys.argv[1],'a','f.txt')\nopen(p,'w').write('Swiftra\\n')\nprint('TOUCHED a/f.txt')\n")
        self.assertEqual(rc, 0); self.assertEqual(j["files"], ["a/f.txt"]); self.assertTrue(j["changed"])
        self.assertEqual(open(os.path.join(self.src, "a", "f.txt")).read(), "Swiftra\n")
        self.assertEqual(os.stat(os.path.join(self.src, "a", "f.txt")).st_mtime, 1000)
        h1 = self.p.series_hash(self.pd, ["x.py"])
        open(os.path.join(self.pd, "x.py"), "a").write("# change\n")
        self.assertNotEqual(h1, self.p.series_hash(self.pd, ["x.py"]))

    def test_bad_touched_path_and_failure_rejected(self):
        self.assertEqual(self._run("print('TOUCHED ../etc/passwd')\n")[0], 1)
        self.assertEqual(self._run("print('TOUCHED /etc/passwd')\n")[0], 1)
        self.assertEqual(self._run("print('TOUCHED a/missing.txt')\n")[0], 1)
        self.assertEqual(self._run("import sys; sys.exit(3)\n")[0], 1)


if __name__ == "__main__":
    unittest.main()
