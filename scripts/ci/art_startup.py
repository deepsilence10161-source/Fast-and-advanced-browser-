#!/usr/bin/env python3
"""How much of Swiftra's cold start is Java running un-compiled? (speed work: measure before building)

A sideloaded APK (adb / GitHub release) is installed by ART with the `verify` filter: Java runs in the interpreter
and JIT until background dexopt (idle + charging) compiles hot methods. Play Store installs get cloud / baseline
profiles and so start compiled. Chromium @155 still declares `enable_baseline_profiles` (build/config/android/
config.gni, default false) and ships build/android/gyp/binary_baseline_profile.py, but no GN template calls it any
more. Before wiring a baseline profile in, this script measures the possible gain on the device.

Same APK, same device, three ART states (`cmd package compile`, no APK change):
  1. install  : `--reset` (install state, normally `verify`)
  2. profile  : `-m speed-profile -f` with the JIT profile collected during step 1 (ART is told to save it with SIGUSR1)
  3. speed    : `-m speed -f` (all methods AOT; the upper bound)
Every state: N cold launches (`am force-stop`, `am start -W` -> TotalTime), median reported, plus the dexopt
`status=` read from dumpsys as proof that the state really changed. At the end the package is reset again.
Prints ART_STARTUP MEASURED|PARTIAL|NOT_RUN and never fails the job (diagnostic).
"""
import argparse
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shield_e2e import adb  # noqa: E402
from startup_netlog import close_all_tabs, resolve_launcher  # noqa: E402

STATES = [("install", ["--reset"]), ("profile", ["-m", "speed-profile", "-f"]), ("speed", ["-m", "speed", "-f"])]
TOTAL_RX = re.compile(r"TotalTime: (\d+)")
STATUS_RX = re.compile(r"status=([A-Za-z-]+)")


def parse_total(text):
    m = TOTAL_RX.search(text or "")
    return int(m.group(1)) if m else None


def parse_status(text):
    """Dexopt filters from `dumpsys package <pkg>` (Android 9-13 and the Android 14 ART service both print status=)."""
    return sorted(set(STATUS_RX.findall(text or "")))


def median(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 1) if xs else None


def dexopt_status(pkg):
    out = adb("shell", "dumpsys", "package", pkg, timeout=60)
    i = out.find("Dexopt state")
    return parse_status(out[i:i + 4000] if i >= 0 else "")


def pid_of(pkg):
    return (adb("shell", "pidof", pkg) or "").split()[:1]


def save_profile(pkg):
    """SIGUSR1 makes ART write the current JIT profile now (instead of waiting for the profile saver)."""
    pid = pid_of(pkg)
    if not pid:
        return False
    for cmd in (["shell", "kill", "-s", "SIGUSR1", pid[0]], ["shell", "su", "0", "kill", "-s", "SIGUSR1", pid[0]]):
        adb(*cmd)
    time.sleep(3)
    return True


def cold_launch(pkg, comp, settle):
    adb("shell", "am", "force-stop", pkg)
    time.sleep(2)
    out = adb("shell", "am", "start", "-W", "-n", comp, timeout=60)
    time.sleep(settle)
    return parse_total(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--devtools", default="http://127.0.0.1:9222")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--settle", type=int, default=6)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pkg, res = a.package, {"package": a.package, "runs": a.runs, "states": {}}
    comp = resolve_launcher(pkg)
    res["component"] = comp
    if not comp:
        print("ART_STARTUP NOT_RUN no launcher activity")
        json.dump(res, open(os.path.join(a.out, "art_startup.json"), "w"), indent=1)
        return 0
    try:
        res["tabs_closed"] = close_all_tabs(a.devtools)     # cold start shows the NTP only, no restored test page
    except Exception as e:                                   # noqa: BLE001
        res["tabs_closed"] = f"error {e}"
    try:
        for name, args in STATES:
            t0 = time.time()
            out = adb("shell", "cmd", "package", "compile", *args, pkg, timeout=900)
            st = res["states"][name] = {"compile_cmd": " ".join(args), "compile_out": (out or "").strip()[-200:],
                                        "compile_s": round(time.time() - t0, 1), "status": dexopt_status(pkg)}
            times = []
            for i in range(a.runs):
                times.append(cold_launch(pkg, comp, a.settle))
                if name == "install":
                    save_profile(pkg)                        # build up the JIT profile that `speed-profile` uses
            st["total_ms"], st["median_ms"] = times, median(times)
            print(f"art startup {name}: status={st['status']} compile {st['compile_s']} s, TotalTime {times}"
                  f" median {st['median_ms']}")
            json.dump(res, open(os.path.join(a.out, "art_startup.json"), "w"), indent=1)
    finally:
        adb("shell", "am", "force-stop", pkg)
        adb("shell", "cmd", "package", "compile", "--reset", pkg, timeout=300)
    m = {k: v.get("median_ms") for k, v in res["states"].items()}
    base = m.get("install")
    res["gain_vs_install_pct"] = {k: round(100.0 * (base - v) / base, 1) for k, v in m.items()
                                  if base and v is not None and k != "install"}
    json.dump(res, open(os.path.join(a.out, "art_startup.json"), "w"), indent=1)
    changed = len({tuple(v.get("status") or []) for v in res["states"].values()}) > 1
    full = all(m.get(k) is not None for k, _ in STATES)
    verdict = "MEASURED" if full and changed else ("PARTIAL" if any(v is not None for v in m.values()) else "NOT_RUN")
    print(f"ART_STARTUP {verdict} medians_ms={m} gain_vs_install_pct={res['gain_vs_install_pct']}"
          f" status_changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
