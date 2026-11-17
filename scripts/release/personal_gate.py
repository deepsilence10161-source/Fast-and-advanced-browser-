#!/usr/bin/env python3
"""Dedicated gate for the personal DEVELOPMENT pre-release (never the ordinary Swiftra release).

It refuses to publish a personal APK unless recorded evidence matches the exact APK bytes:
  * BUILD_INFO says personal_source_only=1 and signer == expected;
  * an evidence JSON lists this cpu with the SAME apk_sha256, FAIL == 0 and PASS > 0;
  * if the build contains Face Guard (0105), a Face Guard APK evidence for the same sha256 must exist
    with FAIL == 0 and the camera scenarios x64 'one' and 'two' PASS (ARM64 Redroid has no camera: NOT_RUN is
    allowed there and is never reported as PASS);
  * if the build contains the omnibox clipboard fix (0109), `clipboard_apk.<cpu>` evidence for the same sha256 with
    K01-K04 all PASS must exist;
  * if the build contains the sign-in message layer (0107) nothing extra is required (static message only).
Passing this gate is NOT a privacy certification. Usage:
  personal_gate.py --cpu x64 --build-info BUILD_INFO-x64.txt --apk-sha <sha256> --evidence a.json [b.json ...]
"""
import argparse
import json
import re
import sys


def _flags(info):
    return {
        "personal": any(v.strip() == "1" for v in re.findall(r"^personal_source_only[ \t]*=[ \t]*(.*)$", info, re.M)),
        "face_guard": bool(re.search(r"^0105-face-guard-presence-mode\.patch\s*$", info, re.M)),
        "omnibox_clipboard": bool(re.search(r"^0109-personal-omnibox-clipboard\.patch\s*$", info, re.M)),
    }


def gate(cpu, info, apk_sha, evidences):
    reasons = []
    f = _flags(info)
    if not f["personal"]:
        reasons.append("not_a_personal_build")
    s = re.search(r"signer_cert_sha256=([0-9a-f]+)", info)
    e = re.search(r"expected_cert_sha256=([0-9a-f]+)", info)
    if not s or not e or s.group(1) != e.group(1):
        reasons.append("signer_mismatch_or_missing")
    ok = False
    for ev in evidences:
        row = ev.get(cpu)
        if isinstance(row, dict) and row.get("apk_sha256") == apk_sha and "face_guard_scenarios" not in row:
            summ = row.get("summary", {})
            if summ.get("FAIL", 1) == 0 and summ.get("PASS", 0) > 0:
                ok = True
    if not ok:
        reasons.append("no_e2e_evidence_for_this_apk_sha256")
    if f["face_guard"]:
        fg = False
        for ev in evidences:
            row = (ev.get("face_guard_apk") or {}).get(cpu)
            if not isinstance(row, dict) or row.get("apk_sha256") != apk_sha:
                continue
            summ = row.get("summary", {})
            if summ.get("FAIL", 1) != 0:
                continue
            sc = row.get("scenarios", {})
            if cpu == "x64" and not (sc.get("one") == "PASS" and sc.get("two") == "PASS" and sc.get("nofaces") == "PASS"):
                continue
            if cpu != "x64" and sc.get("nofaces") != "PASS":
                continue
            fg = True
        if not fg:
            reasons.append("face_guard_in_build_but_no_apk_evidence_for_this_sha256")
    if f["omnibox_clipboard"]:
        cl = False
        for ev in evidences:
            row = (ev.get("clipboard_apk") or {}).get(cpu)
            if isinstance(row, dict) and row.get("apk_sha256") == apk_sha and row.get("K03_urlbar_copy") == "PASS" \
                    and row.get("K01_web_copy") == "PASS" and row.get("K02_web_paste") == "PASS" \
                    and row.get("K04_find_in_page_copy") == "PASS":
                cl = True
        if not cl:
            reasons.append("omnibox_clipboard_fix_in_build_but_no_K01_K02_K03_K04_PASS_for_this_sha256")
    return reasons


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", required=True)
    ap.add_argument("--build-info", required=True)
    ap.add_argument("--apk-sha", required=True)
    ap.add_argument("--evidence", nargs="+", required=True)
    a = ap.parse_args(argv)
    info = open(a.build_info, encoding="utf-8").read()
    evs = [json.load(open(p, encoding="utf-8")) for p in a.evidence]
    reasons = gate(a.cpu, info, a.apk_sha, evs)
    if reasons:
        print("PERSONAL GATE REFUSED:", ", ".join(reasons), file=sys.stderr)
        return 1
    print("personal gate: evidence matches this APK (development pre-release only; NOT a privacy certification)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
