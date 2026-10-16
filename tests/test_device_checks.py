"""device_checks.sh को नकली adb (PATH stub) के साथ चलाना: अच्छे device पर सब PASS, ख़राब पर सही जाँच FAIL।"""
import json, os, subprocess, sys, tempfile, textwrap, unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
import scroll_jank  # noqa: E402

ADB = textwrap.dedent(r'''#!/bin/bash
    M=$(cat "$STUB_DIR/mode"); a="$*"
    case "$a" in
      shell\ getprop\ ro.product.cpu.abi) echo arm64-v8a;;
      shell\ getprop\ ro.build.version.release) echo 14;;
      "shell pm list packages com.swiftra.app") echo package:com.swiftra.app;;
      shell\ cmd\ package\ resolve-activity*) echo priority=0; echo com.swiftra.app/com.google.android.apps.chrome.Main;;
      shell\ uiautomator\ dump*) :;;
      pull\ *) printf '<node text="Swiftra" />' > "${@: -1}";;
      exec-out\ screencap*) printf PNG;;
      shell\ dumpsys\ package*) echo "flags=[ HAS_CODE ALLOW_CLEAR_USER_DATA ]"; echo "signatures=PackageSignatures{x version:3, signatures:[$(cat "$STUB_DIR/sig")], past signatures:[]}";;
      shell\ run-as*) echo "run-as: package not debuggable: com.swiftra.app";;
      install\ -r\ *foreign*)
        if [ "$M" = good ]; then echo "Performing Streamed Install"; echo "adb: failed to install x: Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package com.swiftra.app signatures do not match newer version; ignoring!]"; echo
        else echo "Performing Streamed Install"; echo Success; echo 0bad > "$STUB_DIR/sig"; fi;;
      install\ *) echo "Performing Streamed Install"; echo Success;;
      uninstall\ *) echo Success;;
      shell\ pidof*) echo 4242;;
      logcat\ *) :;;
      *) :;;
    esac
''')


class DeviceChecks(unittest.TestCase):
    def run_mode(self, mode):
        d = tempfile.mkdtemp(); stub = os.path.join(d, "bin"); os.makedirs(stub)
        open(os.path.join(stub, "adb"), "w").write(ADB); os.chmod(os.path.join(stub, "adb"), 0o755)
        open(os.path.join(d, "mode"), "w").write(mode); open(os.path.join(d, "sig"), "w").write("a1b2c3")
        fake_sj = os.path.join(stub, "fake_sj"); open(fake_sj, "w").write(
            "#!/bin/bash\n" + ('echo OK \'{"scroll_events": 40}\' \'{"frames": 120}\'' if mode == "good" else "echo 'BAD {}'") + "\n")
        os.chmod(fake_sj, 0o755)
        work = os.path.join(d, "w"); os.makedirs(os.path.join(work, "out", "T")); os.symlink(os.path.join(ROOT, "scripts"), os.path.join(work, "scripts"))
        open(os.path.join(work, "out", "T", "BUILD_INFO.txt"), "w").write(
            "package: name='com.swiftra.app' versionCode='1'\napplication-label:'Swiftra'\ndebuggable_apks = false\n")
        for f in ("app.apk", "foreign.apk"): open(os.path.join(work, f), "w").write("x")
        env = dict(os.environ, PATH=stub + ":" + os.environ["PATH"], STUB_DIR=d, DC_SCROLL_CMD=fake_sj)
        p = subprocess.run(["bash", os.path.join(ROOT, "scripts/ci/device_checks.sh"), "T", "app.apk", "foreign.apk"],
                           cwd=work, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = json.load(open(os.path.join(work, "out", "T", "device_checks.json")))
        return {r["check"][:2]: r["status"] for r in rows}, open(os.path.join(work, "out", "T", "device_checks_install.log")).read()

    def test_good_device_all_pass_even_with_trailing_blank_line(self):
        st, log = self.run_mode("good")
        self.assertEqual(st, {f"{i:02d}": "PASS" for i in range(1, 10)}, st)
        self.assertIn("=== 06:", log); self.assertIn("INSTALL_FAILED_UPDATE_INCOMPATIBLE", log)

    def test_bad_device_fails_update_protection_and_scroll(self):
        st, _ = self.run_mode("bad")
        self.assertEqual(st["06"], "FAIL"); self.assertEqual(st["07"], "FAIL"); self.assertEqual(st["05"], "PASS")


class ScrollAnalyse(unittest.TestCase):
    def test_smooth_60hz(self):
        fr = [i * 16.67 for i in range(200)]; m = scroll_jank.analyse(fr, [10, 3000])
        self.assertEqual(m["janky_frames"], 0); self.assertAlmostEqual(m["fps"], 60, delta=1)

    def test_janky_frames_counted(self):
        fr, t = [], 0.0
        for i in range(200):
            t += 50 if i % 10 == 0 else 16.67; fr.append(t)
        m = scroll_jank.analyse(fr, [fr[0], fr[-1]])
        self.assertEqual(m["janky_frames"], 19); self.assertGreater(m["p99_ms"], 40)

    def test_no_scroll_returns_none(self):
        self.assertIsNone(scroll_jank.analyse([1, 2, 3], []))


if __name__ == "__main__":
    unittest.main()
