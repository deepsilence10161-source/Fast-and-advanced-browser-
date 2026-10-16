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


class TestStagedBuildResume(unittest.TestCase):
    """chromium_stage.sh की resume-विधि: ninja को बीच में रोकें, PAX tar से pack/restore करें,
    बचा काम (ninja -n) बराबर रहे; seconds-only/नई mtime (negative control) पर watchdog पकड़े।"""
    def setUp(self):
        import shutil
        self.ninja = shutil.which("ninja")
        if not self.ninja:
            self.skipTest("ninja नहीं मिला (pip install ninja)")
    def _sh(self, cmd, cwd):
        import subprocess
        return subprocess.run(["bash", "-c", cmd], cwd=cwd, capture_output=True, text=True)
    def _remaining(self, src):
        import re
        r = self._sh("ninja -C out/X -n all", src).stdout
        m = re.findall(r"^\[(\d+)/(\d+)\]", r, re.M)
        return int(m[-1][1]) if m else 0
    def test_pax_restore_keeps_progress_and_watchdog_catches_bad_restore(self):
        import time
        d = tempfile.mkdtemp(); a = os.path.join(d, "a", "src"); os.makedirs(os.path.join(a, "out", "X"))
        lines = ["rule cp", "  command = sleep 0.15 && cp $in $out"]
        for i in range(30):
            open(os.path.join(a, f"in{i}.txt"), "w").write(str(i))
            lines.append(f"build o{i}: cp ../../in{i}.txt")
        lines.append("build all: phony " + " ".join(f"o{i}" for i in range(30)))
        open(os.path.join(a, "out", "X", "build.ninja"), "w").write("\n".join(lines) + "\n")
        self._sh("timeout -s INT 1.2 ninja -C out/X -j2 all", a)
        before = self._remaining(a)
        self.assertTrue(0 < before < 30, before)
        self._sh("tar --format=posix --exclude=./src/out -C a -cf s.tar ./src && tar --format=posix -C a/src -cf o.tar out/X", d)
        time.sleep(1.1)
        b = os.path.join(d, "b"); os.makedirs(b)
        self._sh("tar -xf s.tar -C b && tar -xf o.tar -C b/src", d)
        self.assertEqual(self._remaining(os.path.join(b, "src")), before)       # कोई rebuild नहीं
        c = os.path.join(d, "c"); os.makedirs(c)
        self._sh("tar --format=gnu -C a -cf - ./src | tar -x -C c && touch c/src/in*.txt", d)
        bad = self._remaining(os.path.join(c, "src"))
        self.assertEqual(bad, 30)
        self.assertGreater(bad, before + before // 50 + 0)                       # watchdog शर्त का आधार

    def test_stage_script_syntax_and_args(self):
        p = os.path.join(os.path.dirname(__file__), "..", "scripts", "ci", "chromium_stage.sh")
        r = self._sh(f"bash -n {p}", ".")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = open(p).read()
        for must in ['use_siso = false', 'use_remoteexec = false', 'is_debug = false', '--format=posix', 'WATCHDOG']:
            self.assertIn(must, s)


class TestStageLib(unittest.TestCase):
    """count_remaining: set -euo pipefail में भी कभी script न रोके (सत्र-2 bug का regression test)।"""
    LIB = os.path.join(os.path.dirname(__file__), "..", "scripts", "ci", "stage_lib.sh")
    def setUp(self):
        import shutil
        if not shutil.which("ninja"): self.skipTest("ninja नहीं मिला")
        self.d = tempfile.mkdtemp(); os.makedirs(os.path.join(self.d, "out"))
        with open(os.path.join(self.d, "in.txt"), "w") as f: f.write("x")
        with open(os.path.join(self.d, "out", "build.ninja"), "w") as f:
            f.write("rule cp\n  command = cp $in $out\nbuild a: cp ../in.txt\nbuild b: cp a\nbuild all: phony b\n")
    def _count(self, ninja="ninja"):
        import subprocess
        r = subprocess.run(["bash", "-c", f'set -euo pipefail; source "{self.LIB}"; X=$(count_remaining {ninja} "{self.d}/out" all); echo "R=$X"'],
                           capture_output=True, text=True)
        return r.returncode, r.stdout.strip()
    def test_pending(self):
        self.assertEqual(self._count(), (0, "R=2"))
    def test_no_work_to_do_returns_zero_without_aborting(self):
        import subprocess
        subprocess.run(["ninja", "-C", os.path.join(self.d, "out"), "all"], capture_output=True, check=True)
        self.assertEqual(self._count(), (0, "R=0"))
    def test_missing_ninja_binary(self):
        self.assertEqual(self._count("/nonexistent/ninja"), (0, "R=0"))


class TestPatches(unittest.TestCase):
    """scripts/ci/patches.py: हर stage pristine src + पिछला out restore करता है, फिर patches लगाता है।
    ninja से असली multi-stage अनुकरण: वही patches -> कोई rebuild नहीं; patch बदला/हटाया -> ठीक प्रभावित
    outputs दोबारा बनें और हटाए गए patch का पुराना output न बचे (negative control: सीधा patch यह चूकता है)।"""
    CI = os.path.join(os.path.dirname(__file__), "..", "scripts", "ci")
    def setUp(self):
        import shutil, subprocess
        if not shutil.which("ninja") or not shutil.which("patch"): self.skipTest("ninja/patch नहीं मिला")
        sys.path.insert(0, self.CI); import patches; self.P = patches
        self.d = tempfile.mkdtemp(); pr = os.path.join(self.d, "pristine", "src")
        os.makedirs(os.path.join(pr, "out", "X"))
        lines = ["rule cp", "  command = cp $in $out"]
        for i in (1, 2, 3):
            open(os.path.join(pr, f"f{i}.txt"), "w").write(f"orig{i}\n")
            lines.append(f"build o{i}: cp ../../f{i}.txt")
        lines.append("build all: phony o1 o2 o3")
        open(os.path.join(pr, "out", "X", "build.ninja"), "w").write("\n".join(lines) + "\n")
        self._sh("tar --format=posix -C pristine -cf src.tar --exclude=./src/out ./src && "
                 "tar --format=posix -C pristine/src -cf out.tar out/X")   # stage-0 जैसा: pristine src + खाली out
        self.pd = os.path.join(self.d, "patches"); os.makedirs(self.pd)
        for i in (1, 2):
            open(os.path.join(self.pd, f"p{i}.patch"), "w").write(
                f"--- a/f{i}.txt\n+++ b/f{i}.txt\n@@ -1 +1 @@\n-orig{i}\n+PATCHED{i}\n")
        self.n = 0
    def _sh(self, cmd, cwd=None):
        import subprocess
        return subprocess.run(["bash", "-c", cmd], cwd=cwd or self.d, capture_output=True, text=True)
    def _series(self, *names):
        open(os.path.join(self.pd, "series"), "w").write("# test\n" + "\n".join(names) + "\n")
    def _remaining(self, src):
        import re
        m = re.findall(r"^\[(\d+)/(\d+)\]", self._sh("ninja -C out/X -n all", src).stdout, re.M)
        return int(m[-1][1]) if m else 0
    def _stage(self, prev, naive=False):
        """एक stage: pristine src + पिछला out restore, patches, ninja, out + progress.json सहेजना।"""
        import time
        time.sleep(1.1)                                  # असली stages घंटों के अंतर पर होते हैं
        self.n += 1; w = os.path.join(self.d, f"st{self.n}"); os.makedirs(w); src = os.path.join(w, "src")
        self._sh(f"tar -xf src.tar -C {w} && tar -xf out.tar -C {src}")
        pj = os.path.join(w, "patches.json")
        if naive:
            for name in [l.strip() for l in open(os.path.join(self.pd, "series")) if l.strip() and not l.startswith("#")]:
                self._sh(f"patch -p1 --forward --batch -i {self.pd}/{name}", src)
            rc = 0
        else:
            rc = self.P.apply(src, self.pd, prev, pj)
            if rc != 0: return rc, None, None, None, None
        rem = self._remaining(src)
        self._sh("ninja -C out/X all", src)
        self._sh(f"tar --format=posix -C {src} -cf {self.d}/out.tar out/X")
        prog = os.path.join(w, "progress.json")
        pt = json.load(open(pj)) if not naive else {}
        pt.pop("changed", None)
        json.dump({"out_prefix": f"out-s{self.n}", "remaining_edges": 0, "patches": pt}, open(prog, "w"))
        outs = {i: open(os.path.join(src, "out", "X", f"o{i}")).read().strip() for i in (1, 2, 3)}
        return rc, rem, prog, outs, (json.load(open(pj)) if not naive else None)

    def test_multistage_resume_change_and_drop(self):
        self._series("p1.patch")
        rc, rem, prog, outs, pj = self._stage("-")
        self.assertEqual((rc, rem), (0, 3)); self.assertTrue(pj["changed"])
        self.assertEqual(outs, {1: "PATCHED1", 2: "orig2", 3: "orig3"})
        rc, rem, prog, outs, pj = self._stage(prog)                    # वही patches: शून्य rebuild
        self.assertEqual((rc, rem), (0, 0)); self.assertFalse(pj["changed"])
        self.assertEqual(outs[1], "PATCHED1")
        self._series("p2.patch")                                       # p1 हटाया, p2 जोड़ा
        rc, rem, prog, outs, pj = self._stage(prog)
        self.assertEqual((rc, rem), (0, 2)); self.assertTrue(pj["changed"])
        self.assertEqual(outs, {1: "orig1", 2: "PATCHED2", 3: "orig3"})  # हटाए patch का output नहीं बचा
        rc, rem, prog, outs, pj = self._stage(prog)                    # स्थिर: फिर शून्य rebuild
        self.assertEqual((rc, rem), (0, 0)); self.assertEqual(outs[1], "orig1")

    def test_negative_control_naive_patching_keeps_stale_output(self):
        self._series("p1.patch"); self._stage("-", naive=True)
        self._series("p2.patch")
        _, _, _, outs, _ = self._stage("-", naive=True)
        self.assertEqual(outs[1], "PATCHED1")       # यही bug patches.py रोकता है

    def test_old_progress_without_patches_and_empty_series(self):
        os.remove(os.path.join(self.pd, "p1.patch")); os.remove(os.path.join(self.pd, "p2.patch"))
        old = os.path.join(self.d, "old.json"); json.dump({"out_prefix": "out-s0", "remaining_edges": 5}, open(old, "w"))
        self.assertEqual(self.P.series_hash(self.pd, []), "none")
        _, rem, _, _, pj = self._stage(old)
        self.assertFalse(pj["changed"]); self.assertEqual(pj["hash"], "none")

    def test_args_gn_changes_hash_and_bad_patch_fails(self):
        self._series("p1.patch"); h1 = self.P.series_hash(self.pd, ["p1.patch"])
        open(os.path.join(self.pd, "args.gn"), "w").write('chrome_public_manifest_package = "org.example.b"\n')
        self.assertNotEqual(h1, self.P.series_hash(self.pd, ["p1.patch"]))
        open(os.path.join(self.pd, "bad.patch"), "w").write("--- a/f3.txt\n+++ b/f3.txt\n@@ -1 +1 @@\n-nomatch\n+x\n")
        self._series("bad.patch")
        rc, *_ = self._stage("-")
        self.assertEqual(rc, 1)
        self._series("../etc.patch"); rc, *_ = self._stage("-"); self.assertEqual(rc, 1)

    def test_stage_script_wiring(self):
        s = open(os.path.join(self.CI, "chromium_stage.sh")).read()
        for must in ['patches.py" apply src', 'PATCH_CHANGED" = 0', '"patches":pt', 'EXP_PKG', 'BUILD_KEY" > "$PK/DONE"',
                     'SEED_STATE', 'GITHUB_RUN_ID']:
            self.assertIn(must, s)
        self.assertNotIn("state mismatch", s)
