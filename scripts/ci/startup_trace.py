#!/usr/bin/env python3
"""Where does Swiftra's cold start spend its time? (speed work: measure before optimising)

Chromium's own startup tracing, switched on from process start through the debug-app command line (same mechanism
as startup_netlog.py; nothing in the APK changes):
  --trace-startup=<categories> --trace-startup-duration=N --trace-startup-file=<app cache> --trace-startup-format=json
(components/tracing/common/tracing_switches.cc @155: default format is proto, default duration 5 s).

Scenario: close all tabs -> force-stop -> cold launch (am start -W) -> trace for N s -> read the file (root).
Output: startup_trace.json (summary) + startup_trace.json.gz (raw trace, opens in ui.perfetto.dev / chrome://tracing).
Summary per thread of the browser process: top-level slices (sum + count), inclusive slices, and milestones.
This is a diagnostic: it prints STARTUP_TRACE CAPTURED|NOT_CAPTURED and never fails the job.
"""
import argparse
import collections
import gzip
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shield_e2e import adb, internal_text, open_internal  # noqa: E402
from startup_netlog import CMDLINE_FILE, CMDLINE_JS, close_all_tabs, read_app_file, resolve_launcher  # noqa: E402

TRACE_NAME = "swiftra_startup_trace.json"
CATEGORIES = "startup,toplevel,browser,content,loading,navigation,Java,android,ui,v8,base,sql,net,gpu,viz,blink"
MILESTONE_RX = re.compile(r"(?i)(onCreate|onStart|onResume|LibraryLoader|BrowserMain|PreMainMessageLoop|"
                          r"PostCreateThreads|FirstDraw|first_paint|FirstContentful|NewTabPage|Ntp|"
                          r"ProfileManager|CreateProfile|TabModel|restoreTabs|Startup\.|ChromeTabbedActivity|"
                          r"ProcessInitializationHandler|SafeBrowsing|Variations|FieldTrial|ComponentUpdater|"
                          r"Subresource|Ruleset)")


def parse_trace(raw):
    """JSON trace (object with traceEvents, or a bare array; tolerant of a missing closing bracket)."""
    text = raw.decode("utf-8", "replace").strip()
    for cand in (text, text.rstrip(",") + "]}", text.rstrip(",") + "]"):
        try:
            o = json.loads(cand)
            return o.get("traceEvents", []) if isinstance(o, dict) else o
        except ValueError:
            continue
    return []


