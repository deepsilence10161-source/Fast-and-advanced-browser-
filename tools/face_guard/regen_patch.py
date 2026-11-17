#!/usr/bin/env python3
"""Regenerate patches/personal/0105-face-guard-presence-mode.patch from the repo Java sources.

Pristine inputs come from the verified fixture (tools/personal_browser/face-guard-upstream-155.0.8059.80.json.gz).
The six edits to existing Chromium files are taken from the CURRENT patch (applied to the pristine copies); the new
Java files are always re-read from tools/face_guard. Usage: regen_patch.py [--check]
"""
import gzip, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "patches/personal/0105-face-guard-presence-mode.patch"
J = "chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/"
T = "chrome/browser/tab_ui/android/java/src/org/chromium/chrome/browser/tab_ui/"


def main():
    check = "--check" in sys.argv
    sources = json.loads(gzip.open(ROOT / "tools/personal_browser/face-guard-upstream-155.0.8059.80.json.gz").read())
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / "a", Path(d) / "b"
        for rel, text in sources.items():
            for base in (a, b):
                (base / rel).parent.mkdir(parents=True, exist_ok=True)
                (base / rel).write_text(text)
        # apply the existing patch to b, then drop its new files (they are re-read from the repo)
        subprocess.run(["patch", "-d", str(b), "-p1", "--forward", "--batch", "--no-backup-if-mismatch", "-i", str(PATCH)],
                       check=True, capture_output=True)
        for old in list((b / J).glob("*.java")) if (b / J).exists() else []:
            old.unlink()
        (b / T / "FaceGuardLockState.java").unlink()
        (b / J).mkdir(parents=True, exist_ok=True)
        for src in sorted((ROOT / "tools/face_guard/src/org/chromium/chrome/browser/swiftra/faceguard").glob("*.java")):
            shutil.copy(src, b / J / src.name)
        shutil.copy(ROOT / "tools/face_guard/src_tab_ui/org/chromium/chrome/browser/tab_ui/FaceGuardLockState.java",
                    b / T / "FaceGuardLockState.java")
        r = subprocess.run(["git", "diff", "--no-index", "a", "b"], cwd=d, capture_output=True, text=True)
        out = r.stdout
        out = re.sub(r"^(diff --git )a/a/(.*?) b/b/", r"\1a/\2 b/", out, flags=re.M)
        out = re.sub(r"^diff --git a/b/(.*) b/b/(.*)$", r"diff --git a/\1 b/\2", out, flags=re.M)
        out = re.sub(r"^--- a/a/", "--- a/", out, flags=re.M)
        out = re.sub(r"^\+\+\+ b/b/", "+++ b/", out, flags=re.M)
        if check:
            same = PATCH.read_text() == out
            print("0105 patch is %s" % ("up to date" if same else "STALE: run tools/face_guard/regen_patch.py"))
            return 0 if same else 1
        PATCH.write_text(out)
        print("wrote", PATCH, len(out.splitlines()), "lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
