#!/usr/bin/env python3
"""patches/0010: Swiftra's advanced defaults, checked by behaviour on the device (no settings screen-scraping).

1. HTTPS-First (balanced) on by default
   http://httponly.example.com/ is mapped (--host-resolver-rules) to a plain-HTTP server on the runner, for every
   port. Chromium first upgrades the navigation to https:// (port 443 -> the same plain-HTTP server -> TLS error).
     * HTTPS-Upgrades only (Chromium default)  -> silent fallback, the HTTP page loads   (marker visible)
     * HTTPS-First balanced (patches/0010)     -> "connection is not secure" interstitial (marker NOT visible)
   example.com is a unique public name, so the balanced mode applies (private IPs / single-label hosts are exempt).

2. Third-party cookies blocked by default
   https://top.example.com/top.html (first party) embeds https://cookie3p.example.org/frame (third party). Both are
   mapped to a local HTTPS server (self-signed; --ignore-certificate-errors for this run only, see
   components/network_session_configurator). The frame response sets `s3p=1; SameSite=None; Secure` and reports
   document.cookie to the top page.
     * allowed (Chromium default) -> frame sees s3p=1
     * blocked (patches/0010)     -> frame sees nothing
   Control: the top page's own first-party cookie must still work (fp=1), so cookies in general are not broken.

The command-line file is honoured because the package is the debug app (see startup_netlog.py); it is removed after.
Usage: advanced_e2e.py --package <pkg> --out <dir> [--devtools http://127.0.0.1:9222]
Prints ADVANCED_E2E PASS / FAIL / NOT_RUN.
"""
import argparse
import http.server
import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shield_e2e import adb, open_internal, page_text, screenshot, targets, internal_text  # noqa: E402
from startup_netlog import CMDLINE_FILE, CMDLINE_JS, resolve_launcher  # noqa: E402

HTTP_PORT, HTTPS_PORT = 8770, 8771
HTTP_HOST, TOP_HOST, THIRD_HOST = "httponly.example.com", "top.example.com", "cookie3p.example.org"
FP_A, FP_B = "fp-a.example.com", "fp-b.example.net"   # two unrelated top-level sites (patches/0011)
# Ad & tracker blocker (patches/0012+0013). The ad/tracker hostnames are real list entries (EasyList ||adnxs.com^,
# EasyPrivacy ||google-analytics.com^$script,third-party, EasyPrivacy ||scorecardresearch.com^$third-party) but are
# mapped to the runner's local server for this browser only -- no request ever leaves the runner.
AD_TOP, AD_CONTROL = "news.example.com", "static.example.org"
AD_HOSTS = ("ib.adnxs.com", "www.google-analytics.com", "sb.scorecardresearch.com")
HTTP_MARKER = "SWIFTRA_HTTPONLY_PAGE_LOADED"
RULES = (f"MAP {HTTP_HOST} 127.0.0.1:{HTTP_PORT},MAP {TOP_HOST} 127.0.0.1:{HTTPS_PORT},"
         f"MAP {THIRD_HOST} 127.0.0.1:{HTTPS_PORT},MAP {FP_A} 127.0.0.1:{HTTPS_PORT},MAP {FP_B} 127.0.0.1:{HTTPS_PORT},"
         + ",".join(f"MAP {h} 127.0.0.1:{HTTPS_PORT}" for h in (AD_TOP, AD_CONTROL) + AD_HOSTS))

TOP_HTML = f"""<!doctype html><meta name="viewport" content="width=device-width"><title>3PC:pending</title>
<h1>Swiftra 3PC test</h1><div id="r"></div>
<script>
let n = 0; const seen = [];
window.addEventListener('message', e => {{
  if (e.origin !== 'https://{THIRD_HOST}') return;
  seen.push(String(e.data)); n++;
  if (n === 1) {{ const f = document.createElement('iframe'); f.src = 'https://{THIRD_HOST}/frame?2'; document.body.appendChild(f); }}
  else {{ document.title = '3PC:done'; document.getElementById('r').textContent = JSON.stringify({{fp: document.cookie, frame: seen}}); }}
}});
const f = document.createElement('iframe'); f.src = 'https://{THIRD_HOST}/frame?1'; document.body.appendChild(f);
</script>"""
FRAME_HTML = "<!doctype html><script>parent.postMessage(document.cookie, '*');</script>"