def summarize(events, top=25):
    procs, threads = {}, {}
    for e in events:
        if e.get("ph") == "M" and e.get("name") == "process_name":
            procs[e.get("pid")] = (e.get("args") or {}).get("name", "")
        if e.get("ph") == "M" and e.get("name") == "thread_name":
            threads[(e.get("pid"), e.get("tid"))] = (e.get("args") or {}).get("name", "")
    # complete slices: ph X, plus B/E pairs per thread
    slices, stacks = [], collections.defaultdict(list)
    for e in sorted((e for e in events if e.get("ph") in ("X", "B", "E") and "ts" in e), key=lambda e: e["ts"]):
        key = (e.get("pid"), e.get("tid"))
        if e["ph"] == "X" and isinstance(e.get("dur"), (int, float)):
            slices.append((key, e["ts"], e["dur"], e.get("name", "?"), e.get("cat", "")))
        elif e["ph"] == "B":
            stacks[key].append(e)
        elif e["ph"] == "E" and stacks[key]:
            b = stacks[key].pop()
            slices.append((key, b["ts"], e["ts"] - b["ts"], b.get("name", "?"), b.get("cat", "")))
    if not slices:
        return {"slices": 0}
    t0 = min(s[1] for s in slices)
    browser = [p for p, n in procs.items() if n in ("Browser", "")] or []
    # the browser process: the one owning CrBrowserMain
    for (pid, tid), n in threads.items():
        if n == "CrBrowserMain":
            browser = [pid]
    out = {"slices": len(slices), "span_ms": round((max(s[1] + s[2] for s in slices) - t0) / 1000, 1),
           "processes": {str(k): v for k, v in procs.items()}, "threads": {}}
    by_thread = collections.defaultdict(list)
    for s in slices:
        by_thread[s[0]].append(s)
    for key, ss in by_thread.items():
        name = threads.get(key, str(key[1]))
        if key[0] not in browser and name not in ("CrRendererMain", "VizCompositorThread", "CrGpuMain"):
            continue
        ss.sort(key=lambda s: (s[1], -s[2]))
        top_level, end = [], -1
        for s in ss:
            if s[1] >= end:
                top_level.append(s)
                end = s[1] + s[2]
        tl, incl = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
        for s in top_level:
            tl[s[3]][0] += s[2]
            tl[s[3]][1] += 1
        for s in ss:
            incl[s[3]][0] += s[2]
            incl[s[3]][1] += 1
        # self time = duration minus direct children (slices are well nested per thread)
        self_t, stack = collections.defaultdict(lambda: [0, 0]), []
        for s in ss:
            while stack and s[1] >= stack[-1][1] + stack[-1][2]:
                stack.pop()
            if stack:
                self_t[stack[-1][3]][0] -= min(s[2], stack[-1][1] + stack[-1][2] - s[1])
            self_t[s[3]][0] += s[2]
            self_t[s[3]][1] += 1
            stack.append(s)
        busy = sum(s[2] for s in top_level)
        label = f"{procs.get(key[0], key[0])}/{name}"
        out["threads"][label] = {
            "busy_ms": round(busy / 1000, 1), "slices": len(ss),
            "top_level": [[n, round(v[0] / 1000, 1), v[1]] for n, v in sorted(tl.items(), key=lambda kv: -kv[1][0])[:top]],
            "inclusive": [[n, round(v[0] / 1000, 1), v[1]] for n, v in sorted(incl.items(), key=lambda kv: -kv[1][0])[:top]],
            "self": [[n, round(v[0] / 1000, 1), v[1]] for n, v in sorted(self_t.items(), key=lambda kv: -kv[1][0])[:top]],
            "milestones": [[n, round((ts - t0) / 1000, 1), round(d / 1000, 1)]
                           for (_, ts, d, n, _c) in ss if MILESTONE_RX.search(n)][:60],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--devtools", default="http://127.0.0.1:9222")
    ap.add_argument("--duration", type=int, default=10)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pkg = a.package
    path = f"/data/user/0/{pkg}/cache/{TRACE_NAME}"
    res = {"package": pkg, "categories": CATEGORIES, "duration_s": a.duration,
           "scenario": "close all tabs -> cold start (am start -W) -> trace N s -> read file"}
    comp = resolve_launcher(pkg)
    res["tabs_closed"] = close_all_tabs(a.devtools)
    time.sleep(4)
    adb("shell", "am", "force-stop", pkg)
    adb("shell", "rm", "-f", path)
    adb("shell", "su", "0", "rm", "-f", path)
    adb("shell", "am", "set-debug-app", "--persistent", pkg)
    flags = (f"_ --trace-startup={CATEGORIES} --trace-startup-duration={a.duration} "
             f"--trace-startup-file={path} --trace-startup-format=json")
    adb("shell", f"echo '{flags}' > {CMDLINE_FILE} && chmod 644 {CMDLINE_FILE}")
    try:
        am = adb("shell", "am", "start", "-W", "-n", comp, timeout=60) if comp else ""
        res["am_start"] = {k: int(v) for k, v in re.findall(r"(TotalTime|WaitTime): (\d+)", am or "")}
        time.sleep(a.duration + 8)
        open_internal(a.devtools, "chrome://version/")
        time.sleep(3)
        cl = internal_text(a.devtools, "chrome://version", CMDLINE_JS) or ""
        res["flags_applied"] = "--trace-startup" in cl
    finally:
        adb("shell", "rm", "-f", CMDLINE_FILE)
        adb("shell", "am", "clear-debug-app")
    raw, how = read_app_file(path)
    res["read_via"] = how
    if not raw:
        res["captured"] = False
        json.dump(res, open(os.path.join(a.out, "startup_trace.json"), "w"), indent=1)
        print("startup trace:", res)
        print("STARTUP_TRACE NOT_CAPTURED")
        return 0
    with gzip.open(os.path.join(a.out, "startup_trace.json.gz"), "wb") as f:
        f.write(raw)
    events = parse_trace(raw)
    res.update({"bytes": len(raw), "events": len(events), "summary": summarize(events)})
    res["captured"] = bool(res["summary"].get("slices"))
    json.dump(res, open(os.path.join(a.out, "startup_trace.json"), "w"), indent=1, ensure_ascii=False)
    print("startup trace:", json.dumps({k: v for k, v in res.items() if k != "summary"}, ensure_ascii=False))
    for label, t in res["summary"].get("threads", {}).items():
        print(f"== {label}: busy {t['busy_ms']} ms, {t['slices']} slices")
        print("   top-level:", json.dumps(t["top_level"][:10], ensure_ascii=False)[:1200])
        print("   self:", json.dumps(t["self"][:20], ensure_ascii=False)[:2000])
        print("   milestones:", json.dumps(t["milestones"][:25], ensure_ascii=False)[:1800])
    print("STARTUP_TRACE", "CAPTURED" if res["captured"] else "NOT_CAPTURED",
          f"span_ms={res['summary'].get('span_ms')} am_start={res.get('am_start')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
