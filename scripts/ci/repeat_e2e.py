#!/usr/bin/env python3
"""Repeat-visit speed (the Arena case: a single-page app the user opens many times a day), same APK, A/B modes.

Page: https://speed.example.com/spa.html?r=<id> (HTML never cached) loads, from stable hashed-name URLs cached for a
year (`max-age=31536000, immutable`, like a modern SPA build): spa.<hash>.css (30 KB), spa-app.<hash>.js (200 KB;
renders the page when it runs, as a framework would) and the LCP image on the CDN host (spa-hero.<hash>.png), which
only the script inserts (late discovery). Server latency/rate are speed_e2e's (60 ms first byte, 250 KiB/s).

Per mode: 3 training visits (fill the HTTP cache and V8 code cache, let LCPP learn), then 3 x
  * cold: verified browser restart (new PID, flags checked in chrome://version), then one visit;
  * warm: a second visit in that running browser.
Modes alternate order per cycle; each records load / LCP / FCP from the page and which resources came from the
network (server log, attributed by time window to the visit).

Modes:
  chromium_defaults  Chromium code defaults (testing config off, Swiftra features off) - as in speed_e2e
  swiftra            the APK as shipped
  swiftra_lcpp       + LCP Critical Path Predictor features that are off by default @155 (none sends a request to a
                     third party; HttpDiskCachePrewarming reads only from cache, LOAD_ONLY_FROM_CACHE, no credentials;
                     prewarm_http_disk_cache_manager.cc). A candidate: it goes into the Speed Pack only if it wins here.

Prints REPEAT_E2E MEASURED ... (medians per mode/scenario). A measurement, not a pass/fail claim.
Usage: repeat_e2e.py --package <pkg> --out <dir> [--socket chrome_devtools_remote] [--cycles 2] [--visits 3]
"""
import argparse
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import speed_e2e as se  # noqa: E402

LCPP_FEATURES = ("LCPCriticalPathPredictor,LCPPFontURLPredictor,LCPPAutoPreconnectLcpOrigin,"
                 "LCPPPrefetchSubresource,HttpDiskCachePrewarming")
MODES = {
    "chromium_defaults": se.MODES["chromium_defaults"],
    "swiftra": "",
    "swiftra_lcpp": f"--enable-features={LCPP_FEATURES}",
}
CSS, APP, HERO = "spa.3f9a1c.css", "spa-app.8b2e4d.js", "spa-hero.c71d0e.png"
IMMUTABLE = "public, max-age=31536000, immutable"
ASSETS = {}

PAGE = """<!doctype html><html><head><meta name=viewport content='width=device-width'>
<title>SPEED:pending</title><link rel=stylesheet href='/%(css)s'>
<script>
window.__lcp=0;try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__lcp=e.startTime;})
.observe({type:'largest-contentful-paint',buffered:true});}catch(e){}
addEventListener('load',()=>setTimeout(()=>{
 const n=performance.getEntriesByType('navigation')[0]||{};
 const p=performance.getEntriesByName('first-contentful-paint')[0];
 const res=performance.getEntriesByType('resource');
 const h=res.find(e=>e.name.indexOf('%(hero)s')>=0)||{};
 const a=res.find(e=>e.name.indexOf('%(app)s')>=0)||{};
 document.getElementById('r').textContent=JSON.stringify({load:Math.round(n.loadEventEnd||0),
  dcl:Math.round(n.domContentLoadedEventEnd||0),ttfb:Math.round(n.responseStart||0),
  fcp:p?Math.round(p.startTime):null,lcp:Math.round(window.__lcp),app_ran:Math.round(window.__appT||0),
  hero_start:Math.round(h.startTime||0),hero_end:Math.round(h.responseEnd||0),hero_transfer:h.transferSize,
  app_end:Math.round(a.responseEnd||0),app_transfer:a.transferSize,resources:res.length,
  transfer:res.reduce((s,e)=>s+(e.transferSize||0),0)+(n.transferSize||0)});
 document.title='SPEED:done';},1500));
</script></head><body><div id=app>Loading</div><p id=r></p>
<script src='/%(app)s'></script></body></html>"""

APP_TAIL = """
window.__appT=performance.now();
(function(){var d=document.createElement('div');
d.innerHTML="<h1 class=brand>Swiftra repeat-visit test</h1>"+
 "<img id=hero width=360 height=240 src='https://%s/%s'>"+
 "<p>"+new Array(40).join('Rendered by the app script. ')+"</p>";
var a=document.getElementById('app');a.textContent='';a.appendChild(d);})();
""" % (se.CDN, HERO)


