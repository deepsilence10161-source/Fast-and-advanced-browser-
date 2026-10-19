#!/usr/bin/env python3
"""E2E gate for the public "swiftra" release: was THIS exact APK tested on a device/emulator, and did it pass?

  e2e_gate.py --dir <downloaded E2E artifact dir> --apk-sha <sha256 of the APK to publish>
PASS only if:
  * the artifact's BUILD_INFO.txt "--- sha256" equals --apk-sha (the tested APK is byte-identical);
  * every marker in REQUIRED printed PASS (scripts/ci/shield_e2e.py, scripts/ci/advanced_e2e.py);
  * no "<NAME>_E2E FAIL" line anywhere (speed/repeat lines are measurements, not gates: MEASURED/PARTIAL allowed);
  * DEVICE_CHECKS reports at least one pass and 0 failures (scripts/ci/device_checks.sh).
"""
import argparse
import glob
import os
import re
import sys

REQUIRED = ["SHIELD_E2E", "DOWNLOAD_SHIELD_E2E", "ADVANCED_E2E", "FINGERPRINT_E2E", "CREDITS_E2E", "ADBLOCK_E2E"]


def tested_sha(d):
    for p in glob.glob(os.path.join(d, "**", "BUILD_INFO.txt"), recursive=True):
        m = re.search(r"^--- sha256\s*\n([0-9a-f]{64})", open(p, encoding="utf-8", errors="replace").read(), re.M)
        if m:
            return m.group(1)
    return None


def gate(d, apk_sha):
    reasons = []
    sha = tested_sha(d)
    if sha != apk_sha:
        reasons.append(f"tested APK sha {str(sha)[:12]} != published {apk_sha[:12]}")
    seen, fails, dev = {}, [], None
    for p in glob.glob(os.path.join(d, "**", "*.txt"), recursive=True) + glob.glob(os.path.join(d, "**", "*.log"), recursive=True):
        for line in open(p, encoding="utf-8", errors="replace"):
            m = re.match(r"^([A-Z_]+_E2E) (PASS|FAIL|NOT_RUN|PARTIAL|MEASURED)\b", line)
            if m:
                seen.setdefault(m.group(1), set()).add(m.group(2))
                if m.group(2) == "FAIL":
                    fails.append(m.group(1))
            m = re.match(r"^DEVICE_CHECKS: (\d+) \S+, (\d+) ", line)
            if m:
                dev = (int(m.group(1)), int(m.group(2)))
    for k in REQUIRED:
        if seen.get(k) != {"PASS"}:
            reasons.append(f"{k}={','.join(sorted(seen.get(k, {'missing'})))}")
    if fails:
        reasons.append("FAIL lines: " + ",".join(sorted(set(fails))))
    if not dev or dev[0] == 0 or dev[1] != 0:
        reasons.append(f"DEVICE_CHECKS={dev}")
    return reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--apk-sha", required=True)
    a = ap.parse_args()
    r = gate(a.dir, a.apk_sha)
    print("E2E_GATE " + ("PASS" if not r else "FAIL " + " | ".join(r)))
    return 0 if not r else 1


if __name__ == "__main__":
    sys.exit(main())
