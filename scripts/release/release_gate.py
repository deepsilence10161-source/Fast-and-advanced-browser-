#!/usr/bin/env python3
"""Gate for the public "swiftra" release: may this APK be published as the latest Swiftra?

  release_gate.py --apk A.apk --build-info BUILD_INFO.txt --abi arm64|x64
Checks: BUILD_INFO lists every patch in release/required_patches.txt; package com.swiftra.app; apk_audit 7/7
(signer cert == patches/signing_cert_sha256.txt, not debuggable, allowBackup=false, v2+v3, no new exported entry
points, no Google/Chrome logo images). Prints GATE PASS|FAIL <reasons>; exit 0 only on PASS.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def required():
    p = os.path.join(ROOT, "release", "required_patches.txt")
    return [l.strip() for l in open(p) if l.strip() and not l.startswith("#")]


def build_patches(text):
    m = re.search(r"^--- patches\n(.*?)(?:^---|\Z)", text, re.S | re.M)
    body = m.group(1) if m else ""
    return [l.strip() for l in body.splitlines() if re.match(r"^\d{4}-", l.strip())]


def gate(apk, build_info, abi, run_audit=True):
    reasons = []
    text = open(build_info, encoding="utf-8", errors="replace").read()
    have = build_patches(text)
    missing = [p for p in required() if p not in have]
    if missing:
        reasons.append("missing patches: " + ",".join(missing))
    if "com.swiftra.app" not in text:
        reasons.append("BUILD_INFO package is not com.swiftra.app")
    if abi == "arm64" and "arm64" not in text:
        reasons.append("BUILD_INFO is not an arm64 build")
    if run_audit:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "security", "apk_audit.py"), "--apk", apk],
                           capture_output=True, text=True)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        if r.returncode != 0 or not last.startswith("APK_AUDIT PASS"):
            reasons.append("apk_audit: " + last)
    return reasons, have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apk", required=True)
    ap.add_argument("--build-info", required=True)
    ap.add_argument("--abi", required=True, choices=["arm64", "x64"])
    a = ap.parse_args()
    reasons, have = gate(a.apk, a.build_info, a.abi)
    print(f"patches in build: {len(have)}")
    print("GATE " + ("PASS" if not reasons else "FAIL " + " | ".join(reasons)))
    return 0 if not reasons else 1


if __name__ == "__main__":
    sys.exit(main())