def spki_hash(cert_pem):
    """base64 SHA-256 of the certificate's SubjectPublicKeyInfo, for --ignore-certificate-errors-spki-list.

    Chromium never stores a response in the HTTP cache when the certificate has an error, so the plain
    --ignore-certificate-errors that speed_e2e uses (no-store pages there anyway) would make every repeat visit a
    network visit. With the test certificate's SPKI on that list the certificate verifies as valid (the same method
    Chromium's WebPageReplay/telemetry uses), and caching behaves as on a real site."""
    import base64
    import hashlib
    import subprocess
    der = subprocess.run(["openssl", "x509", "-in", cert_pem, "-noout", "-pubkey"], check=True, capture_output=True)
    spki = subprocess.run(["openssl", "pkey", "-pubin", "-outform", "der"], input=der.stdout, check=True,
                          capture_output=True).stdout
    return base64.b64encode(hashlib.sha256(spki).digest()).decode()


def build_assets():
    ASSETS[CSS] = ((se.filler(30000, "spa-css") + "h1.brand{font:600 22px sans-serif;color:#1a73e8}\n").encode(),
                   "text/css")
    ASSETS[APP] = ((se.filler(200000, "spa-app") + APP_TAIL).encode(), "application/javascript")
    ASSETS[HERO] = (se.png(360, 240, "spa-hero"), "image/png")


def page_html():
    return (PAGE % {"css": CSS, "app": APP, "hero": HERO}).encode()


def register_routes():
    se.EXTRA[(se.SITE, "spa.html")] = lambda rec, q: (page_html(), "text/html; charset=utf-8", "no-store")
    for host, name in ((se.SITE, CSS), (se.SITE, APP), (se.CDN, HERO)):
        se.EXTRA[(host, name)] = (lambda n: lambda rec, q: (ASSETS[n][0], ASSETS[n][1], IMMUTABLE))(name)


def visit_requests(rid, recs=None):
    """Server requests that belong to visit |rid|: from its HTML request until the next spa.html request (stable
    asset URLs carry no visit id; visits run one after another)."""
    if recs is None:
        with se.LOCK:
            recs = [dict(r) for r in se.REQ]
    html = [r for r in recs if r["path"] == "/spa.html" and r["rid"] == rid]
    if not html:
        return []
    t0 = html[0]["t0"]
    later = [r["t0"] for r in recs if r["path"] == "/spa.html" and r["t0"] > t0]
    t1 = min(later) if later else float("inf")
    # LCPP subresource prefetch may start just before its HTML request: both window edges get the same 0.5 s lead
    return [r for r in recs if t0 - 0.5 <= r["t0"] < t1 - 0.5 and r["path"] != "/spa.html"
            and r["path"].lstrip("/") in (CSS, APP, HERO)]


def drop_page_cache():
    """Best effort cold-device emulation (root only). Returns True if the kernel page cache was dropped."""
    for cmd in (["shell", "echo 3 > /proc/sys/vm/drop_caches && echo dropped"],
                ["shell", "su", "0", "sh", "-c", "echo 3 > /proc/sys/vm/drop_caches && echo dropped"]):
        if "dropped" in se.adb(*cmd, timeout=20):
            return True
    return False


def load_spa(rid):
    url = f"https://{se.SITE}/spa.html?r={rid}"
    r = se.open_tab(url, rid)
    out = {"rid": rid, "open": r, "page": None}
    if r == "ok":
        t0, val = time.time(), None
        while time.time() - t0 < 45 and not val:
            for t in se.targets(se.DEVTOOLS):
                if t.get("type") == "page" and t.get("url", "") == url:
                    v = se.page_text(se.DEVTOOLS, url, "(() => ({t: document.title, "
                                     "r: (document.getElementById('r')||{}).textContent||''}))()")
                    if isinstance(v, dict) and v.get("t") == "SPEED:done":
                        val = v
            if not val:
                time.sleep(1)
        try:
            out["page"] = json.loads(val["r"]) if val else None
        except ValueError:
            pass
    time.sleep(1)
    reqs = visit_requests(rid)
    out["network"] = sorted({x["path"].lstrip("/") for x in reqs})
    out["closed_tabs"] = se.close_targets("spa.html")
    return out


