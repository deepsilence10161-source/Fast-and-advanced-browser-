"""chromium_stage.sh का end-to-end अनुकरण — असली script, नकली (stub) बाहरी दुनिया।

क्यों: दो बार script के ऐसे रास्ते (exit path) विफल हुए जो केवल CI पर चलते थे:
  * b7a2f0d से पहले: build पूरा होने पर grep का exit 1 -> APK खोया (x64 run 38745313869, arm64 run 38750988168)।
  * b7a2f0d: `cd $ROOT` के बाद `stage_lib.sh` का relative path टूटा (x64 run 38837246181)।
यह test workflow जैसा ही चलाता है (`bash scripts/ci/chromium_stage.sh`, repo root से, relative $0) और हर stage
के लिए runner को ephemeral मानता है (ROOT मिटाकर)। stub: gh (local dir = releases), sudo (no-op), zstd (identity),
gn / install-build-deps / apksigner / aapt2 (नकली src में)। ninja असली है।

परिदृश्य: timeout-stage (state सहेजना, अद्वितीय out नाम, पुराना out हटना, पुरानी progress.json संगत) ->
पूरा stage (APK, BUILD_INFO, DONE=build key) -> दोबारा चलाना (already-done) -> branded variant (seed से src/out,
केवल प्रभावित 2 edges, नया package gate पास, baseline अछूता) -> negative (args में package पर patch नहीं: gate FAIL,
APK फिर भी सुरक्षित, DONE नहीं) -> patch हटाना (DONE key बदली, incremental, मूल package वापस)।
"""
import json, os, shutil, stat, subprocess, sys, tempfile, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CI = os.path.join(HERE, "..", "scripts", "ci")
TAG, CPU = "155.0.8059.80", "x64"

GH = r'''#!/usr/bin/env python3
import os, shutil, sys
store = os.environ["GH_STORE"]; a = sys.argv[1:]
assert a[0] == "release", a
sub, tag = a[1], a[2]; d = os.path.join(store, tag); rest = a[3:]
def opt(n):
    return rest[rest.index(n) + 1] if n in rest else None
pos = []; skip = False
for x in rest:
    if skip: skip = False; continue
    if x in ("-R", "-p", "-O", "-t", "-n", "--target", "--json", "-q"): skip = True; continue
    if x.startswith("-"): continue
    pos.append(x)
if sub == "view":
    if not os.path.isdir(d): sys.exit(1)
    if "--json" in rest: print("\n".join(sorted(os.listdir(d))))
elif sub == "create":
    os.makedirs(d, exist_ok=True)
elif sub == "download":
    f = os.path.join(d, opt("-p"))
    if not os.path.isfile(f): sys.exit(1)
    sys.stdout.buffer.write(open(f, "rb").read())
elif sub == "upload":
    for f in pos: shutil.copy(f, os.path.join(d, os.path.basename(f)))
elif sub == "delete-asset":
    os.remove(os.path.join(d, pos[0]))
else:
    sys.exit(2)
'''
NINJA_TMPL = """rule cp
  command = cp $in $out
rule cat
  command = cat $in > $out
build obj/f1.o: cp ../../f1.txt
build obj/f2.o: cp ../../f2.txt
build obj/pkg.o: cp ../../pkg.txt
build apks/ChromePublic.apk: cat obj/f1.o obj/f2.o obj/pkg.o || apks/ChromePublic.apk.extras
build chrome_public_apk: phony apks/ChromePublic.apk
""" + "".join(f"build obj/x{i}.o: cp ../../f1.txt\n" for i in range(60)) + \
    "build apks/ChromePublic.apk.extras: phony " + " ".join(f"obj/x{i}.o" for i in range(60)) + "\n"
