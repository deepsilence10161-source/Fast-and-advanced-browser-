#!/usr/bin/env python3
"""Compare two speed_e2e.json files (baseline APK vs new APK, same device type), e.g. arm64 non-PGO vs PGO.

  python3 tools/speedpack/compare_runs.py BASE.json NEW.json [--mode swiftra]

Prints per-metric medians and the ratio base/new (>1 = new is faster), with the min-max spread of every
individual measurement so noise is visible. Nothing is claimed when either side has no data, and a ratio
inside the spread of both sides is marked "within noise".
"""
import argparse
import json
import statistics


def bench_values(res, mode):
    out = {}
    for c in res.get("cycles", []):
        b = ((c.get(mode) or {}).get("bench") or {}).get("result")
        if not b:
            continue
        out.setdefault("total", []).append(b["total"])
        for k, v in b["ms"].items():
            out.setdefault(k, []).append(v)
    return out


def page_values(res, mode):
    out = {"load_ms": [], "lcp_ms": [], "download_s": []}
    for c in res.get("cycles", []):
        m = c.get(mode) or {}
        for x in m.get("loads", []):
            p = x.get("page") or {}
            if p.get("load"):
                out["load_ms"].append(p["load"])
            if p.get("lcp"):
                out["lcp_ms"].append(p["lcp"])
        d = ((m.get("download") or {}).get("server") or {})
        if d.get("complete"):
            out["download_s"].append(d["seconds"])
    return out


def compare(base, new):
    rows = []
    for k in sorted(set(base) | set(new), key=lambda k: (k != "total", k)):
        a, b = base.get(k) or [], new.get(k) or []
        if not a or not b:
            rows.append({"metric": k, "base": None, "new": None, "ratio": None, "note": "no data"})
            continue
        ma, mb = statistics.median(a), statistics.median(b)
        ratio = round(ma / mb, 3) if mb else None
        overlap = max(min(a), min(b)) <= min(max(a), max(b))
        rows.append({"metric": k, "base": round(ma, 1), "new": round(mb, 1), "ratio": ratio,
                     "base_range": [min(a), max(a)], "new_range": [min(b), max(b)], "n": [len(a), len(b)],
                     "note": "within noise" if overlap else ("new faster" if ratio and ratio > 1 else "new slower")})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("--mode", default="swiftra")
    a = ap.parse_args()
    base, new = json.load(open(a.base)), json.load(open(a.new))
    out = {"mode": a.mode,
           "bench": compare(bench_values(base, a.mode), bench_values(new, a.mode)),
           "page": compare(page_values(base, a.mode), page_values(new, a.mode))}
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
