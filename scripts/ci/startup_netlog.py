#!/usr/bin/env python3
"""c2d: what does Swiftra contact on its own, from a cold start?

The CDP trace in shield_e2e.py starts after the browser is already running, so it cannot see startup traffic.
Here Chromium's own NetLog is switched on from process start:

  * base/android/.../CommandLineInitUtil.java reads /data/local/tmp/chrome-command-line when the package is the
    "debug app" (adb enabled) - `am set-debug-app --persistent <pkg>`; nothing in the APK changes.
  * content/browser/network_service_instance_impl.cc opens --log-net-log=<path> before the first request;
    --net-log-duration=N stops and flushes the file cleanly after N seconds; --net-log-file-format=ndjson
    gives one JSON object per line (robust to truncation).

Scenario (default Safe Browsing mode is whatever the device is in; run_capture.sh runs this after shield_e2e.py,
which restores Standard protection): force-stop -> cold launch -> idle -> open the New Tab Page -> idle.
Only the browser's own traffic is in the window (no test page is opened).

Verdict: FAIL only if a Safe Browsing endpoint is contacted (request, DNS or connection). Everything else is
reported (Google requests/resolves/connections), so privacy work can be targeted with evidence.
"""
import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shield_e2e import HOST_RX, SB_HOSTS, adb, browser_ws, internal_text, is_google, open_internal, targets  # noqa: E402

CMDLINE_FILE = "/data/local/tmp/chrome-command-line"
NETLOG_NAME = "swiftra_startup_netlog.jsonl"
CONNECT_HINTS = ("STREAM_JOB", "QUIC_SESSION", "CONNECT_JOB", "SOCKET_POOL", "HTTP_STREAM_POOL",
                 "PRECONNECT", "SSL_CONNECT", "TCP_CONNECT", "HTTP2_SESSION")
GROUP_RX = re.compile(r'"(?:group_id|group_name|host|server|destination)":\s*"(?:[a-z]+/)*(?:[a-z]+://)?([A-Za-z0-9.-]+)')
HOSTPORT_RX = re.compile(r"^(?:[a-z]+://)?\[?([A-Za-z0-9.:-]+?)\]?(?::\d+)?/?$")


def norm_host(v):
    m = HOSTPORT_RX.match(str(v).strip().lower())
    return (m.group(1) if m else str(v)).rstrip(".")


def load_netlog(text):
    """Parse ndjson (or json) NetLog text, tolerating a truncated tail. Returns (constants, events)."""
    consts, events = None, []
    dec = json.JSONDecoder()
    head = text.lstrip()
    if head.startswith('{"constants":'):
        try:
            i = len('{"constants":')
            while head[i:i + 1].isspace():
                i += 1
            consts, _ = dec.raw_decode(head, i)
        except ValueError:
            consts = None
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line or line in ("[", "]", "]}", "}"):
            continue
        if line.startswith('"events": ['):
            line = line[len('"events": ['):].strip()
            if not line:
                continue
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict):
            continue
        if "constants" in o and isinstance(o["constants"], dict):
            consts = o["constants"]
        if "type" in o and "source" in o:
            events.append(o)
        if isinstance(o.get("events"), list):
            events.extend(e for e in o["events"] if isinstance(e, dict))
    return consts or {}, events


