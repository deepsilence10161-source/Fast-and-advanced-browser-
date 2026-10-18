#!/usr/bin/env python3
"""Swiftra Speed Pack (patches/0016-swiftra-speedpack.py): which field trials may be active on the device.

chrome://version/?show-variations-cmd prints the active trials as --force-fieldtrials=Study/Group/... .
  * no "field-trial-config" variations source         -> "no_testing_config" (builds before 0016)
  * testing config active, every upstream study seen is in the pack -> "speedpack_only"
  * an upstream testing-config study outside the pack is active      -> "unexpected_studies" (FAIL)
Trials that Chromium code creates on the client (not in the upstream testing config) are reported, not failed.
"""
import importlib.util
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCH = os.path.join(ROOT, "patches", "0016-swiftra-speedpack.py")
UPSTREAM = os.path.join(ROOT, "tools", "speedpack", "upstream_android_studies_155.0.8059.80.txt")


def load_pack():
    spec = importlib.util.spec_from_file_location("swiftra_speedpack", PATCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pack_studies():
    mod = load_pack()
    return set(mod.ALLOW) | set(mod.SWIFTRA)


def upstream_studies():
    with open(UPSTREAM, encoding="utf-8") as f:
        return {ln.strip() for ln in f if ln.strip() and not ln.startswith("#")}


def parse_force_fieldtrials(cmd):
    """'--force-fieldtrials=*A/G1/B/G2/' -> {'A': 'G1', 'B': 'G2'} (a leading '*' marks an activated trial)."""
    m = re.search(r"--force-fieldtrials=(\S*)", cmd or "")
    if not m:
        return {}
    parts = [p for p in m.group(1).strip('"').split("/")]
    out = {}
    for i in range(0, len(parts) - 1, 2):
        study = parts[i].lstrip("*")
        if study:
            out[study] = parts[i + 1]
    return out


def verdict(source, cmd):
    trials = parse_force_fieldtrials(cmd)
    if "field-trial-config" not in (source or ""):
        return {"verdict": "no_testing_config", "trials": len(trials)}
    pack, upstream = pack_studies(), upstream_studies()
    unexpected = sorted(s for s in trials if s in upstream and s not in pack)
    active_pack = sorted(s for s in trials if s in pack)
    client = sorted(s for s in trials if s not in upstream and s not in pack)
    return {"verdict": "unexpected_studies" if unexpected else ("speedpack_only" if active_pack else "pack_not_seen"),
            "unexpected": unexpected, "pack_active": len(active_pack), "pack_total": len(pack),
            "missing_from_pack": sorted(pack - set(trials))[:40], "client_side_trials": client[:40],
            "swiftra_parallel_download": trials.get("SwiftraParallelDownloading")}
