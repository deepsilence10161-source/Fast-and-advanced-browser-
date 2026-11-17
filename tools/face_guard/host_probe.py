#!/usr/bin/env python3
"""Compile + run FaceGuardPolicy host tests (pure Java, JDK only, no Android/camera/model).
Host JVM only: this is NOT Android PASS and says nothing about camera, model accuracy or UI."""
import pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src/org/chromium/chrome/browser/swiftra/faceguard/FaceGuardPolicy.java"
TEST = ROOT / "test/FaceGuardPolicyTest.java"


def run(policy_source: pathlib.Path = SRC):
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d)
        c = subprocess.run(["javac", "-Xlint:all", "-Werror", "-d", str(out), str(policy_source), str(TEST)],
                           capture_output=True, text=True)
        if c.returncode:
            return 2, c.stdout + c.stderr
        r = subprocess.run(["java", "-cp", str(out), "FaceGuardPolicyTest"], capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout + r.stderr


if __name__ == "__main__":
    rc, out = run()
    print(out.strip())
    sys.exit(rc)
