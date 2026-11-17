#!/usr/bin/env python3
"""Evaluate scripts/ci/face_guard_probe.sh output. Expectations are fixed by the three committed AI-generated
fixture images: no_face -> 0 faces, one_face -> 1, two_faces -> 2, for ALL four frame rotations.
Prints `FACE_PROBE_CHECK <image> PASS|FAIL <detail>`; exit 1 on any FAIL, 2 when the probe did not finish.
Device-level analyzer evidence only (no camera, no APK); three images are NOT a calibration or accuracy claim."""
import re
import sys

EXPECT = {"no_face.jpg": 0, "one_face.jpg": 1, "two_faces.jpg": 2}


def evaluate(text):
    if "FACE_PROBE_DONE" not in text:
        return None
    got = {}
    for m in re.finditer(r"^FACE_PROBE (\S+) rot=(\d+) faces=(\d+)\s*$", text, re.M):
        got.setdefault(m.group(1), {})[int(m.group(2))] = int(m.group(3))
    rows = []
    for name, want in EXPECT.items():
        counts = got.get(name, {})
        ok = sorted(counts) == [0, 90, 180, 270] and all(v == want for v in counts.values())
        rows.append((name, ok, f"expected {want} at every rotation, got {dict(sorted(counts.items()))}"))
    return rows


def main(argv):
    rows = evaluate(open(argv[1], encoding="utf-8", errors="replace").read())
    if rows is None:
        print("FACE_PROBE_CHECK NOT_RUN probe did not finish")
        return 2
    bad = 0
    for name, ok, detail in rows:
        print(f"FACE_PROBE_CHECK {name} {'PASS' if ok else 'FAIL'} {detail}")
        bad += 0 if ok else 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