# Fingerprint probes (patches/0011). Solid fill with a known colour: without the shield every pixel reads back exactly.
FP_JS = r"""
async function h(buf){const d=await crypto.subtle.digest('SHA-256',buf);return [...new Uint8Array(d)].slice(0,8).map(b=>b.toString(16).padStart(2,'0')).join('');}
function dev(d){let n=0,m=0;for(let i=0;i<d.length;i+=4){const e=[Math.abs(d[i]-200),Math.abs(d[i+1]-100),Math.abs(d[i+2]-51)];const x=Math.max(...e);if(x){n++;m=Math.max(m,x);}}return [n,m];}
async function canvasProbe(){
  const c=document.createElement('canvas');c.width=120;c.height=60;const x=c.getContext('2d');
  x.fillStyle='rgb(200,100,51)';x.fillRect(0,0,120,60);
  const [n,m]=dev(x.getImageData(0,0,120,60).data);
  x.font='16px sans-serif';x.fillStyle='#069';x.fillText('Swiftra fp 123',4,30);
  const a=await h(x.getImageData(0,0,120,60).data),b=await h(x.getImageData(0,0,120,60).data);
  const sub=x.getImageData(30,20,10,10).data,full=x.getImageData(0,0,120,60).data;let subok=true;
  for(let y=0;y<10;y++)for(let i=0;i<40;i++)if(sub[y*40+i]!==full[((20+y)*120+30)*4+i])subok=false;
  const img=x.getImageData(0,0,120,60);x.putImageData(img,0,0);const s=await h(x.getImageData(0,0,120,60).data);
  const u1=c.toDataURL(),u2=c.toDataURL();
  return {dev:n,max:m,hash:a,reread_same:a===b,strip_same:s===a,subrect_same:subok,url_same:u1===u2,url_hash:await h(new TextEncoder().encode(u1))};
}
async function webglProbe(){
  const c=document.createElement('canvas');c.width=64;c.height=64;const g=c.getContext('webgl',{preserveDrawingBuffer:true});
  if(!g)return {available:false};
  g.clearColor(200/255,100/255,51/255,1);g.clear(g.COLOR_BUFFER_BIT);
  const p=new Uint8Array(64*64*4);g.readPixels(0,0,64,64,g.RGBA,g.UNSIGNED_BYTE,p);const [n,m]=dev(p);
  const q=new Uint8Array(64*64*4);g.readPixels(0,0,64,64,g.RGBA,g.UNSIGNED_BYTE,q);
  return {available:true,dev:n,max:m,hash:await h(p),reread_same:(await h(q))===(await h(p))};
}
async function audioProbe(){
  try{const ctx=new OfflineAudioContext(1,5000,44100);const o=ctx.createOscillator();o.type='triangle';o.frequency.value=10000;
  const k=ctx.createDynamicsCompressor();o.connect(k);k.connect(ctx.destination);o.start(0);
  const buf=await ctx.startRendering();const d=buf.getChannelData(0);let s=0;for(let i=4500;i<5000;i++)s+=Math.abs(d[i]);return {sum:s.toString()};}
  catch(e){return {error:String(e)};}
}
async function probeAll(){return {canvas:await canvasProbe(),webgl:await webglProbe(),audio:await audioProbe()};}
"""
FP_HTML = ("<!doctype html><meta name=viewport content='width=device-width'><title>FP:pending</title><h1>Swiftra FP test</h1>"
           "<pre id=r></pre><script>" + FP_JS + f"""
(async()=>{{const me=await probeAll();let frame=null;
  window.addEventListener('message',e=>{{if(e.origin==='https://{THIRD_HOST}')frame=e.data;}});
  const f=document.createElement('iframe');f.src='https://{THIRD_HOST}/fpframe';document.body.appendChild(f);
  for(let i=0;i<60&&!frame;i++)await new Promise(r=>setTimeout(r,250));
  document.getElementById('r').textContent=JSON.stringify({{me,frame}});document.title='FP:done';}})();
</script>""")
FPFRAME_HTML = "<!doctype html><script>" + FP_JS + "(async()=>{parent.postMessage((await canvasProbe()).hash,'*');})();</script>"
# Each resource reports load/error; the server log is the ground truth (a blocked request never reaches it).
AD_HTML = ("<!doctype html><meta name=viewport content='width=device-width'><title>AD:pending</title>"
           "<h1>Swiftra ad-block test</h1><pre id=r></pre><script>\n"
           "const res={};let left=0;function done(k,v){res[k]=v;if(--left===0){"
           "document.getElementById('r').textContent=JSON.stringify(res);document.title='AD:done';}}\n"
           "function add(tag,k,url){left++;const e=document.createElement(tag);e.onload=()=>done(k,'loaded');"
           "e.onerror=()=>done(k,'error');e.src=url+(url.includes('?')?'&':'?')+'t='+Date.now();document.body.appendChild(e);}\n"
           f"add('script','first_party','https://{AD_TOP}/first.js');"
           f"add('script','control_third_party','https://{AD_CONTROL}/lib.js');"
           f"add('script','adnxs_script','https://{AD_HOSTS[0]}/ast.js');"
           f"add('img','adnxs_pixel','https://{AD_HOSTS[0]}/px.gif');"
           f"add('script','ga_script','https://{AD_HOSTS[1]}/analytics.js');"
           f"add('script','scorecard_script','https://{AD_HOSTS[2]}/beacon.js');"
           "setTimeout(()=>{if(document.title!=='AD:done'){document.getElementById('r').textContent=JSON.stringify(res);"
           "document.title='AD:done';}},15000);\n</script>")
GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")
FP_RESULT_JS = "(() => ({title: document.title, r: (document.getElementById('r') || {}).textContent || ''}))()"
RESULT_JS = ("(() => ({title: document.title, r: (document.getElementById('r') || {}).textContent || '', "
             "fp: document.cookie}))()")
HFM_JS = ("(() => ({title: document.title, href: location.href, text: (document.body ? document.body.innerText : '')"
          ".slice(0, 600), ids: ['primary-button', 'proceed-link', 'main-message', 'details-button']"
          ".filter(i => document.getElementById(i))}))()")


HITS = []   # (port, host, path) of every plain request the runner-side servers answered


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        HITS.append((self.server.server_port, host, self.path))
        if host == HTTP_HOST:
            body, extra = f"<!doctype html><title>{HTTP_MARKER}</title><h1>{HTTP_MARKER}</h1>", []
        elif host == TOP_HOST and self.path.startswith("/top.html"):
            body, extra = TOP_HTML, [("Set-Cookie", "fp=1; SameSite=Lax; Secure; Path=/")]
        elif host in (FP_A, FP_B) and self.path.startswith("/fp.html"):
            body, extra = FP_HTML, []
        elif host == THIRD_HOST and self.path.startswith("/fpframe"):
            body, extra = FPFRAME_HTML, []
        elif host == THIRD_HOST and self.path.startswith("/frame"):
            body, extra = FRAME_HTML, [("Set-Cookie", "s3p=1; SameSite=None; Secure; Path=/")]
        elif host == AD_TOP and self.path.startswith("/ads.html"):
            body, extra = AD_HTML, []
        elif host in (AD_TOP, AD_CONTROL) + AD_HOSTS and self.path.split("?")[0].endswith(".js"):
            return self._send(b"/* swiftra e2e */", "application/javascript")
        elif host in AD_HOSTS and self.path.split("?")[0].endswith(".gif"):
            return self._send(GIF, "image/gif")
        else:
            self.send_response(404)
            self.end_headers()
            return
        return self._send(body.encode(), "text/html; charset=utf-8", extra)

    def _send(self, data, ctype, extra=()):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)


