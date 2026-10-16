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


class TestCertDigests(unittest.TestCase):
    """stage_lib.sh::cert_digests — apksigner के दोनों असली output formats (b1 run 38892991040 का bug:
    build-tools 37 "V2 Signer: certificate …" format न पहचानने से release gate "?" पर FAIL)।"""
    LIB = os.path.join(os.path.dirname(__file__), "..", "scripts", "ci", "stage_lib.sh")
    A = "32a2fc74d731105859e5a85df16d95f102d85b22099b8064c5d8915c61dad1e0"
    B = "029de0fab8f35ee0990ced814d38ab47d6a1be9bc49ffea9bbf4dc190010fe06"
    def _run(self, text):
        import subprocess
        f = os.path.join(tempfile.mkdtemp(), "v.txt"); open(f, "w").write(text)
        r = subprocess.run(["bash", "-c", f'set -euo pipefail; source "{self.LIB}"; X=$(cert_digests "{f}"); echo "R=$X"'],
                           capture_output=True, text=True)
        return r.returncode, r.stdout.strip()
    def test_build_tools_37_format_from_real_evidence(self):     # evidence/source-build-x64-ui-run-38865720986
        t = ("Verifies\nVerified using v2 scheme (APK Signature Scheme v2): true\nNumber of signers: 1\n"
             "V2 Signer: certificate DN: CN=Unknown\nV2 Signer: certificate SHA-256 digest: " + self.A + "\n"
             "V2 Signer: certificate SHA-1 digest: 33b28eafdf43dea4ff5dc3dbd9e5a523f67f6bb1\n")
        self.assertEqual(self._run(t), (0, "R=" + self.A))
    def test_build_tools_36_format_from_real_local_run(self):   # स्थानीय apksigner 36, Swiftra keystore
        t = "Verifies\nSigner #1 certificate DN: CN=Swiftra, O=Swiftra, C=IN\nSigner #1 certificate SHA-256 digest: " + self.B + "\n"
        self.assertEqual(self._run(t), (0, "R=" + self.B))
    def test_v2_and_v3_same_signer_dedup_and_uppercase(self):
        t = f"V2 Signer: certificate SHA-256 digest: {self.B.upper()}\nV3 Signer: certificate SHA-256 digest: {self.B}\n"
        self.assertEqual(self._run(t), (0, "R=" + self.B))
    def test_two_different_signers_never_match_single_expected(self):
        t = f"V3 Signer: certificate SHA-256 digest: {self.A}\nV3.1 Signer: certificate SHA-256 digest: {self.B}\n"
        rc, out = self._run(t); self.assertEqual(rc, 0); self.assertNotIn(out, ("R=" + self.A, "R=" + self.B))
    def test_no_match_or_missing_file_is_empty_not_abort(self):
        self.assertEqual(self._run("ERROR: JAR signer CERT.RSA: ...\n"), (0, "R="))
        import subprocess
        r = subprocess.run(["bash", "-c", f'set -euo pipefail; source "{self.LIB}"; X=$(cert_digests /nonexistent); echo "R=$X"'],
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "R="))
    def test_public_key_digest_lines_are_ignored(self):
        t = f"V2 Signer: public key SHA-256 digest: {self.A}\nV2 Signer: certificate SHA-256 digest: {self.B}\n"
        self.assertEqual(self._run(t), (0, "R=" + self.B))


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

    def _overlay(self, rel, data):
        fp = os.path.join(self.pd, "overlay", rel); os.makedirs(os.path.dirname(fp), exist_ok=True)
        open(fp, "wb").write(data)

    def test_overlay_multistage_change_and_drop(self):
        """overlay (binary icon जैसा): लगे, स्थिर रहे (शून्य rebuild), हटाने पर मूल लौटे — और patch के साथ मिल सके।"""
        import shutil
        self._series("p1.patch")
        h_patch_only = self.P.series_hash(self.pd, ["p1.patch"])
        self._overlay("f3.txt", b"OVERLAY3\n")
        self.assertNotEqual(h_patch_only, self.P.series_hash(self.pd, ["p1.patch"]))
        rc, rem, prog, outs, pj = self._stage("-")
        self.assertEqual((rc, rem), (0, 3)); self.assertEqual(pj["overlay"], ["f3.txt"])
        self.assertEqual(outs, {1: "PATCHED1", 2: "orig2", 3: "OVERLAY3"})
        self.assertIn("f3.txt", pj["files"])
        rc, rem, prog, outs, pj = self._stage(prog)                    # वही: शून्य rebuild
        self.assertEqual((rc, rem), (0, 0)); self.assertFalse(pj["changed"]); self.assertEqual(outs[3], "OVERLAY3")
        self._overlay("f3.txt", b"OVERLAY3-v2\n")   # hash बदला -> सभी patched/overlay फ़ाइलें नए epoch पर (o1,o3), o2 नहीं
        rc, rem, prog, outs, pj = self._stage(prog)
        self.assertEqual((rc, rem), (0, 2)); self.assertEqual(outs[3], "OVERLAY3-v2")
        shutil.rmtree(os.path.join(self.pd, "overlay"))                # overlay हटाया -> मूल लौटे
        self.assertEqual(self.P.series_hash(self.pd, ["p1.patch"]), h_patch_only)   # पुराना सूत्र अपरिवर्तित
        rc, rem, prog, outs, pj = self._stage(prog)                    # हटाई overlay फ़ाइल भी touch -> मूल लौटा
        self.assertEqual((rc, rem), (0, 2)); self.assertEqual(outs, {1: "PATCHED1", 2: "orig2", 3: "orig3"})
        rc, rem, prog, outs, pj = self._stage(prog)                    # फिर स्थिर
        self.assertEqual((rc, rem), (0, 0))

    def test_overlay_errors_and_empty(self):
        self._series()
        os.makedirs(os.path.join(self.pd, "overlay"))
        self.assertEqual(self.P.series_hash(self.pd, []), "none")      # खाली overlay = baseline
        self._overlay("nope/new.txt", b"x")                            # लक्ष्य src में नहीं -> त्रुटि
        rc, *_ = self._stage("-"); self.assertEqual(rc, 1)
        os.remove(os.path.join(self.pd, "overlay", "nope", "new.txt"))
        os.symlink("/etc/passwd", os.path.join(self.pd, "overlay", "f2.txt"))   # symlink -> त्रुटि
        rc, *_ = self._stage("-"); self.assertEqual(rc, 1)

    def test_repo_overlay_targets_are_known_chromium_icons(self):
        """repo के असली overlay: केवल res_chromium_base के ज्ञात icon resources, सही pixel आकार।"""
        sys.path.insert(0, self.CI); import patches
        pd = os.path.join(os.path.dirname(__file__), "..", "patches")
        ov = patches.overlay_files(pd)
        if not ov: self.skipTest("कोई overlay नहीं")
        base = "chrome/android/java/res_chromium_base/"
        size = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
        try:
            from PIL import Image
        except ImportError:
            Image = None
        for rel in ov:
            self.assertTrue(rel.startswith(base), rel)
            leaf = rel[len(base):]
            if leaf == "drawable/themed_app_icon.xml":
                import xml.dom.minidom as M; d = M.parse(os.path.join(pd, "overlay", rel))
                self.assertEqual(d.documentElement.getAttribute("android:viewportWidth"), "90"); continue
            dens, name = leaf.split("/")
            self.assertIn(name, ("app_icon.png", "layered_app_icon.png", "layered_app_icon_background.png"))
            f = size[dens.replace("mipmap-", "")]
            if Image:
                w = Image.open(os.path.join(pd, "overlay", rel)).size
                self.assertEqual(w, ((round(48 * f),) * 2) if name == "app_icon.png" else ((round(108 * f),) * 2), rel)

    def test_stage_script_wiring(self):
        s = open(os.path.join(self.CI, "chromium_stage.sh")).read()
        f = open(os.path.join(self.CI, "finalize_apk.sh")).read()
        for must in ['patches.py" apply src', 'PATCH_CHANGED" = 0', '"patches":pt', 'EXP_PKG', 'SEED_STATE', 'GITHUB_RUN_ID',
                     'finalize.env', 'exec bash "$CI_DIR/finalize_apk.sh"', 'out sign true']:
            self.assertIn(must, s)
        self.assertNotIn("state mismatch", s)
        self.assertNotIn("SIGNING_KS", s)                      # build step कभी secrets न छुए
        for must in ['BUILD_KEY" > "$PK/DONE"', 'EXP_CERT', '--alignment-preserved true', 'file:$KSD/kpass', 'rm -rf "$KSD"']:
            self.assertIn(must, f)
        self.assertNotIn("pass:", f)                           # password कभी argv में नहीं
        # workflow: secrets केवल sign step के env में; build step में नहीं
        import yaml
        wf = yaml.safe_load(open(os.path.join(self.CI, "..", "..", ".github", "workflows", "chromium-stage.yml")))
        steps = wf["jobs"]["stage"]["steps"]
        build = [x for x in steps if x.get("id") == "s"][0]; sign = [x for x in steps if x.get("id") == "sign"][0]
        self.assertFalse(any("secrets." in str(v) for v in build.get("env", {}).values()))
        self.assertIn("secrets.SWIFTRA_KS_B64", sign["env"]["SIGNING_KS_B64"])
        self.assertEqual(sign["if"], "steps.s.outputs.sign == 'true'")
        self.assertIn("steps.sign.outputs.done", wf["jobs"]["stage"]["outputs"]["done"])
        caller = yaml.safe_load(open(os.path.join(self.CI, "..", "..", ".github", "workflows", "chromium-source-build.yml")))
        self.assertTrue(all(j.get("secrets") == "inherit" for j in caller["jobs"].values()))
