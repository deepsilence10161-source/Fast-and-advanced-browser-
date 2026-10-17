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
              "Chromebookilla": "Chromebookilla", "Chrome 网上应用店": "Swiftra 网上应用店",
              # लिप्यंतरित (hi/ne/ur); मिलते-जुलते शब्द नहीं छूते
              "क्रोमियम को फिर से शुरू करें": "Swiftra को फिर से शुरू करें", "क्रोमियमले": "Swiftraले",
              "गूगल क्रोम में": "Swiftra में", "क्रोमबुक पर": "क्रोमबुक पर", "क्रोम वेब स्टोर": "क्रोम वेब स्टोर",
              "क्रोमा": "क्रोमा", "کروم کو": "Swiftra کو", "Кроме того": "Кроме того", "Χρώμα": "Χρώμα"}
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
          <message name="IDS_LEGAL_INFORMATION_SUMMARY" desc="x" meaning="Android">Copyright <ph name="year">%1$d<ex>2014</ex></ph> Google LLC. All rights reserved.</message>
          <message name="IDS_ABOUT_VERSION_COPYRIGHT" desc="x">Copyright <ph name="YEAR">{0,date,y}<ex>2016</ex></ph> The Chromium Authors. All rights reserved.</message>
          <if expr="is_android">
            <message name="IDS_QUIT" desc="x">Press to quit</message>
          </if>
          <if expr="_google_chrome">
            <message name="IDS_RESTART" desc="x">Restart Chrome</message>
          </if>
          <if expr="not _google_chrome">
            <message name="IDS_RESTART" desc="x">Restart Chromium</message>
          </if>
        </messages>
      </release>
    </grit>