def summarize(consts, events):
    names = {v: k for k, v in (consts.get("logEventTypes") or {}).items()}
    requests, resolves, connects, preconnects, google_types = {}, {}, {}, {}, {}
    ips = set()
    for ev in events:
        name = names.get(ev.get("type"), str(ev.get("type")))
        params = ev.get("params") if isinstance(ev.get("params"), dict) else {}
        blob = json.dumps(params)
        if name == "URL_REQUEST_START_JOB" and isinstance(params.get("url"), str):
            k = f"{params.get('method', '?')} {params['url'].split('?')[0][:160]}"
            requests[k] = requests.get(k, 0) + 1
        if name.startswith("HOST_RESOLVER") and isinstance(params.get("host"), str):
            h = norm_host(params["host"])
            resolves[h] = resolves.get(h, 0) + 1
        evh = set()
        if any(x in name for x in CONNECT_HINTS):
            for a1, a2 in HOST_RX.findall(blob):
                evh.add((a1 or a2).lower().rstrip("."))
            for g in GROUP_RX.findall(blob):
                evh.add(g.lower().rstrip("."))
            for h in evh:
                connects[h] = connects.get(h, 0) + 1
            if params.get("is_preconnect") or "PRECONNECT" in name:
                for h in evh:
                    preconnects[h] = preconnects.get(h, 0) + 1
            for ip in re.findall(r'"(?:address|remote_address|peer_address)":\s*"([0-9a-fA-F.:\[\]]+)"', blob):
                ips.add(ip)
            for lst in (params.get("address_list") or []) if isinstance(params.get("address_list"), list) else []:
                ips.add(str(lst))
        if any(is_google(h) for h in evh | {norm_host(params.get("host", ""))}):
            google_types[name] = google_types.get(name, 0) + 1

    def host_of(k):
        return re.sub(r"^\S+ \w+://([^/:]+).*$", r"\1", k).lower()

    loop = ("127.0.0.1", "localhost", "::1")
    contacted = set(map(host_of, requests)) | set(resolves) | set(connects)
    sb = sorted(h for h in contacted if h in SB_HOSTS)
    return {
        "events": len(events), "event_type_table": bool(names),
        "requests": dict(sorted(requests.items())[:300]),
        "google_requests": {k: c for k, c in requests.items() if is_google(host_of(k))},
        "non_google_requests": {k: c for k, c in requests.items()
                                if not is_google(host_of(k)) and host_of(k) not in loop},
        "resolves": resolves, "google_resolves": sorted(h for h in resolves if is_google(h)),
        "connect_hosts": dict(sorted(connects.items())[:200]),
        "google_connect_hosts": sorted(h for h in connects if is_google(h)),
        "preconnect_hosts": preconnects, "google_event_types": google_types,
        "remote_ips": sorted(i for i in ips if i not in loop)[:100],
        "sb_hosts": sb,
    }


def resolve_launcher(package):
    out = adb("shell", "cmd", "package", "resolve-activity", "--brief", "-c", "android.intent.category.LAUNCHER",
              package, timeout=20)
    comps = [l.strip() for l in out.splitlines() if "/" in l]
    return comps[-1] if comps else None


def read_app_file(path):
    """Non-debuggable app: its private dir needs root. Redroid is root; the google_apis emulator allows su/adb root."""
    for cmd in (["exec-out", "cat", path], ["exec-out", "su", "0", "cat", path]):
        r = subprocess.run(["adb", *cmd], capture_output=True, timeout=60)
        if r.returncode == 0 and r.stdout and not r.stdout.startswith(b"cat:") and b"Permission denied" not in r.stdout[:200]:
            return r.stdout, " ".join(cmd[:3])
    subprocess.run(["adb", "root"], capture_output=True, timeout=30)
    time.sleep(3)
    subprocess.run(["adb", "wait-for-device"], capture_output=True, timeout=60)
    r = subprocess.run(["adb", "exec-out", "cat", path], capture_output=True, timeout=60)
    if r.returncode == 0 and r.stdout and not r.stdout.startswith(b"cat:"):
        return r.stdout, "adb root"
    return None, (r.stdout or r.stderr)[:200].decode("utf-8", "replace")


def close_all_tabs(devtools):
    """So the cold start restores no test page: only the browser's own traffic is in the window."""
    import websocket
    ws_url = browser_ws(devtools)
    pages = [t["id"] for t in targets(devtools) if t.get("type") == "page"]
    if not ws_url or not pages:
        return {"closed": 0, "pages": len(pages)}
    closed = 0
    try:
        ws = websocket.create_connection(ws_url, timeout=10, suppress_origin=True)
        for i, tid in enumerate(pages, start=10):
            ws.send(json.dumps({"id": i, "method": "Target.closeTarget", "params": {"targetId": tid}}))
            for _ in range(20):
                m = json.loads(ws.recv())
                if m.get("id") == i:
                    closed += bool((m.get("result") or {}).get("success", "error" not in m))
                    break
        ws.close()
    except Exception as e:  # noqa: BLE001
        return {"closed": closed, "pages": len(pages), "error": str(e)[:160]}
    return {"closed": closed, "pages": len(pages)}


