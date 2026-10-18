#!/usr/bin/env python3
"""Swiftra speed, measured on the device: same APK, same device, two modes, alternated (A B A B).

Modes (command-line file; the package is the debug app, see startup_netlog.py):
  chromium_defaults : --disable-field-trial-config --disable-features=SwiftraAdBlock
                      = Chromium code defaults (no Speed Pack, no ad blocker). NOT Google Chrome: Chrome stable also
                      gets Finch experiments from Google's server, which no test here can reproduce.
  swiftra           : the shipped defaults (Speed Pack 0016 + ad blocker 0012/0013 + everything else)

1. Page load. https://speed.example.com/news.html is a synthetic news page: 4 CSS, 8 scripts, 1 hero image (LCP),
   18 images from speed.example.com + cdn.example.net, plus a typical ad/tracker chain (ib.adnxs.com loader ->
   3 ad iframes with creatives + scorecardresearch beacons, google-analytics script + beacon). All hosts are mapped
   (--host-resolver-rules) to a local HTTPS server on the runner (adb reverse); no request leaves the runner.
   The server adds a fixed per-response latency (LAT_MS, ad servers ADLAT_MS) and caps each connection's rate
   (PAGE_RATE), so the network is the bottleneck like on a phone, not the loopback. Every load uses a fresh
   ?r=<id> on all URLs (no HTTP cache hits). Recorded per load: navigation loadEventEnd, FCP, LCP (from the page,
   Navigation/Paint/LCP APIs), and server-side requests/bytes for that load id.
2. Download. https://dl.example.com/f/<id>.zip (24 MiB, Accept-Ranges, ETag, Last-Modified, attachment).
   Each connection is capped at DL_RATE (servers that limit per-connection speed are common; on a link that is
   the bottleneck itself extra connections cannot help, and this test does not claim otherwise).
   Recorded server-side: wall time from the first request to the last byte, number of connections, and whether
   the served byte ranges cover the whole file; on the device: the file in /sdcard/Download and its size.

Prints SPEED_E2E MEASURED ... (numbers + medians) or NOT_RUN. It is a measurement, not a pass/fail claim.
Usage: speed_e2e.py --package <pkg> --out <dir> [--socket chrome_devtools_remote] [--cycles 2] [--loads 3]
"""
import argparse
import hashlib
import http.server
import json
import os
import re
import ssl
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import zlib
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shield_e2e import adb, browser_ws, open_internal, page_text, targets  # noqa: E402
from startup_netlog import CMDLINE_FILE, CMDLINE_JS, resolve_launcher  # noqa: E402

PORT = 8772
SITE, CDN, DL = "speed.example.com", "cdn.example.net", "dl.example.com"
ADS = ("ib.adnxs.com", "www.google-analytics.com", "sb.scorecardresearch.com")   # real list entries (0012 E2E)
HOSTS = (SITE, CDN, DL) + ADS
RULES = ",".join(f"MAP {h} 127.0.0.1:{PORT}" for h in HOSTS)
MODES = {
    "chromium_defaults": "--disable-field-trial-config --disable-features=SwiftraAdBlock",
    "swiftra": "",
}
LAT_MS, ADLAT_MS = 60, 150          # per-response latency (first byte), site/CDN vs ad servers
PAGE_RATE = 250 * 1024              # bytes/s per connection for page resources
DL_SIZE, DL_RATE = 24 * 1024 * 1024, 1024 * 1024   # 24 MiB file, 1 MiB/s per connection
DEVTOOLS = "http://127.0.0.1:9222"