def summarize(res):
    out = {}
    for mode in MODES:
        out[mode] = {}
        for sc in ("cold", "warm"):
            vs = [v for c in res["cycles"] for v in c.get(mode, {}).get(sc, [])]
            pages = [v["page"] for v in vs if v.get("page")]
            out[mode][sc] = {"n": len(pages), "of": len(vs),
                             "load_ms": se.med([p["load"] for p in pages]),
                             "lcp_ms": se.med([p["lcp"] for p in pages]),
                             "fcp_ms": se.med([p["fcp"] for p in pages]),
                             "app_ran_ms": se.med([p.get("app_ran") for p in pages]),
                             "hero_end_ms": se.med([p.get("hero_end") for p in pages]),
                             "network_hits": se.med([len(v.get("network", [])) for v in vs if v.get("page")])}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--socket", default=os.environ.get("SOCK", "chrome_devtools_remote"))
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--visits", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    se.MODES.clear()
    se.MODES.update(MODES)                       # restart()/flags_ok() check exactly these modes' flags
    se.SOCKET, se.OUT, se.PKG = a.socket, a.out, a.package
    se.DL_DATA = b"\0" * 1024
    build_assets()
    register_routes()
    tmp = tempfile.mkdtemp()
    se.start_server(tmp)
    spki = f"--ignore-certificate-errors-spki-list={spki_hash(os.path.join(tmp, 'c.pem'))}"
    for m in se.MODES:                           # every mode: the test certificate counts as valid (HTTP cache on)
        se.MODES[m] = (se.MODES[m] + " " + spki).strip()
    pkg, comp = a.package, se.resolve_launcher(a.package)
    res = {"package": pkg, "modes": MODES, "lat_ms": se.LAT_MS, "page_rate": se.PAGE_RATE, "cycles": [],
           "page_cache_dropped": None}
    order = list(MODES)
    try:
        se.adb("shell", "am", "set-debug-app", "--persistent", pkg)
        se.adb("reverse", f"tcp:{se.PORT}", f"tcp:{se.PORT}")
        for c in range(a.cycles):
            cyc = {}
            for mode in (order if c % 2 == 0 else order[::-1]):
                rec = cyc[mode] = {"cold": [], "warm": [], "train": []}
                try:
                    st = se.restart(pkg, comp, mode, a.socket)
                    rec["flags_applied"] = st["flags_applied"]
                    if not st["flags_applied"]:
                        continue
                    for i in range(3):
                        rec["train"].append(load_spa(f"t{c}{mode[:2]}{mode[-2:]}{i}"))
                    for i in range(a.visits):
                        st = se.restart(pkg, comp, mode, a.socket)
                        if not st["flags_applied"]:
                            rec.setdefault("restart_failures", 0)
                            rec["restart_failures"] += 1
                            continue
                        dropped = drop_page_cache()
                        res["page_cache_dropped"] = bool(res["page_cache_dropped"]) or dropped
                        rec["cold"].append(load_spa(f"c{c}{mode[:2]}{mode[-2:]}{i}"))
                        rec["warm"].append(load_spa(f"w{c}{mode[:2]}{mode[-2:]}{i}"))
                except Exception as e:  # noqa: BLE001 - keep the other modes
                    rec["error"] = f"{type(e).__name__}: {e}"[:300]
                print(f"cycle {c} {mode}: " + json.dumps({
                    "flags": rec.get("flags_applied"),
                    "cold": [(v["page"] or {}).get("lcp") for v in rec["cold"]],
                    "warm": [(v["page"] or {}).get("lcp") for v in rec["warm"]],
                    "net_cold": [len(v.get("network", [])) for v in rec["cold"]]}), flush=True)
            res["cycles"].append(cyc)
            res["devtools_recovery"] = se.RECOVERY
            json.dump(res, open(os.path.join(a.out, "repeat_e2e.json"), "w"), indent=1)
    finally:
        se.adb("shell", "rm", "-f", se.CMDLINE_FILE)
        se.adb("shell", "am", "clear-debug-app")
        se.adb("shell", "am", "force-stop", pkg)
    s = res["summary"] = summarize(res)
    json.dump(res, open(os.path.join(a.out, "repeat_e2e.json"), "w"), indent=1)
    ok = all(s[m][sc]["n"] for m in MODES for sc in ("cold", "warm"))
    parts = " ".join(f"{m}:cold_lcp={s[m]['cold']['lcp_ms']},cold_load={s[m]['cold']['load_ms']},"
                     f"warm_lcp={s[m]['warm']['lcp_ms']},warm_load={s[m]['warm']['load_ms']},"
                     f"net={s[m]['cold']['network_hits']}" for m in MODES)
    print(f"REPEAT_E2E {'MEASURED' if ok else 'PARTIAL'} {parts} page_cache_dropped={res['page_cache_dropped']} "
          f"devtools_recoveries={len(se.RECOVERY)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