CMDLINE_JS = "(() => { const e = document.getElementById('command_line'); return e ? e.textContent : ''; })()"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--devtools", default="http://127.0.0.1:9222")
    ap.add_argument("--duration", type=int, default=75, help="NetLog duration (s) from process start")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pkg = a.package
    netlog = f"/data/user/0/{pkg}/cache/{NETLOG_NAME}"
    res = {"package": pkg, "scenario": "close all tabs -> cold start -> 25 s idle -> New Tab Page -> idle (no test pages)"}

    comp = resolve_launcher(pkg)
    res["launcher"] = comp
    flags = f"_ --log-net-log={netlog} --net-log-file-format=ndjson --net-log-duration={a.duration}"
    res["tabs_closed"] = close_all_tabs(a.devtools)
    time.sleep(4)   # let the tab state be written before the process is killed
    adb("shell", "am", "force-stop", pkg)
    res["adb_enabled_setting"] = adb("shell", "settings", "get", "global", "adb_enabled").strip()
    if res["adb_enabled_setting"] != "1":   # CommandLineInitUtil.getDebugApp() needs ADB_ENABLED == 1
        adb("shell", "settings", "put", "global", "adb_enabled", "1")
    adb("shell", "am", "set-debug-app", "--persistent", pkg)
    adb("shell", f"echo '{flags}' > {CMDLINE_FILE} && chmod 644 {CMDLINE_FILE}")
    t0 = time.time()
    try:
        adb("shell", "am", "start", "-W", "-n", comp, timeout=60) if comp else adb(
            "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(25)
        res["ntp_open"] = open_internal(a.devtools, "chrome://newtab/")
        time.sleep(15)
        res["version_open"] = open_internal(a.devtools, "chrome://version/")
        time.sleep(3)
        cl = internal_text(a.devtools, "chrome://version", CMDLINE_JS) or ""
        res["flags_applied"] = "--log-net-log" in cl
        res["command_line"] = cl[:400]
        time.sleep(max(0, a.duration + 8 - (time.time() - t0)))   # past --net-log-duration -> file flushed
    finally:
        adb("shell", "rm", "-f", CMDLINE_FILE)
        adb("shell", "am", "clear-debug-app")
    raw, how = read_app_file(netlog)
    res["read_via"] = how
    if not raw:
        res.update({"captured": False, "verdict": "not_captured"})
        print("startup netlog:", res)
        json.dump(res, open(os.path.join(a.out, "startup_netlog.json"), "w"), indent=1)
        print("STARTUP_NETLOG NOT_CAPTURED")
        return 0
    with gzip.open(os.path.join(a.out, "startup_netlog.jsonl.gz"), "wb") as f:
        f.write(raw)
    consts, events = load_netlog(raw.decode("utf-8", "replace"))
    s = summarize(consts, events)
    res.update(s)
    res["captured"] = s["events"] > 0
    res["bytes"] = len(raw)
    res["verdict"] = ("sb_contact_at_startup" if s["sb_hosts"] else "clean") if res["captured"] else "not_captured"
    json.dump(res, open(os.path.join(a.out, "startup_netlog.json"), "w"), indent=1, ensure_ascii=False)
    short = {k: v for k, v in res.items() if k not in ("requests", "connect_hosts", "resolves", "remote_ips",
                                                       "command_line", "ntp_open", "version_open")}
    print("startup netlog:", json.dumps(short, ensure_ascii=False))
    print("requests:", json.dumps(res["requests"], ensure_ascii=False)[:3000])
    print("resolves:", json.dumps(res["resolves"], ensure_ascii=False)[:2000])
    print("connect hosts:", json.dumps(res["connect_hosts"], ensure_ascii=False)[:2000])
    print("STARTUP_NETLOG", {"clean": "PASS", "not_captured": "NOT_CAPTURED"}.get(res["verdict"], "FAIL"))
    return 1 if res["verdict"] == "sb_contact_at_startup" else 0


if __name__ == "__main__":
    raise SystemExit(main())