# (60 अतिरिक्त edges: watchdog की 50-edge छूट से बड़ा graph)
GN = """#!/bin/bash
[ "$1" = gen ] || exit 2
mkdir -p "$2"; [ -f "$2/build.ninja" ] || cp build_template.ninja "$2/build.ninja"; echo "Done. (stub gn)"
"""
AAPT2 = """#!/bin/bash
[ "$1 $2" = "dump badging" ] || exit 2
p=$(grep -o 'PKG=[a-z.]*' "$3" | head -1 | cut -d= -f2)
echo "package: name='$p' versionCode='1'"; echo "application-label:'stub'"
"""
BRAND_PATCH = "--- a/pkg.txt\n+++ b/pkg.txt\n@@ -1 +1 @@\n-PKG=org.chromium.chrome\n+PKG=org.example.fab\n"


def wexe(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@unittest.skipUnless(shutil.which("ninja") and shutil.which("patch"), "ninja/patch नहीं मिला (pip install ninja)")
class TestStageScriptEndToEnd(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix="stage-e2e-")
        self.store = os.path.join(self.t, "releases"); os.makedirs(self.store)
        self.bin = os.path.join(self.t, "bin")
        wexe(os.path.join(self.bin, "gh"), GH)
        wexe(os.path.join(self.bin, "sudo"), "#!/bin/sh\nexit 0\n")        # runner-तैयारी के sudo कदम no-op
        wexe(os.path.join(self.bin, "zstd"), "#!/bin/sh\nexec cat\n")       # compression = identity
        self.repo = os.path.join(self.t, "repo"); os.makedirs(os.path.join(self.repo, "scripts"))
        shutil.copytree(CI, os.path.join(self.repo, "scripts", "ci"))
        self.series([])
        self.root = os.path.join(self.t, "runner", "cr"); self.pk = os.path.join(self.t, "runner", "pk")
        self.run_id = 1000
        self._seed_baseline_state()

    # ---------- सहायक ----------
    def series(self, names, patches=None, args=None):
        pd = os.path.join(self.repo, "patches"); shutil.rmtree(pd, ignore_errors=True); os.makedirs(pd)
        for n, body in (patches or {}).items(): open(os.path.join(pd, n), "w").write(body)
        open(os.path.join(pd, "series"), "w").write("# e2e\n" + "".join(n + "\n" for n in names))
        if args: open(os.path.join(pd, "args.gn"), "w").write(args)

    def state(self, v): return os.path.join(self.store, f"crstate-{TAG}-{CPU}-{v}")
    def assets(self, v): return sorted(os.listdir(self.state(v))) if os.path.isdir(self.state(v)) else []

    def _seed_baseline_state(self):
        """stage-0 के बाद जैसी a1 state: pristine src pack + out-s0 (gn gen हुआ, कुछ compile नहीं) + पुरानी progress.json।"""
        sr = os.path.join(self.t, "seedroot"); src = os.path.join(sr, "src")
        for n, c in (("f1.txt", "one\n"), ("f2.txt", "two\n"), ("pkg.txt", "PKG=org.chromium.chrome\n")):
            os.makedirs(src, exist_ok=True); open(os.path.join(src, n), "w").write(c)
        open(os.path.join(src, "build_template.ninja"), "w").write(NINJA_TMPL)
        wexe(os.path.join(src, "buildtools", "linux64", "gn"), GN)
        wexe(os.path.join(src, "build", "install-build-deps.sh"), "#!/bin/sh\nexit 0\n")
        bt = os.path.join(src, "third_party", "android_sdk", "public", "build-tools", "99.0.0")
        wexe(os.path.join(bt, "apksigner"), "#!/bin/sh\necho Verifies\nexit 0\n")
        wexe(os.path.join(bt, "aapt2"), AAPT2)
        open(os.path.join(sr, "COMMIT"), "w").write("c0ffee\n"); open(os.path.join(sr, ".gclient"), "w").write("#\n")
        # असली stage-0 जैसा: base args.gn (script के heredoc से, CPU भरकर) + gn gen
        body = open(os.path.join(CI, "chromium_stage.sh")).read().split("ARGS=$(cat <<EOF\n", 1)[1].split("\nEOF\n", 1)[0]
        os.makedirs(os.path.join(src, "out", "x64"), exist_ok=True)
        open(os.path.join(src, "out", "x64", "args.gn"), "w").write(body.replace("$CPU", CPU) + "\n")
        subprocess.run(["bash", "-c", "cd src && buildtools/linux64/gn gen out/x64 >/dev/null"], cwd=sr, check=True)
        d = self.state("a1"); os.makedirs(d)
        sh = lambda c: subprocess.run(["bash", "-c", c], cwd=sr, check=True)
        sh(f"tar --format=posix --exclude=./src/out -cf - ./src ./.gclient ./COMMIT | split -b 1900m -d -a 3 - {d}/src.tar.zst.part")
        sh(f"cd {d} && sha256sum src.tar.zst.part* > src.sha256")
        sh(f"tar --format=posix -C src -cf - out/x64 | split -b 1900m -d -a 3 - {d}/out-s0.tar.zst.part")
        sh(f"cd {d} && sha256sum out-s0.tar.zst.part* > out-s0.sha256")
        json.dump({"tag": TAG, "cpu": CPU, "commit": "c0ffee", "stage": 0, "out_prefix": "out-s0",
                   "remaining_edges": 64, "ninja_rc": 124, "time": 0}, open(os.path.join(d, "progress.json"), "w"))

    def stage(self, stage, variant="a1", seed="", budget=3600):
        """एक stage = एक ephemeral runner: ROOT/PK मिटाकर, workflow जैसा `bash scripts/ci/chromium_stage.sh`।"""
        time.sleep(1.1)
        shutil.rmtree(os.path.join(self.t, "runner"), ignore_errors=True)
        os.makedirs(os.path.join(self.root, "depot_tools"))            # depot_tools clone (network) न हो
        self.run_id += 1
        outd = os.path.join(self.t, f"outputs-{self.run_id}"); go = os.path.join(self.t, f"ghout-{self.run_id}")
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"], GH_STORE=self.store,
                   TAG=TAG, CPU=CPU, STAGE=str(stage), DEADLINE=str(int(time.time()) + budget),
                   STATE=f"crstate-{TAG}-{CPU}-{variant}", SEED_STATE=(f"crstate-{TAG}-{CPU}-{seed}" if seed else ""),
                   OUTPUTS_DIR=outd, GITHUB_OUTPUT=go, GITHUB_REPOSITORY="o/r", GITHUB_RUN_ID=str(self.run_id),
                   GITHUB_RUN_ATTEMPT="1", CR_ROOT=self.root, CR_PK=self.pk, GH_TOKEN="x")
        r = subprocess.run(["bash", "scripts/ci/chromium_stage.sh"], cwd=self.repo, env=env, capture_output=True, text=True, timeout=300)
        ev = open(os.path.join(outd, f"stage-{stage}.txt")).read() if os.path.exists(os.path.join(outd, f"stage-{stage}.txt")) else ""
        done = open(go).read() if os.path.exists(go) else ""
        return r, ev, done

    def kv(self, ev, key):
        for tok in ev.split():
            if tok.startswith(key + "="): return tok.split("=", 1)[1]
        return None

    def apk_pkg(self, v):
        return open(os.path.join(self.state(v), f"ChromePublic-{TAG}-{CPU}.apk")).read().strip().splitlines()[-1]

    # ---------- पूरा परिदृश्य ----------
    def test_full_lifecycle(self):
        # 1) समय-सीमा वाला stage: compile नहीं (budget<=300), state सहेजी, अद्वितीय नाम, पुराना out-s0 हटा
        r, ev, done = self.stage(1, budget=100)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        self.assertIn("done=false", done)
        self.assertEqual(self.kv(ev, "remaining_edges_at_start"), "64")
        a = self.assets("a1")
        self.assertIn("out-s1-r1001-1.sha256", a); self.assertFalse([x for x in a if x.startswith("out-s0")], a)
        prog = json.load(open(os.path.join(self.state("a1"), "progress.json")))
        self.assertEqual((prog["out_prefix"], prog["remaining_edges"], prog["patches"]["hash"]), ("out-s1-r1001-1", 64, "none"))

        # 2) पूरा stage: APK + BUILD_INFO + DONE(build key); watchdog शांत
        r, ev, done = self.stage(2)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        self.assertIn("done=true", done); self.assertIn("status=DONE", ev)
        a = self.assets("a1")
        for must in (f"ChromePublic-{TAG}-{CPU}.apk", "BUILD_INFO.txt", "DONE"): self.assertIn(must, a)
        key_a1 = open(os.path.join(self.state("a1"), "DONE")).read().strip()
        self.assertEqual(key_a1, self.kv(ev, "build_key"))
        self.assertEqual(self.apk_pkg("a1"), "PKG=org.chromium.chrome")
        info = open(os.path.join(self.state("a1"), "BUILD_INFO.txt")).read()
        self.assertIn("package: name='org.chromium.chrome'", info); self.assertIn("patch_hash=none", info)

        # 3) दोबारा चलाना: already-done, कुछ नहीं बदलता
        r, ev, done = self.stage(0)
        self.assertEqual(r.returncode, 0); self.assertIn("status=already-done", ev); self.assertIn("done=true", done)

        # 4) branded variant b1 (seed a1): केवल pkg.o + APK (2 edges), नया package gate पास, a1 अछूता
        self.series(["brand.patch"], {"brand.patch": BRAND_PATCH}, 'chrome_public_manifest_package = "org.example.fab"\n')
        r, ev, done = self.stage(0, variant="b1", seed="a1")
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        self.assertIn(f"src_state=crstate-{TAG}-{CPU}-a1", ev); self.assertIn(f"out_state=crstate-{TAG}-{CPU}-a1", ev)
        self.assertEqual(self.kv(ev, "patch_changed"), "1"); self.assertEqual(self.kv(ev, "args_changed"), "1")
        self.assertEqual(self.kv(ev, "remaining_edges_at_start"), "2")
        self.assertEqual(self.kv(ev, "expected_package"), "org.example.fab")
        self.assertIn("done=true", done)
        self.assertEqual(self.apk_pkg("b1"), "PKG=org.example.fab")
        self.assertFalse([x for x in self.assets("b1") if x.startswith("src.")], "b1 में src की प्रति नहीं होनी चाहिए")
        self.assertEqual(self.apk_pkg("a1"), "PKG=org.chromium.chrome")
        self.assertEqual(open(os.path.join(self.state("a1"), "DONE")).read().strip(), key_a1)

        # 5) negative: args में नया package पर कोई patch नहीं -> gate FAIL, APK फिर भी सुरक्षित, DONE नहीं
        self.series([], args='chrome_public_manifest_package = "org.example.fab"\n')
        r, ev, done = self.stage(0, variant="c1", seed="a1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("अपेक्षित package (org.example.fab) नहीं", r.stdout + r.stderr)
        self.assertIn(f"ChromePublic-{TAG}-{CPU}.apk", self.assets("c1")); self.assertNotIn("DONE", self.assets("c1"))

        # 6) b1 से patch हटाना: DONE key बदली -> incremental (हटाए patch की फ़ाइल touch), मूल package वापस
        self.series([])
        r, ev, done = self.stage(0, variant="b1", seed="a1")
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        self.assertIn("DONE पुरानी key", r.stdout)
        self.assertEqual(self.kv(ev, "patch_changed"), "1"); self.assertEqual(self.kv(ev, "remaining_edges_at_start"), "2")
        self.assertEqual(self.apk_pkg("b1"), "PKG=org.chromium.chrome")
        self.assertEqual(open(os.path.join(self.state("b1"), "DONE")).read().strip(), self.kv(ev, "build_key"))

    def test_watchdog_still_catches_bad_restore(self):
        """patches/args न बदलें और restore के बाद काम बढ़े -> WATCHDOG FAIL (सुरक्षा कमजोर न हो)।"""
        p = os.path.join(self.state("a1"), "progress.json"); d = json.load(open(p)); d["remaining_edges"] = 1
        json.dump(d, open(p, "w"))
        r, ev, done = self.stage(1)
        self.assertEqual(r.returncode, 1); self.assertIn("WATCHDOG FAIL", r.stdout)


if __name__ == "__main__":
    unittest.main()