def start_servers(tmp):
    http_srv = http.server.ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    threading.Thread(target=http_srv.serve_forever, daemon=True).start()
    key, crt = os.path.join(tmp, "k.pem"), os.path.join(tmp, "c.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-keyout", key,
                    "-out", crt, "-subj", f"/CN={TOP_HOST}",
                    "-addext", "subjectAltName=" + ",".join(
                        f"DNS:{h}" for h in (TOP_HOST, THIRD_HOST, FP_A, FP_B, AD_TOP, AD_CONTROL) + AD_HOSTS)],
                   check=True, capture_output=True, timeout=60)
    https_srv = http.server.ThreadingHTTPServer(("127.0.0.1", HTTPS_PORT), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    https_srv.socket = ctx.wrap_socket(https_srv.socket, server_side=True)
    threading.Thread(target=https_srv.serve_forever, daemon=True).start()
    return http_srv, https_srv


def find_target(substr):
    for t in targets(DEVTOOLS):
        if t.get("type") == "page" and substr in t.get("url", ""):
            return t
    return None


def eval_on(substr, js, wait=20, until=None):
    t0, last = time.time(), None
    while time.time() - t0 < wait:
        t = find_target(substr)
        if t:
            v = page_text(DEVTOOLS, t["url"], js)
            if isinstance(v, dict):
                last = dict(v, target_url=t["url"])
                if until is None or until(last):
                    return last
        time.sleep(1)
    return last


DIALOG_TEXTS = ("support a secure connection", "connection is not secure", "your connection is not private")


def ui_dialog_text():
    """The Android HTTPS-First warning is a native dialog (kHttpsFirstDialogUi), invisible to page JS: read the UI tree
    (same dump method as shield_e2e.py)."""
    adb("shell", "uiautomator", "dump", "/sdcard/adv_ui.xml", timeout=40)
    xml = adb("shell", "cat", "/sdcard/adv_ui.xml").lower()
    return next((t for t in DIALOG_TEXTS if t in xml), "")


def fp_verdict(a, b):
    """a, b = parsed results for two unrelated top-level sites. Returns (verdict, reasons)."""
    if not a or not b:
        return "no_result", ["missing"]
    reasons = []
    ca, cb = a["me"]["canvas"], b["me"]["canvas"]
    if ca["dev"] == 0 and cb["dev"] == 0 and ca["hash"] == cb["hash"]:
        return "no_shield", ["canvas exact and identical on both sites"]
    for name, c in (("A", ca), ("B", cb)):
        if not (c["dev"] > 0 and c["max"] == 1):
            reasons.append(f"canvas {name}: dev={c['dev']} max={c['max']}")
        for k in ("reread_same", "strip_same", "subrect_same", "url_same"):
            if not c.get(k):
                reasons.append(f"canvas {name}: {k} false")
    if ca["hash"] == cb["hash"] or ca["url_hash"] == cb["url_hash"]:
        reasons.append("canvas hash same on both sites")
    wa, wb = a["me"]["webgl"], b["me"]["webgl"]
    if wa.get("available") and wb.get("available"):
        if not (wa["dev"] > 0 and wa["max"] == 1 and wa["reread_same"]):
            reasons.append(f"webgl A: dev={wa['dev']} max={wa['max']} reread={wa['reread_same']}")
        if wa["hash"] == wb["hash"]:
            reasons.append("webgl hash same on both sites")
    aa, ab = a["me"]["audio"], b["me"]["audio"]
    if "sum" in aa and "sum" in ab and aa["sum"] == ab["sum"]:
        reasons.append("audio sum same on both sites")
    if a.get("frame") and a.get("frame") == b.get("frame"):
        reasons.append("same third-party iframe fingerprint under both sites (linkable)")
    return ("shielded" if not reasons else "partial"), reasons


def ad_hits(since=0):
    """Server hits per ad/tracker host and for the controls, counting only requests after index `since` of HITS."""
    out = {h: 0 for h in AD_HOSTS + (AD_TOP + "/first.js", AD_CONTROL)}
    for port, host, path in HITS[since:]:
        if host in AD_HOSTS:
            out[host] += 1
        elif host == AD_TOP and path.startswith("/first.js"):
            out[AD_TOP + "/first.js"] += 1
        elif host == AD_CONTROL:
            out[AD_CONTROL] += 1
    return out


def ad_verdict(hits, page):
    """blocked = every ad/tracker host got 0 requests while both controls loaded; no_blocker = all ad hosts were hit."""
    if not page or page.get("title") != "AD:done":
        return "no_result"
    if hits.get(AD_TOP + "/first.js", 0) == 0 or hits.get(AD_CONTROL, 0) == 0:
        return "controls_broken"
    ad = [hits.get(h, 0) for h in AD_HOSTS]
    if all(n == 0 for n in ad):
        return "blocked"
    return "no_blocker" if all(n > 0 for n in ad) else "partial"


CREDITS_JS = ("(() => {const t = document.body ? document.body.innerText : ''; return {len: t.length, "
              "sample: t.includes('This is sample credits page'), adblock: t.includes('Swiftra Ad & Tracker Blocker'), "
              "boringssl: /BoringSSL/i.test(t), entries: document.querySelectorAll('.product').length}})()")


def credits_verdict(c):
    """chrome://credits must be the generated notices page (patches/args.gn generate_about_credits) with the
    ad-block list attribution; non-official builds otherwise ship components/resources/sample_credits.html."""
    if not c or not c.get("len"):
        return "no_page"
    if c.get("sample"):
        return "sample_page"
    if c.get("boringssl") and c.get("adblock") and c.get("entries", 0) >= 100:
        return "complete"
    return "incomplete"


def hfm_verdict(r, http_hits=None, dialog=""):
    """interstitial = warning page rendered; blocked_no_http = error page and the plain-HTTP page was never fetched
    (same security outcome; desktop headless renders the HFM interstitial as an empty chrome-error page)."""
    if not r:
        return "no_page"
    text = (r.get("title", "") + " " + r.get("text", ""))
    if HTTP_MARKER in text or http_hits:
        return "http_loaded_silently"
    if dialog:
        return "warning_dialog"
    if r.get("ids") or "not secure" in text.lower() or "secure connection" in text.lower():
        return "interstitial"
    if str(r.get("href", "")).startswith("chrome-error://") and http_hits == 0:
        return "blocked_no_http"
    return "unknown"


def http_hits():
    return sum(1 for port, host, _ in HITS if port == HTTP_PORT and host == HTTP_HOST)


def tpc_verdict(r):
    if not r or r.get("title") != "3PC:done":
        return "no_result"
    try:
        d = json.loads(r.get("r") or "{}")
    except ValueError:
        return "no_result"
    frame = " ".join(d.get("frame", []))
    fp_ok = "fp=1" in (d.get("fp") or "")
    if not fp_ok:
        return "first_party_cookie_broken"
    return "third_party_allowed" if "s3p=1" in frame else "third_party_blocked"


DEVTOOLS = "http://127.0.0.1:9222"


def main():
    global DEVTOOLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--devtools", default=DEVTOOLS)
    ap.add_argument("--socket", default=os.environ.get("SOCK", "chrome_devtools_remote"))
    a = ap.parse_args()
    DEVTOOLS = a.devtools
    os.makedirs(a.out, exist_ok=True)
    pkg, res = a.package, {"package": a.package, "rules": RULES}
    tmp = tempfile.mkdtemp()
    start_servers(tmp)
    flags = f'_ --host-resolver-rules="{RULES}" --ignore-certificate-errors'
    comp = resolve_launcher(pkg)
    try:
        adb("shell", "am", "force-stop", pkg)
        if adb("shell", "settings", "get", "global", "adb_enabled").strip() != "1":
            adb("shell", "settings", "put", "global", "adb_enabled", "1")
        adb("shell", "am", "set-debug-app", "--persistent", pkg)
        adb("shell", f"echo '{flags}' > {CMDLINE_FILE} && chmod 644 {CMDLINE_FILE}")
        for p in (HTTP_PORT, HTTPS_PORT):
            adb("reverse", f"tcp:{p}", f"tcp:{p}")
        adb("shell", "am", "start", "-W", "-n", comp, timeout=60) if comp else adb(
            "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(8)
        adb("forward", "tcp:9222", f"localabstract:{a.socket}")
        time.sleep(2)
        res["version_open"] = open_internal(DEVTOOLS, "chrome://version/")
        time.sleep(3)
        cl = internal_text(DEVTOOLS, "chrome://version", CMDLINE_JS) or ""
        res["flags_applied"] = "--host-resolver-rules" in cl
        res["command_line"] = cl[:500]
        if not res["flags_applied"]:
            res["verdict"] = "not_run"
        else:
            # 1. HTTPS-First
            res["hfm_open"] = open_internal(DEVTOOLS, f"http://{HTTP_HOST}/")
            r = eval_on(HTTP_HOST, HFM_JS, wait=25,
                        until=lambda x: hfm_verdict(x, http_hits()) in ("interstitial", "http_loaded_silently"))
            time.sleep(4)   # a late silent fallback must not be missed
            r = eval_on(HTTP_HOST, HFM_JS, wait=5) or r
            res["hfm_page"], res["hfm_http_hits"] = r, http_hits()
            res["hfm_dialog_text"] = ui_dialog_text()
            res["hfm"] = hfm_verdict(r, res["hfm_http_hits"], res["hfm_dialog_text"])
            screenshot(os.path.join(a.out, 'hfm.png'))
            # 2. third-party cookies
            res["tpc_open"] = open_internal(DEVTOOLS, f"https://{TOP_HOST}/top.html")
            r = eval_on(TOP_HOST, RESULT_JS, wait=25, until=lambda x: x.get("title") == "3PC:done")
            res["tpc_page"] = r
            res["tpc"] = tpc_verdict(r)
            screenshot(os.path.join(a.out, 'tpc.png'))
            # 3. fingerprint shield (patches/0011): same probes on two unrelated top-level sites
            fp = {}
            for host in (FP_A, FP_B):
                res[f"fp_open_{host}"] = open_internal(DEVTOOLS, f"https://{host}/fp.html")
                r = eval_on(host, FP_RESULT_JS, wait=40, until=lambda x: x.get("title") == "FP:done")
                try:
                    fp[host] = json.loads((r or {}).get("r") or "null")
                except ValueError:
                    fp[host] = None
                screenshot(os.path.join(a.out, host + '.png'))
            res["fp"] = fp
            res["fp_verdict"], res["fp_reasons"] = fp_verdict(fp.get(FP_A), fp.get(FP_B))
            # 4. ad & tracker blocker (patches/0012+0013). The bundled ruleset is indexed in the background after
            # startup, so a page loaded before it is published is unfiltered: up to 3 attempts, all recorded.
            res["ad_attempts"] = []
            for attempt in range(3):
                since = len(HITS)
                res["ad_open"] = open_internal(DEVTOOLS, f"https://{AD_TOP}/ads.html?a={attempt}")
                r = eval_on(f"{AD_TOP}/ads.html?a={attempt}", FP_RESULT_JS, wait=30,
                            until=lambda x: x.get("title") == "AD:done")
                time.sleep(2)
                hits = ad_hits(since)
                v = ad_verdict(hits, r)
                res["ad_attempts"].append({"attempt": attempt, "verdict": v, "hits": hits,
                                           "page": (r or {}).get("r", "")[:400]})
                if v in ("blocked", "controls_broken"):
                    break
                time.sleep(10)
            res["ad_verdict"] = res["ad_attempts"][-1]["verdict"]
            # 5. licence notices + list attribution (chrome://credits)
            res["credits_open"] = open_internal(DEVTOOLS, "chrome://credits/")
            time.sleep(4)
            res["credits"] = internal_text(DEVTOOLS, "chrome://credits", CREDITS_JS)
            res["credits_verdict"] = credits_verdict(res["credits"])
            screenshot(os.path.join(a.out, 'adblock.png'))
            res["server_hits"] = HITS[:60]
            ok = res["hfm"] in ("warning_dialog", "interstitial", "blocked_no_http") and res["tpc"] == "third_party_blocked"
            res["verdict"] = "pass" if ok else "fail"
    finally:
        adb("shell", "rm", "-f", CMDLINE_FILE)
        adb("shell", "am", "clear-debug-app")
        adb("shell", "am", "force-stop", pkg)
    json.dump(res, open(os.path.join(a.out, "advanced_e2e.json"), "w"), indent=1, ensure_ascii=False)
    print("advanced e2e:", json.dumps({k: v for k, v in res.items() if k != "command_line"}, ensure_ascii=False)[:3000])
    print("ADVANCED_E2E", {"pass": "PASS", "fail": "FAIL"}.get(res["verdict"], "NOT_RUN"),
          f"hfm={res.get('hfm')} tpc={res.get('tpc')}")
    fpv = res.get("fp_verdict")
    print("FINGERPRINT_E2E", {"shielded": "PASS", None: "NOT_RUN", "no_result": "NOT_RUN"}.get(fpv, "FAIL"),
          f"verdict={fpv} reasons={res.get('fp_reasons')}")
    crv = res.get("credits_verdict")
    print("CREDITS_E2E", {"complete": "PASS", None: "NOT_RUN", "no_page": "NOT_RUN"}.get(crv, "FAIL"),
          f"verdict={crv} info={res.get('credits')}")
    adv = res.get("ad_verdict")
    print("ADBLOCK_E2E", {"blocked": "PASS", None: "NOT_RUN", "no_result": "NOT_RUN"}.get(adv, "FAIL"),
          f"verdict={adv} attempts={len(res.get('ad_attempts', []))}")
    return 1 if res["verdict"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