def png(w, h, seed):
    """Valid RGB PNG with noisy rows (incompressible enough to have a realistic size)."""
    rnd = hashlib.sha256(seed.encode()).digest()
    rows = b"".join(b"\x00" + (rnd * ((w * 3) // 32 + 1))[:w * 3] for _ in range(h))
    # vary rows so zlib cannot collapse them
    rows = bytes((b + i * 7) & 0xFF for i, b in enumerate(rows))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def filler(n, seed, comment=("/*", "*/")):
    h = hashlib.sha256(seed.encode()).hexdigest()
    body = (h * (n // len(h) + 1))[:max(0, n - 8)]
    return f"{comment[0]}{body}{comment[1]}\n"


ASSETS = {}


def build_assets():
    ASSETS["hero.png"] = (png(360, 240, "hero"), "image/png")
    for i in range(18):
        ASSETS[f"img{i}.png"] = (png(120, 80, f"img{i}"), "image/png")
    for i in range(4):
        ASSETS[f"s{i}.css"] = ((filler(20000, f"css{i}") + f".c{i}{{color:#333}}\n").encode(), "text/css")
    for i in range(8):
        ASSETS[f"a{i}.js"] = ((filler(40000, f"js{i}") + f"window.__a{i}=1;\n").encode(), "application/javascript")
    ASSETS["creative.png"] = (png(300, 250, "creative"), "image/png")
    ASSETS["ast.js"] = ((filler(80000, "ast") + AST_JS).encode(), "application/javascript")
    ASSETS["analytics.js"] = ((filler(50000, "ga") + GA_JS).encode(), "application/javascript")
    ASSETS["b.gif"] = (bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b"),
                       "image/gif")


AST_JS = """(function(){var r=(document.currentScript&&document.currentScript.src.split('r=')[1])||'0';
for(var i=0;i<3;i++){var f=document.createElement('iframe');f.width=300;f.height=250;
f.src='https://ib.adnxs.com/creative.html?i='+i+'&r='+r;document.body.appendChild(f);}})();
"""
GA_JS = """(function(){var r=(document.currentScript&&document.currentScript.src.split('r=')[1])||'0';
var i=new Image();i.src='https://www.google-analytics.com/collect?b.gif&r='+r;})();
"""
CREATIVE_HTML = ("<!doctype html><body style=margin:0><img src='https://ib.adnxs.com/creative.png?r={r}'>"
                 "<img src='https://sb.scorecardresearch.com/b.gif?c={i}&r={r}'>"
                 "<script src='https://ib.adnxs.com/a0.js?f={i}&r={r}'></script></body>")


def news_html(r):
    css = "".join(f"<link rel=stylesheet href='https://{SITE if i % 2 else CDN}/s{i}.css?r={r}'>" for i in range(4))
    js = "".join(f"<script src='https://{CDN if i % 2 else SITE}/a{i}.js?r={r}'></script>" for i in range(4))
    js_end = "".join(f"<script src='https://{CDN}/a{i}.js?r={r}'></script>" for i in range(4, 8))
    imgs = "".join(f"<img width=120 height=80 src='https://{CDN if i % 3 else SITE}/img{i}.png?r={r}'>"
                   for i in range(18))
    ads = (f"<script async src='https://ib.adnxs.com/ast.js?r={r}'></script>"
           f"<script async src='https://www.google-analytics.com/analytics.js?r={r}'></script>")
    return f"""<!doctype html><html><head><meta name=viewport content='width=device-width'>
<title>SPEED:pending</title>{css}{js}{ads}
<script>
window.__lcp=0;try{{new PerformanceObserver(l=>{{for(const e of l.getEntries())window.__lcp=e.startTime;}})
.observe({{type:'largest-contentful-paint',buffered:true}});}}catch(e){{}}
addEventListener('load',()=>setTimeout(()=>{{
 const n=performance.getEntriesByType('navigation')[0]||{{}};
 const p=performance.getEntriesByName('first-contentful-paint')[0];
 const res=performance.getEntriesByType('resource');
 document.getElementById('r').textContent=JSON.stringify({{load:Math.round(n.loadEventEnd||0),
  dcl:Math.round(n.domContentLoadedEventEnd||0),ttfb:Math.round(n.responseStart||0),
  fcp:p?Math.round(p.startTime):null,lcp:Math.round(window.__lcp),resources:res.length,
  transfer:res.reduce((a,e)=>a+(e.transferSize||0),0)+(n.transferSize||0)}});
 document.title='SPEED:done';}},1500));
</script></head><body><h1>Swiftra speed test</h1>
<img id=hero width=360 height=240 src='https://{SITE}/hero.png?r={r}'>
<p id=r></p>{imgs}{js_end}</body></html>"""


LOCK = threading.Lock()
REQ = []   # dicts: host, path, rid, t0, t1, bytes, range_start, status


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"   # keep-alive + ranges (parallel download needs HTTP/1.1)

    def log_message(self, *a):
        pass

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        path, _, query = self.path.partition("?")
        m = re.search(r"(?:^|&)r=([A-Za-z0-9_-]+)", query)
        rec = {"host": host, "path": path, "rid": m.group(1) if m else None, "t0": time.time(), "t1": None,
               "bytes": 0, "range": self.headers.get("Range"), "status": None}
        with LOCK:
            REQ.append(rec)
        try:
            if host == DL and path.startswith("/f/"):
                rec["rid"] = path[3:].split(".")[0]
                return self._download(rec)
            time.sleep((ADLAT_MS if host in ADS else LAT_MS) / 1000)
            name = path.lstrip("/")
            if host == SITE and name == "bench.html":
                return self._send(rec, BENCH_HTML.encode(), "text/html; charset=utf-8", rate=10 * 1024 * 1024)
            if host == SITE and name == "news.html":
                return self._send(rec, news_html(rec["rid"]).encode(), "text/html; charset=utf-8")
            if host in ADS and name == "creative.html":
                i = re.search(r"i=(\d+)", query)
                return self._send(rec, CREATIVE_HTML.format(r=rec["rid"], i=i.group(1) if i else 0).encode(),
                                  "text/html; charset=utf-8")
            if host in ADS and name == "collect":
                name = "b.gif"
            if name in ASSETS:
                data, ctype = ASSETS[name]
                return self._send(rec, data, ctype)
            rec["status"] = 404
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError, OSError):
            pass
        finally:
            rec["t1"] = time.time()

    def _send(self, rec, data, ctype, rate=PAGE_RATE):
        rec["status"] = 200
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Timing-Allow-Origin", "*")
        self.end_headers()
        self._throttled(rec, data, rate)

    def _throttled(self, rec, data, rate):
        t0, sent, step = time.time(), 0, 16 * 1024
        while sent < len(data):
            chunk = data[sent:sent + step]
            self.wfile.write(chunk)
            sent += len(chunk)
            rec["bytes"] = sent
            ahead = sent / rate - (time.time() - t0)
            if ahead > 0:
                time.sleep(ahead)
        self.wfile.flush()

    def _download(self, rec):
        size, start, end = DL_SIZE, 0, DL_SIZE - 1
        rng = self.headers.get("Range")
        m = re.match(r"bytes=(\d+)-(\d*)", rng or "")
        if m:
            start = int(m.group(1))
            end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
        rec["range_start"] = start
        rec["status"] = 206 if m else 200
        self.send_response(206 if m else 200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", '"swiftra-speed-24m"')
        self.send_header("Last-Modified", "Sat, 17 Oct 2026 00:00:00 GMT")
        self.send_header("Content-Disposition", f'attachment; filename="swiftra-speed-{rec["rid"]}.zip"')
        if m:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        self._throttled(rec, DL_DATA[start:end + 1], DL_RATE)


DL_DATA = b""
# CPU benchmark (tools/speedpack/bench.js, own code): JS engine + DOM/layout work, no network. Same page in both
# modes; across APKs it is the PGO before/after number (arm64).
BENCH_RUNS = 5
BENCH_HTML = ("<!doctype html><meta name=viewport content='width=device-width'><title>BENCH:running</title>"
              "<body><pre id=r></pre><script>"
              + open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "speedpack",
                                  "bench.js"), encoding="utf-8").read()
              + "\nsetTimeout(function(){var r=swiftraBench(%d);document.getElementById('r').textContent="
                "JSON.stringify(r);document.title='BENCH:done';},1500);</script>" % BENCH_RUNS)


def start_server(tmp):
    key, crt = os.path.join(tmp, "k.pem"), os.path.join(tmp, "c.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-keyout", key,
                    "-out", crt, "-subj", f"/CN={SITE}", "-addext",
                    "subjectAltName=" + ",".join(f"DNS:{h}" for h in HOSTS)],
                   check=True, capture_output=True, timeout=60)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.daemon_threads = True
    srv.handle_error = lambda *a: None   # cancelled slices / closed tabs end with SSL EOF: expected
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def coverage(recs, size):
    """Bytes of [0, size) covered by what the server actually wrote (union of [range_start, +bytes))."""
    iv = sorted((r.get("range_start", 0), r.get("range_start", 0) + r["bytes"]) for r in recs if r["bytes"])
    covered, cur_s, cur_e = 0, None, None
    for s, e in iv:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                covered += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        covered += cur_e - cur_s
    return min(covered, size)


def download_stats(rid):
    with LOCK:
        recs = [dict(r) for r in REQ if r["host"] == DL and r["rid"] == rid]
    if not recs:
        return {"requests": 0}
    t0 = min(r["t0"] for r in recs)
    done = [r["t1"] for r in recs if r["t1"]]
    cov = coverage(recs, DL_SIZE)
    return {"requests": len(recs), "ranges": [r["range"] for r in recs][:12], "covered": cov,
            "complete": cov == DL_SIZE, "all_closed": len(done) == len(recs),
            "seconds": round(max(done) - t0, 2) if done and len(done) == len(recs) else None,
            "max_concurrent": max_concurrent(recs)}


def max_concurrent(recs):
    ev = sorted([(r["t0"], 1) for r in recs] + [(r["t1"] or 1e18, -1) for r in recs])
    cur = best = 0
    for _, d in ev:
        cur += d
        best = max(best, cur)
    return best


def page_stats(rid):
    with LOCK:
        recs = [dict(r) for r in REQ if r["rid"] == rid and r["host"] != DL]
    return {"requests": len(recs), "bytes": sum(r["bytes"] for r in recs),
            "ad_requests": sum(1 for r in recs if r["host"] in ADS),
            "ad_bytes": sum(r["bytes"] for r in recs if r["host"] in ADS),
            "server_span_ms": round((max(r["t1"] or r["t0"] for r in recs) - min(r["t0"] for r in recs)) * 1000)
            if recs else None}


DIALOG_BUTTONS = ("Download", "Continue", "Keep", "Don't allow", "Don’t allow", "OK")


def tap_dialog_buttons(seconds):
    """Download location / notification permission dialogs: tap the first known button (logged)."""
    taps, t0 = [], time.time()
    while time.time() - t0 < seconds:
        adb("shell", "uiautomator", "dump", "/sdcard/sp.xml", timeout=20)
        xml = adb("shell", "cat", "/sdcard/sp.xml", timeout=20)
        hit = None
        for m in re.finditer(r'<node [^>]*text="([^"]*)"[^>]*clickable="true"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                             xml):
            if m.group(1) in DIALOG_BUTTONS:
                hit = m
                break
        if not hit:
            time.sleep(1.5)
            continue
        x = (int(hit.group(2)) + int(hit.group(4))) // 2
        y = (int(hit.group(3)) + int(hit.group(5))) // 2
        adb("shell", "input", "tap", str(x), str(y))
        taps.append(hit.group(1))
        time.sleep(1.5)
    return taps


def pid_of(pkg):
    out = (adb("shell", "pidof", pkg) or "").strip().split()
    return out[0] if out else ""


def flags_ok(cl, mode):
    """The browser runs with exactly this mode's flags: its own present, every other mode's flags absent."""
    if "--host-resolver-rules" not in cl:
        return False
    mine = MODES[mode].split()
    others = {f for m, v in MODES.items() if m != mode for f in v.split()} - set(mine)
    return all(f in cl for f in mine) and not any(f in cl for f in others)


def restart(pkg, comp, mode, socket, attempts=3):
    """Cold restart with this mode's command line, verified: new browser PID + chrome://version of that process.

    (2026-10-18 A/A run 39132156695: a fixed 7 s wait missed DevTools on arm64, and an empty expected-flag list
    made a stale command line count as applied. Both are checked now.)"""
    flags = f'_ --host-resolver-rules="{RULES}" --ignore-certificate-errors {MODES[mode]}'.rstrip()
    tries = []
    for attempt in range(attempts):
        old = pid_of(pkg)
        adb("shell", "am", "force-stop", pkg)
        t0 = time.time()
        while pid_of(pkg) and time.time() - t0 < 15:
            time.sleep(1)
        adb("shell", f"echo '{flags}' > {CMDLINE_FILE} && chmod 644 {CMDLINE_FILE}")
        adb("shell", "am", "start", "-W", "-n", comp, timeout=60) if comp else adb(
            "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
        t0, pid, ready = time.time(), "", False
        while time.time() - t0 < 45:
            pid = pid_of(pkg)
            if pid and pid != old:
                adb("forward", "tcp:9222", f"localabstract:{socket}")
                if targets(DEVTOOLS):
                    ready = True
                    break
            time.sleep(1.5)
        nonce = f"{mode[0]}{attempt}{int(time.time() * 1000) % 100000000}"
        url = f"chrome://version/?swiftra={nonce}"
        cl = ""
        if ready:
            time.sleep(2)
            open_internal(DEVTOOLS, url)
            t1 = time.time()
            while time.time() - t1 < 20 and not cl:
                if any(t.get("url", "") == url for t in targets(DEVTOOLS)):
                    cl = page_text(DEVTOOLS, url, CMDLINE_JS) or ""
                if not cl:
                    time.sleep(1.5)
            close_targets("chrome://version")
        ok = flags_ok(cl, mode)
        tries.append({"attempt": attempt, "old_pid": old, "pid": pid, "ready": ready,
                      "seconds": round(time.time() - t0, 1), "ok": ok})
        if ok:
            return {"flags_applied": True, "cmdline": cl[:400], "pid": pid, "tries": tries}
    return {"flags_applied": False, "cmdline": cl[:400], "tries": tries}


def close_targets(substr):
    """Target.closeTarget for every page whose URL contains |substr| (keeps the tab strip small between loads)."""
    import websocket
    ids = [t["id"] for t in targets(DEVTOOLS) if t.get("type") == "page" and substr in t.get("url", "")]
    ws_url = browser_ws(DEVTOOLS)
    if not ids or not ws_url:
        return 0
    try:
        ws = websocket.create_connection(ws_url, timeout=10, suppress_origin=True)
        for n, tid in enumerate(ids, 1):
            ws.send(json.dumps({"id": n, "method": "Target.closeTarget", "params": {"targetId": tid}}))
            for _ in range(20):
                if json.loads(ws.recv()).get("id") == n:
                    break
        ws.close()
    except Exception:  # noqa: BLE001
        pass
    return len(ids)


def load_page(rid, shot=None):
    url = f"https://{SITE}/news.html?r={rid}"
    r = open_internal(DEVTOOLS, url)
    t0, val, reopened = time.time(), None, False
    while time.time() - t0 < 60:
        if not reopened and time.time() - t0 > 10 and not page_stats(rid)["requests"]:
            r, reopened = open_internal(DEVTOOLS, url), True      # the tab never opened (A/A run: 1 of 6 loads)
            t0 = time.time()
        for t in targets(DEVTOOLS):
            if t.get("type") == "page" and t.get("url", "") == url:
                v = page_text(DEVTOOLS, url, "(() => ({t: document.title, r: (document.getElementById('r')||{}).textContent||''}))()")
                if isinstance(v, dict) and v.get("t") == "SPEED:done":
                    val = v
        if val:
            break
        time.sleep(1)
    time.sleep(1)
    if shot:
        subprocess.run(f"adb exec-out screencap -p > '{shot}'", shell=True, timeout=30)
    out = {"open": r, "page": None, "reopened": reopened}
    try:
        out["page"] = json.loads(val["r"]) if val else None
    except ValueError:
        pass
    out["server"] = page_stats(rid)
    out["closed_tabs"] = close_targets(f"r={rid}")
    return out


def run_bench(rid):
    url = f"https://{SITE}/bench.html?r={rid}"
    r = open_internal(DEVTOOLS, url)
    t0, val, reopened = time.time(), None, False
    while time.time() - t0 < 180 and not val:
        time.sleep(3)
        if not reopened and time.time() - t0 > 10 and not page_stats(rid)["requests"]:
            r, reopened = open_internal(DEVTOOLS, url), True
            t0 = time.time()
        v = page_text(DEVTOOLS, url, "(() => ({t: document.title, r: (document.getElementById('r')||{}).textContent||''}))()")
        if isinstance(v, dict) and v.get("t") == "BENCH:done":
            val = v
    out = {"open": r, "seconds": round(time.time() - t0, 1), "result": None}
    try:
        out["result"] = json.loads(val["r"]) if val else None
    except ValueError:
        pass
    out["closed_tabs"] = close_targets("bench.html")
    return out


def device_file(rid):
    ls = adb("shell", "ls", "-l", "/sdcard/Download/", timeout=20)
    for ln in ls.splitlines():
        if f"swiftra-speed-{rid}" in ln:
            m = re.search(r"\s(\d+)\s+\d{4}-\d\d-\d\d", ln)
            return {"line": ln.strip()[:160], "size": int(m.group(1)) if m else None}
    return None


def run_download(rid):
    url = f"https://{DL}/f/{rid}.zip"
    r = open_internal(DEVTOOLS, url)
    taps = tap_dialog_buttons(8)
    t0 = time.time()
    st = download_stats(rid)
    while time.time() - t0 < 75:
        st = download_stats(rid)
        if st.get("complete") and st.get("all_closed"):
            break
        time.sleep(1)
    time.sleep(3)
    rec = {"open": r, "dialog_taps": taps, "server": download_stats(rid), "device_file": device_file(rid)}
    rec["closed_tabs"] = close_targets(DL)
    return rec


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 1) if xs else None


def summarize(res):
    s = {}
    for mode in MODES:
        loads = [x for c in res["cycles"] for x in c[mode]["loads"]]
        pages = [x["page"] for x in loads if x.get("page")]
        dls = [c[mode]["download"]["server"] for c in res["cycles"] if c[mode].get("download")]
        s[mode] = {"loads_ok": len(pages), "loads_total": len(loads),
                   "load_ms": med([p["load"] for p in pages]), "lcp_ms": med([p["lcp"] for p in pages]),
                   "fcp_ms": med([p["fcp"] for p in pages]), "dcl_ms": med([p["dcl"] for p in pages]),
                   "requests": med([x["server"]["requests"] for x in loads]),
                   "kib": med([x["server"]["bytes"] / 1024 for x in loads]),
                   "ad_requests": med([x["server"]["ad_requests"] for x in loads]),
                   "download_s": med([d.get("seconds") for d in dls if d.get("complete")]),
                   "download_conns": med([d.get("requests") for d in dls if d.get("complete")]),
                   "downloads_complete": sum(1 for d in dls if d.get("complete")), "downloads": len(dls)}
        benches = [c[mode]["bench"]["result"] for c in res["cycles"] if (c[mode].get("bench") or {}).get("result")]
        s[mode]["bench_ms"] = med([b["total"] for b in benches])
        s[mode]["bench_runs"] = len(benches)
        s[mode]["bench_parts"] = {k: med([b["ms"].get(k) for b in benches]) for k in (benches[0]["ms"] if benches else {})}
    a, b = s["chromium_defaults"], s["swiftra"]

    def ratio(x, y):
        return round(x / y, 2) if x and y else None
    s["speedup"] = {"load": ratio(a["load_ms"], b["load_ms"]), "lcp": ratio(a["lcp_ms"], b["lcp_ms"]),
                    "download": ratio(a["download_s"], b["download_s"]), "bytes": ratio(a["kib"], b["kib"]),
                    "bench": ratio(a.get("bench_ms"), b.get("bench_ms"))}
    return s


def main():
    global DEVTOOLS, DL_DATA
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--devtools", default=DEVTOOLS)
    ap.add_argument("--socket", default=os.environ.get("SOCK", "chrome_devtools_remote"))
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--loads", type=int, default=3)
    a = ap.parse_args()
    DEVTOOLS = a.devtools
    os.makedirs(a.out, exist_ok=True)
    DL_DATA = hashlib.sha256(b"swiftra").digest() * (DL_SIZE // 32)
    build_assets()
    start_server(tempfile.mkdtemp())
    pkg, comp = a.package, resolve_launcher(a.package)
    res = {"package": pkg, "rules": RULES, "modes": MODES, "lat_ms": LAT_MS, "ad_lat_ms": ADLAT_MS,
           "page_rate": PAGE_RATE, "dl_size": DL_SIZE, "dl_rate": DL_RATE, "cycles": []}
    try:
        adb("shell", "am", "set-debug-app", "--persistent", pkg)
        adb("reverse", f"tcp:{PORT}", f"tcp:{PORT}")
        for c in range(a.cycles):
            cyc = {}
            for mode in MODES:
                st = restart(pkg, comp, mode, a.socket)
                rec = {"restart": st, "loads": []}
                if st["flags_applied"]:
                    load_page(f"w{c}{mode[0]}")    # warm-up (renderer, TLS session, ruleset), not counted
                    for i in range(a.loads):
                        shot = os.path.join(a.out, f"page_{mode}_{c}.png") if i == a.loads - 1 else None
                        rec["loads"].append(load_page(f"c{c}{mode[0]}{i}", shot))
                    rec["download"] = run_download(f"d{c}{mode[0]}")
                    rec["bench"] = run_bench(f"b{c}{mode[0]}")
                    subprocess.run(f"adb exec-out screencap -p > '{os.path.join(a.out, f'download_{mode}_{c}.png')}'",
                                   shell=True, timeout=30)
                cyc[mode] = rec
                print(f"cycle {c} {mode}:", json.dumps({"flags": st["flags_applied"],
                      "loads": [x.get("page") for x in rec["loads"]],
                      "download": (rec.get("download") or {}).get("server"),
                      "bench": (rec.get("bench") or {}).get("result")})[:1400], flush=True)
            res["cycles"].append(cyc)
    finally:
        adb("shell", "rm", "-f", CMDLINE_FILE)
        adb("shell", "am", "clear-debug-app")
        adb("shell", "am", "force-stop", pkg)
    ran = all(c[m]["restart"]["flags_applied"] for c in res["cycles"] for m in MODES) and res["cycles"]
    res["summary"] = summarize(res) if ran else None
    json.dump(res, open(os.path.join(a.out, "speed_e2e.json"), "w"), indent=1, ensure_ascii=False)
    if not ran:
        print("SPEED_E2E NOT_RUN flags not applied")
        return 0
    s = res["summary"]
    print("speed summary:", json.dumps(s, ensure_ascii=False))
    d, w = s["chromium_defaults"], s["swiftra"]
    print(f"SPEED_E2E MEASURED load_ms {d['load_ms']}->{w['load_ms']} lcp_ms {d['lcp_ms']}->{w['lcp_ms']} "
          f"kib {d['kib']}->{w['kib']} requests {d['requests']}->{w['requests']} "
          f"download_s {d['download_s']}->{w['download_s']} conns {d['download_conns']}->{w['download_conns']} "
          f"bench_ms {d.get('bench_ms')}->{w.get('bench_ms')} "
          f"speedup {s['speedup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
