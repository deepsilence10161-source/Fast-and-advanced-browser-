#!/usr/bin/env python3
"""A/B on ONE device: new APK vs baseline APK, alternated (new, base, new, base).

Why: runner-to-runner noise. Two separate runs compare two machines. Here both APKs run on the same Redroid in the
same job, so a few-percent effect (arm64 PGO + orderfile vs the preserved 0011 build) is measurable.

Every round: `adb install -r -d <apk>` (keeps the profile, so no first-run flow; both are signed with the same
Swiftra key), the sha256 of the installed base.apk read back from the device (proof which build ran), one cold
launch not counted, `--runs` cold launches (am start -W TotalTime), a verified restart with the speed_e2e command
line, `--bench` rounds of tools/speedpack/bench.js (5 runs each) and `--loads` page loads of the speed_e2e page.
ART state is the install state for both (fresh install each round).
Prints AB_BENCH MEASURED|PARTIAL|NOT_RUN and never fails the job (diagnostic).
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speed_e2e as S  # noqa: E402
from shield_e2e import adb  # noqa: E402
from startup_netlog import CMDLINE_FILE, resolve_launcher  # noqa: E402

ORDER = ("new", "base", "new", "base")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def device_sha(pkg):
    path = ""
    for ln in (adb("shell", "pm", "path", pkg, timeout=30) or "").splitlines():
        if ln.startswith("package:") and ln.strip().endswith("base.apk"):
            path = ln.strip()[len("package:"):]
    if not path:
        return None
    out = adb("shell", "sha256sum", path, timeout=120) or adb("shell", "su", "0", "sha256sum", path, timeout=120)
    m = re.match(r"([0-9a-f]{64})", (out or "").strip())
    return m.group(1) if m else None


def cold_starts(pkg, comp, n):
    out = []
    for _ in range(n):
        adb("shell", "am", "force-stop", pkg)
        time.sleep(2)
        r = adb("shell", "am", "start", "-W", "-n", comp, timeout=60)
        m = re.search(r"TotalTime: (\d+)", r or "")
        out.append(int(m.group(1)) if m else None)
        time.sleep(5)
    return out


def ratio(x, y):
    return round(x / y, 3) if x and y else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--base-label", default="baseline")
    ap.add_argument("--out", required=True)
    ap.add_argument("--socket", default=os.environ.get("SOCK", "chrome_devtools_remote"))
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--bench", type=int, default=2)
    ap.add_argument("--loads", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pkg = a.package
    apks = {"new": a.new, "base": a.base}
    res = {"package": pkg, "order": ORDER, "base_label": a.base_label,
           "apk_sha256": {k: sha256_file(v) for k, v in apks.items()}, "rounds": []}
    if res["apk_sha256"]["new"] == res["apk_sha256"]["base"]:
        print("AB_BENCH NOT_RUN new and base APK are identical")
        json.dump(res, open(os.path.join(a.out, "ab_bench.json"), "w"), indent=1)
        return 0
    S.DL_DATA = b"\0" * (1024 * 1024)      # the download parts of speed_e2e are not used here
    S.build_assets()
    S.start_server(tempfile.mkdtemp())
    adb("reverse", f"tcp:{S.PORT}", f"tcp:{S.PORT}")
    try:
        for i, which in enumerate(ORDER):
            rnd = {"round": i, "apk": which}
            res["rounds"].append(rnd)
            try:
                adb("shell", "am", "force-stop", pkg)
                inst = adb("install", "-r", "-d", apks[which], timeout=600)
                rnd["install"] = (inst or "").strip().splitlines()[-1:] or [""]
                rnd["device_sha256"] = device_sha(pkg)
                rnd["installed_ok"] = rnd["device_sha256"] == res["apk_sha256"][which]
                comp = resolve_launcher(pkg)
                adb("shell", "am", "set-debug-app", "--persistent", pkg)
                cold_starts(pkg, comp, 1)                          # first launch after install: not counted
                rnd["cold_ms"] = cold_starts(pkg, comp, a.runs)
                st = S.restart(pkg, comp, "swiftra", a.socket)
                rnd["flags_applied"] = st["flags_applied"]
                if st["flags_applied"]:
                    S.load_page(f"aw{i}")                          # warm-up, not counted
                    rnd["loads"] = [(S.load_page(f"a{i}l{k}") or {}).get("page") for k in range(a.loads)]
                    rnd["bench"] = [(S.run_bench(f"a{i}b{k}") or {}).get("result") for k in range(a.bench)]
            except Exception as e:  # noqa: BLE001 - keep the other rounds
                rnd["error"] = f"{type(e).__name__}: {e}"[:300]
            print(f"ab round {i} {which}: sha_ok={rnd.get('installed_ok')} cold={rnd.get('cold_ms')} "
                  f"bench={[b and b.get('total') for b in rnd.get('bench') or []]} "
                  f"load={[p and p.get('load') for p in rnd.get('loads') or []]}", flush=True)
            json.dump(res, open(os.path.join(a.out, "ab_bench.json"), "w"), indent=1)
    finally:
        adb("shell", "rm", "-f", CMDLINE_FILE)
        adb("shell", "am", "clear-debug-app")
        adb("shell", "am", "force-stop", pkg)
        adb("install", "-r", "-d", apks["new"], timeout=600)      # leave the new build installed for later steps
    summ = {}
    for which in ("new", "base"):
        rs = [r for r in res["rounds"] if r["apk"] == which and r.get("installed_ok")]
        benches = [b for r in rs for b in (r.get("bench") or []) if b]
        summ[which] = {"rounds_ok": len(rs),
                       "cold_ms": S.med([x for r in rs for x in r.get("cold_ms") or []]),
                       "bench_ms": S.med([b["total"] for b in benches]), "bench_n": len(benches),
                       "bench_parts": {k: S.med([b["ms"].get(k) for b in benches])
                                       for k in (benches[0]["ms"] if benches else {})},
                       "load_ms": S.med([p["load"] for r in rs for p in r.get("loads") or [] if p]),
                       "lcp_ms": S.med([p["lcp"] for r in rs for p in r.get("loads") or [] if p])}
    n, b = summ["new"], summ["base"]
    summ["base_over_new"] = {k: ratio(b.get(k), n.get(k)) for k in ("cold_ms", "bench_ms", "load_ms", "lcp_ms")}
    summ["parts_base_over_new"] = {k: ratio(b["bench_parts"].get(k), n["bench_parts"].get(k))
                                   for k in n["bench_parts"]}
    res["summary"] = summ
    json.dump(res, open(os.path.join(a.out, "ab_bench.json"), "w"), indent=1)
    full = n["rounds_ok"] == 2 and b["rounds_ok"] == 2 and n["bench_n"] and b["bench_n"]
    verdict = "MEASURED" if full else ("PARTIAL" if n["rounds_ok"] or b["rounds_ok"] else "NOT_RUN")
    print("ab summary:", json.dumps(summ, ensure_ascii=False))
    print(f"AB_BENCH {verdict} base={a.base_label} bench_ms new {n['bench_ms']} base {b['bench_ms']} "
          f"cold_ms new {n['cold_ms']} base {b['cold_ms']} load_ms new {n['load_ms']} base {b['load_ms']} "
          f"base_over_new {summ['base_over_new']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
