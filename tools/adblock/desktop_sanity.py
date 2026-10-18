#!/usr/bin/env python3
"""Desktop-component check of the Swiftra ruleset with the *real* Chromium matcher (not a reimplementation).

Uses the E2E harness itself (scripts/ci/advanced_e2e.py: same page, servers, host mapping and verdict) against a
desktop Chromium build in two modes:
  baseline : clean profile, no ruleset                      -> expected verdict no_blocker
  ruleset  : our unindexed ruleset pre-placed as the installed "Subresource Filter Rules" component in the profile,
             activation forced to all sites through the SubresourceFilter field-trial params
             (activation_scope=all_sites, activation_state=enabled; subresource_filter_features.cc)
                                                            -> expected verdict blocked
This proves the ruleset file format and the rules; the APK path (bundled resource, preset, no component download)
is proven only by the device E2E.
Usage: desktop_sanity.py --chrome <binary> --ruleset <unindexed.pb> --out <json>
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "ci"))
import advanced_e2e as E  # noqa: E402

PORT = 9333


def prepare_profile(ruleset):
    ud = tempfile.mkdtemp(prefix="sw-ab-")
    if ruleset:
        d = os.path.join(ud, "Subresource Filter", "Unindexed Rules", "9.99.0")
        os.makedirs(d)
        shutil.copy(ruleset, os.path.join(d, "Filtering Rules"))
        open(os.path.join(d, "LICENSE"), "w").write("EasyList/EasyPrivacy CC BY-SA 3.0; AdAway hosts CC BY 3.0\n")
        json.dump({"manifest_version": 2, "name": "Subresource Filter Rules", "version": "9.99.0",
                   "ruleset_format": 1}, open(os.path.join(d, "manifest.json"), "w"))
    return ud


def run(chrome, ruleset):
    ud = prepare_profile(ruleset)
    flags = [chrome, "--headless=new", "--no-sandbox", f"--user-data-dir={ud}", f"--remote-debugging-port={PORT}",
             f"--host-resolver-rules={E.RULES}", "--ignore-certificate-errors", "--no-first-run",
             "--remote-allow-origins=*", "about:blank"]
    if ruleset:
        flags[1:1] = ["--enable-features=SubresourceFilter:activation_scope/all_sites/activation_state/enabled/"
                      "activation_priority/900"]
    p = subprocess.Popen(flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = {"ruleset": bool(ruleset), "attempts": []}
    try:
        E.DEVTOOLS = f"http://127.0.0.1:{PORT}"
        time.sleep(4)
        for attempt in range(4):
            since = len(E.HITS)
            url = f"https://{E.AD_TOP}/ads.html?a={attempt}"
            E.open_internal(E.DEVTOOLS, url)
            r = E.eval_on(url.split("//")[1], E.FP_RESULT_JS, wait=30, until=lambda x: x.get("title") == "AD:done")
            time.sleep(1)
            hits = E.ad_hits(since)
            v = E.ad_verdict(hits, r)
            out["attempts"].append({"attempt": attempt, "verdict": v, "hits": hits, "page": (r or {}).get("r", "")})
            if v in ("blocked", "controls_broken") or (not ruleset and v != "no_result"):
                break
            time.sleep(8)
        idx = os.path.join(ud, "Subresource Filter", "Indexed Rules")
        out["indexed_dirs"] = sorted(os.listdir(idx)) if os.path.isdir(idx) else []
        out["verdict"] = out["attempts"][-1]["verdict"]
    finally:
        p.terminate()
        p.wait(timeout=20)
        shutil.rmtree(ud, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome", required=True)
    ap.add_argument("--ruleset", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    E.start_servers(tempfile.mkdtemp())
    res = {"chrome": subprocess.run([a.chrome, "--version"], capture_output=True, text=True).stdout.strip(),
           "baseline": run(a.chrome, None), "with_ruleset": run(a.chrome, a.ruleset)}
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps({"baseline": res["baseline"]["verdict"], "with_ruleset": res["with_ruleset"]["verdict"],
                      "indexed": res["with_ruleset"]["indexed_dirs"]}))


if __name__ == "__main__":
    main()
