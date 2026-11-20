#!/usr/bin/env python3
"""PERF_COMPARE: cold start and memory of two installed browsers measured the same way on the same emulator.

Per package: N cold starts (force-stop, then `am start -W` VIEW https://example.org/ with --disable-fre) -> TotalTime;
then after 20 s the summed PSS of every process of the package (dumpsys meminfo). Report only; never gates.
x64 emulator only: absolute numbers say nothing about a real phone.
"""
import argparse
import json
import re
import statistics
import subprocess
import sys
import time

CMD = "/data/local/tmp/chrome-command-line"


def adb(*a, timeout=60):
    try:
        return subprocess.run(["adb", *a], capture_output=True, text=True, timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        return ""


def pss_sum(pkg):
    out = adb("shell", "dumpsys", "meminfo", timeout=90)
    m = re.search(r"Total PSS by process:(.*?)\n\n", out, re.S)
    tot, n = 0, 0
    for line in (m.group(1) if m else "").splitlines():
        mm = re.match(r"\s*([\d,]+)K: (\S+)", line)
        if mm and mm.group(2).startswith(pkg):
            tot += int(mm.group(1).replace(",", ""))
            n += 1
    return tot, n


def measure(pkg, runs):
    adb("shell", "am", "set-debug-app", "--persistent", pkg)
    adb("shell", f"echo '_ --disable-fre' > {CMD} && chmod 644 {CMD}")
    times = []
    for i in range(runs):
        adb("shell", "am", "force-stop", pkg)
        time.sleep(3)
        o = adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", "https://example.org/", "-p", pkg, timeout=90)
        m = re.search(r"TotalTime:\s*(\d+)", o)
        if m:
            times.append(int(m.group(1)))
        time.sleep(6)
    adb("shell", "am", "force-stop", pkg)
    time.sleep(3)
    adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", "https://example.org/", "-p", pkg, timeout=90)
    time.sleep(20)
    pss, procs = pss_sum(pkg)
    ver = re.search(r"versionName=(\S+)", adb("shell", "dumpsys", "package", pkg))
    adb("shell", "am", "force-stop", pkg)
    adb("shell", "rm", "-f", CMD)
    adb("shell", "am", "clear-debug-app")
    return {"package": pkg, "version": ver.group(1) if ver else None, "cold_start_ms": times,
            "median_ms": statistics.median(times) if times else None, "pss_kb_sum": pss, "processes": procs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packages", nargs="+", required=True)
    ap.add_argument("--runs", type=int, default=7)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    adb("root"); time.sleep(3); adb("wait-for-device")
    res = []
    for pkg in a.packages:
        r = measure(pkg, a.runs)
        res.append(r)
        print("PERF_COMPARE", json.dumps(r), flush=True)
    json.dump(res, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