''')


LEG_OLD = "Copyright YEAR Google LLC. All rights reserved."
LEG_SRC = "Copyright YEAR The Chromium Authors. All rights reserved."


def xtb_name(rel):
    return os.path.splitext(os.path.basename(rel))[0] + "_hi.xtb"


@unittest.skipUnless(GRIT_DIR and os.path.isfile(os.path.join(GRIT_DIR, "grit.py")), "GRIT_DIR नहीं")
class TransformWithRealGrit(unittest.TestCase):
    def setUp(self):
        self.src = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.src, "tools"))
        os.symlink(os.path.abspath(GRIT_DIR), os.path.join(self.src, "tools", "grit"))
        sys.path.insert(0, GRIT_DIR)

    def tearDown(self):
        shutil.rmtree(self.src)

    def _mk_scoped(self, rel, parts):
        """scoped entry: grd में अपना message (scope बाहर) + <part>s (scope भीतर; पहला part test messages, बाकी खाली)।"""
        part = parts[0]
        d = os.path.join(self.src, os.path.dirname(rel)); os.makedirs(os.path.join(d, "translations"), exist_ok=True)
        prel = os.path.relpath(os.path.join(self.src, part), d)
        extra = ""
        for x in parts[1:]:
            os.makedirs(os.path.dirname(os.path.join(self.src, x)), exist_ok=True)
            with open(os.path.join(self.src, x), "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="utf-8"?>\n<grit-part>\n</grit-part>\n')
            extra += f'\n          <part file="{os.path.relpath(os.path.join(self.src, x), d)}" />'
        g = GRD.replace('<message name="IDS_PLAIN" desc="x">Settings</message>',
                        '<message name="IDS_OUT" desc="x">Open Chrome Settings</message>\n'
                        f'          <part file="{prel}" />')
        body = GRD.split("<messages fallback_to_english=\"true\">")[1].split("</messages>")[0]
        body = body.replace('<message name="IDS_PLAIN" desc="x">Settings</message>', "")
        g = g.split("<messages fallback_to_english=\"true\">")[0] + '<messages fallback_to_english="true">\n' + \
            '          <message name="IDS_OUT" desc="x">Open Chrome Settings</message>\n' + \
            f'          <part file="{prel}" />{extra}\n        </messages>' + g.split("</messages>")[1]
        os.makedirs(os.path.dirname(os.path.join(self.src, part)), exist_ok=True)
        open(os.path.join(self.src, part), "w", encoding="utf-8").write(
            '<?xml version="1.0" encoding="utf-8"?>\n<grit-part>' + body + '</grit-part>\n')
        p = os.path.join(self.src, rel); open(p, "w", encoding="utf-8").write(g.replace("t_hi.xtb", xtb_name(rel)))
        ids = {txt: i for i, txt in rb.message_ids(self.src, p)}
        xtb = ['<?xml version="1.0" ?>', '<!DOCTYPE translationbundle>', '<translationbundle lang="hi">',
               f'<translation id="{ids["Open Chrome Settings"]}">Chrome सेटिंग खोलें</translation>',
               f'<translation id="{ids["About Chrome"]}">Chrome के बारे में</translation>',
               f'<translation id="{ids["Press to quit"]}">Chrome बंद करने के लिए दबाएं</translation>',
               f'<translation id="{ids["Restart Chrome"]}">Chrome रीस्टार्ट करें</translation>',
               f'<translation id="{ids["Restart Chromium"]}">Chromium रीस्टार्ट करें</translation>', '</translationbundle>']
        open(os.path.join(d, "translations", xtb_name(rel)), "w", encoding="utf-8").write("\n".join(xtb) + "\n")
        return ids

    def _mk_all(self):
        out = {}
        for e in rb.GRDS:
            if isinstance(e, str):
                out[e] = self._mk(e)
            else:
                out[e[0]] = self._mk_scoped(e[0], e[1])
        return out

    def _mk(self, rel):
        d = os.path.join(self.src, os.path.dirname(rel)); os.makedirs(os.path.join(d, "translations"), exist_ok=True)
        p = os.path.join(self.src, rel); open(p, "w", encoding="utf-8").write(GRD.replace("t_hi.xtb", xtb_name(rel)))
        ids = {}
        for i, txt in rb.message_ids(self.src, p):
            ids[txt] = i
        xtb = ['<?xml version="1.0" ?>', '<!DOCTYPE translationbundle>', '<translationbundle lang="hi">']
        xtb += [f'<translation id="{ids["About Chrome"]}">Chrome के बारे में</translation>',
                f'<translation id="{ids["Visit Chrome Web Store"]}">Chrome वेब स्टोर पर जाएं</translation>',
                f'<translation id="{ids["Settings"]}">सेटिंग</translation>',
                f'<translation id="{ids["Press to quit"]}">Chrome बंद करने के लिए दबाएं</translation>',
                f'<translation id="{ids["Restart Chrome"]}">Chrome रीस्टार्ट करें</translation>',
                f'<translation id="{ids["Restart Chromium"]}">Chromium रीस्टार्ट करें</translation>',
                f'<translation id="{ids[LEG_OLD]}">कॉपीराइट <ph name="YEAR" /> Google LLC. सर्वाधिकार सुरक्षित.</translation>',
                f'<translation id="{ids[LEG_SRC]}">कॉपीराइट <ph name="YEAR" /> Chrome लेखक. सर्वाधिकार सुरक्षित.</translation>',
                '<translation id="111">दूसरी grd का Chrome</translation>', '</translationbundle>']
        open(os.path.join(d, "translations", xtb_name(rel)), "w", encoding="utf-8").write("\n".join(xtb) + "\n")
        return ids

    def test_remap_keeps_translations_and_ids_match_grit(self):
        rels = [e for e in rb.GRDS if isinstance(e, str)]
        old = self._mk_all()
        out = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        touched = [l[8:] for l in out.stdout.splitlines() if l.startswith("TOUCHED ")]
        self.assertEqual(len(touched), 2 * len(rb.GRDS), touched)      # हर grd (या scoped part) + उसका xtb
        # scoped entry: केवल part बदला; grd का अपना message और उसका translation अछूते
        for e in rb.GRDS:
            if isinstance(e, str):
                continue
            g, part = e[0], e[1][0]
            self.assertIn(part, touched); self.assertNotIn(g, touched)
            self.assertIn("Open Chrome Settings", open(os.path.join(self.src, g), encoding="utf-8").read())
            pt = open(os.path.join(self.src, part), encoding="utf-8").read()
            self.assertIn(">About Swiftra</message>", pt); self.assertIn("Restart Swiftra", pt)
            new = {txt: i for i, txt in rb.message_ids(self.src, os.path.join(self.src, g))}
            x = open(os.path.join(self.src, os.path.dirname(g), "translations", xtb_name(g)), encoding="utf-8").read()
            tr = dict(re.findall(r'<translation id="(\d+)">(.*?)</translation>', x))
            self.assertEqual(tr[new["Open Chrome Settings"]], "Chrome सेटिंग खोलें")       # scope बाहर
            self.assertEqual(tr[new["About Swiftra"]], "Swiftra के बारे में")
            self.assertEqual(tr[new["Press to quit"]], "Chrome बंद करने के लिए दबाएं")    # ID न बदला -> scoped में नहीं छूता
            self.assertEqual(tr[new["Restart Swiftra"]], "Swiftra रीस्टार्ट करें")
            ids_in_x = re.findall(r'<translation id="(\d+)">', x)
            self.assertEqual(len(ids_in_x), len(set(ids_in_x)))
        for r in rels:
            p = os.path.join(self.src, r)
            g = open(p, encoding="utf-8").read()
            self.assertIn(">About Swiftra</message>", g)
            self.assertIn('desc="About Chrome page title"', g)              # desc नहीं छूता
            self.assertIn("Visit Chrome Web Store", g)
            self.assertIn('&lt;link&gt;</ph>Swiftra<ph name="END_LINK">', g)
            new = {txt: i for i, txt in rb.message_ids(self.src, p)}       # असली grit से नए IDs
            x = open(os.path.join(os.path.dirname(p), "translations", xtb_name(r)), encoding="utf-8").read()
            tr = dict(re.findall(r'<translation id="(\d+)">(.*?)</translation>', x))
            self.assertEqual(tr[new["About Swiftra"]], "Swiftra के बारे में")
            self.assertNotIn(old[r]["About Chrome"], tr)
            self.assertEqual(tr[new["Visit Chrome Web Store"]], "Chrome वेब स्टोर पर जाएं")   # सुरक्षित message: अनुवाद नहीं छूता
            self.assertEqual(tr[new["Press to quit"]], "Swiftra बंद करने के लिए दबाएं")       # ID वही, अनुवाद में नाम बदला
            self.assertEqual(tr[new["Settings"]], "सेटिंग")
            self.assertEqual(tr["111"], "दूसरी grd का Chrome")                          # दूसरी grd का message नहीं छूता
            ids_in_x = re.findall(r'<translation id="(\d+)">', x)
            self.assertEqual(len(ids_in_x), len(set(ids_in_x)))                          # merge के बाद कोई duplicate ID नहीं
            self.assertEqual(tr[new["Restart Swiftra"]], "Swiftra रीस्टार्ट करें")

    def test_fact_fix_copyright(self):
        """About -> Legal: "Google LLC" दावा हटे; अनुवाद स्रोत message से (tr_fix सहित); स्रोत grd का अनुवाद अछूता।"""
        old = self._mk_all()
        out = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("[fact] IDS_LEGAL_INFORMATION_SUMMARY", out.stderr)
        fx = rb.FACT_FIXES[0]
        p = os.path.join(self.src, fx["grd"])
        g = open(p, encoding="utf-8").read()
        self.assertIn("</ph> The Chromium Authors. All rights reserved.</message>", g)
        self.assertNotIn("Google LLC", g)
        new = {nm: i for i, _, nm in rb.message_ids(self.src, p, names=True)}
        x = open(os.path.join(os.path.dirname(p), "translations", xtb_name(fx["grd"])), encoding="utf-8").read()
        tr = dict(re.findall(r'<translation id="(\d+)">(.*?)</translation>', x))
        # स्रोत-अनुवाद "Chrome लेखक" (upstream fr-CA जैसी भूल) -> tr_fix -> "Chromium लेखक"; branding ("Swiftra") नहीं
        self.assertEqual(tr[new["IDS_LEGAL_INFORMATION_SUMMARY"]], 'कॉपीराइट <ph name="YEAR" /> Chromium लेखक. सर्वाधिकार सुरक्षित.')
        self.assertNotIn(old[fx["grd"]][LEG_OLD], tr)
        self.assertNotIn("Google LLC", x)
        sx = open(os.path.join(self.src, os.path.dirname(fx["tr_from"][0]), "translations",
                               xtb_name(fx["tr_from"][0])), encoding="utf-8").read()
        self.assertIn("Chrome लेखक", sx)                                   # स्रोत grd का अपना अनुवाद नहीं छूता

    def test_fact_fix_missing_source_translation_fails(self):
        old = self._mk_all()
        fx = rb.FACT_FIXES[0]
        sxp = os.path.join(self.src, os.path.dirname(fx["tr_from"][0]), "translations", xtb_name(fx["tr_from"][0]))
        sx = open(sxp, encoding="utf-8").read()
        sx = re.sub(r'<translation id="%s">.*?</translation>\n' % old[fx["tr_from"][0]][LEG_SRC], "", sx)
        open(sxp, "w", encoding="utf-8").write(sx)
        out = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("स्रोत-अनुवाद नहीं", out.stderr)

    def test_fact_fix_target_must_exist_once(self):
        self._mk_all()
        p = os.path.join(self.src, rb.FACT_FIXES[0]["grd"])
        g = open(p, encoding="utf-8").read().replace("IDS_LEGAL_INFORMATION_SUMMARY", "IDS_RENAMED")
        open(p, "w", encoding="utf-8").write(g)
        out = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("0 बार मिला", out.stderr)

    def test_deterministic(self):
        self._mk_all()
        a = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True).stdout
        files = [l[8:] for l in a.splitlines() if l.startswith("TOUCHED ")]
        snap = {r: open(os.path.join(self.src, r), encoding="utf-8").read() for r in files}
        self._mk_all()
        b = subprocess.run([sys.executable, SCRIPT, self.src], capture_output=True, text=True).stdout
        self.assertEqual(a, b)
        for r in files: self.assertEqual(snap[r], open(os.path.join(self.src, r), encoding="utf-8").read())

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
