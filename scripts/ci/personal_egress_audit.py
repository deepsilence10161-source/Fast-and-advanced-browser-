#!/usr/bin/env python3
"""PERSONAL_EGRESS: which hosts does the personal build contact on its own, and while browsing a neutral site?

Reuses the NetLog machinery of startup_netlog.py (Chromium --log-net-log from process start, debug-app command-line
file, read back through adb root). Three captures, each a fresh process:

  idle    cold start, 40 s idle                                   -> the browser's OWN traffic with nothing open
  browse  VIEW https://example.org/ then https://example.com/     -> only those hosts (+ nothing else) are expected
  search  WEB_SEARCH intent with a dummy query                    -> shows WHICH search engine gets typed text

Report only. No verdict gates a release: this MEASURES (hosts/requests, Google vs non-Google). It does not see
non-Chromium traffic (Java HttpURLConnection, Android system services, the keyboard) - stated in the output.
Never logs in anywhere; nothing here uses a real account.
"""
import argparse
import gzip
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import startup_netlog as sn  # noqa: E402
from shield_e2e import adb  # noqa: E402

BROWSE = ["https://example.org/", "https://example.com/"]
SEARCH_QUERY = "swiftra_egress_audit_query"


def host_of(k):
    return sn.re.sub(r"^\S+ \w+://([^/:]+).*$", r"\1", k).lower()


def view(pkg, url):
    adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", url, "-p", pkg, timeout=60)


def capture(pkg, name, actions, duration, out):
    netlog = f"/data/user/0/{pkg}/cache/swiftra_egress_{name}.jsonl"
    adb("shell", "rm", "-f", netlog)
    adb("shell", "am", "force-stop", pkg)
    if adb("shell", "settings", "get", "global", "adb_enabled").strip() != "1":
        adb("shell", "settings", "put", "global", "adb_enabled", "1")
    adb("shell", "am", "set-debug-app", "--persistent", pkg)
    flags = f"_ --log-net-log={netlog} --net-log-file-format=ndjson --net-log-duration={duration}"
    adb("shell", f"echo '{flags}' > {sn.CMDLINE_FILE} && chmod 644 {sn.CMDLINE_FILE}")
    t0 = time.time()
    try:
        actions()
        time.sleep(max(0, duration + 8 - (time.time() - t0)))
    finally:
        adb("shell", "rm", "-f", sn.CMDLINE_FILE)
        adb("shell", "am", "clear-debug-app")
    raw, how = sn.read_app_file(netlog)
    r = {"phase": name, "read_via": how, "captured": False}
    if not raw:
        return r
    with gzip.open(os.path.join(out, f"netlog_{name}.jsonl.gz"), "wb") as f:
        f.write(raw)
    consts, events = sn.load_netlog(raw.decode("utf-8", "replace"))
    s = sn.summarize(consts, events)
    r.update(captured=s["events"] > 0, events=s["events"])
    r["requests"] = s["requests"]
    r["google_requests"] = s["google_requests"]
    r["non_google_requests"] = s["non_google_requests"]
    r["google_resolves"] = s["google_resolves"]
    r["google_connect_hosts"] = s["google_connect_hosts"]
    r["resolves"] = sorted(s["resolves"])
    r["sb_hosts"] = s["sb_hosts"]
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pkg = a.package
    comp = sn.resolve_launcher(pkg)
    res = {"package": pkg, "launcher": comp, "phases": {}}

    def idle():
        adb("shell", "am", "start", "-W", "-n", comp, timeout=60)
        time.sleep(40)

    def browse():
        for u in BROWSE:
            view(pkg, u)
            time.sleep(15)

    def search():
        adb("shell", "am", "start", "-W", "-a", "android.intent.action.WEB_SEARCH", "-e", "query", SEARCH_QUERY,
            "-p", pkg, timeout=60)
        time.sleep(15)

    for name, fn, dur in (("idle", idle, 55), ("browse", browse, 50), ("search", search, 35)):
        r = capture(pkg, name, fn, dur, a.out)
        res["phases"][name] = r
        print(f"PERSONAL_EGRESS phase={name} captured={r['captured']} events={r.get('events')} "
              f"google_requests={len(r.get('google_requests', {}))} google_resolves={r.get('google_resolves')} "
              f"sb={r.get('sb_hosts')}")
        for k in sorted(r.get("requests", {}))[:60]:
            print(f"  {name} request {k}")
    # verdicts that are MEASUREMENTS, not gates
    idle_r = res["phases"]["idle"]
    brw = res["phases"]["browse"]
    allowed = {"example.org", "example.com"}
    extra = sorted({host_of(k) for k in brw.get("requests", {})} - allowed - {"127.0.0.1", "localhost"})
    res["summary"] = {
        "idle_google_requests": len(idle_r.get("google_requests", {})),
        "idle_google_hosts": sorted(set(idle_r.get("google_resolves", [])) | set(idle_r.get("google_connect_hosts", []))),
        "browse_other_hosts": extra,
        "browse_google_requests": len(brw.get("google_requests", {})),
        "search_hosts": sorted({host_of(k) for k in res["phases"]["search"].get("requests", {})}),
        "note": "NetLog sees only Chromium's network stack: not Java HttpURLConnection, Android services or the keyboard.",
    }
    json.dump(res, open(os.path.join(a.out, "personal_egress.json"), "w"), indent=1, ensure_ascii=False)
    print("PERSONAL_EGRESS summary", json.dumps(res["summary"], ensure_ascii=False))
    ok = all(res["phases"][p]["captured"] for p in res["phases"])
    print("PERSONAL_EGRESS", "MEASURED" if ok else "NOT_CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
