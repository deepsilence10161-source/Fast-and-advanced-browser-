#!/usr/bin/env python3
"""असली touch scroll के दौरान web page का frame pacing (CDP + adb input swipe)।

क्यों: Chromium web content को अपने compositor (SurfaceView/viz) से draw करता है, इसलिए
`dumpsys gfxinfo <pkg>` (HWUI) में web scroll के frames नहीं गिने जाते (x64 run 38904972738: "no frames")।
तरीका: example.org (पहले से खुला tab) में लंबा content जोड़ना + requestAnimationFrame recorder;
फिर adb से असली touch swipes (input pipeline -> compositor scroll); फिर frame intervals पढ़ना।
सीमा: software GPU (emulator swiftshader / Redroid guest) पर संख्याएँ असली phone जैसी नहीं।
Usage: scroll_jank.py --out out/T/scroll_jank [--devtools http://127.0.0.1:9222] [--match example.org]
Exit: 0 = scroll हुआ और frames मापे गए; 1 = scroll/frames नहीं; 2 = harness त्रुटि।
"""
import argparse, json, statistics, subprocess, sys, time, urllib.request

try:
    import websocket
except ImportError:  # pragma: no cover
    websocket = None

SETUP_JS = r"""
(() => {
  if (!window.__sj) {
    const box = document.createElement('div'); box.id = '__sj_box';
    for (let i = 0; i < 400; i++) {
      const p = document.createElement('p');
      p.textContent = 'Scroll test paragraph ' + i + ' — the quick brown fox jumps over the lazy dog. ' .repeat(3);
      p.style.cssText = 'margin:12px 16px;padding:10px;border-radius:8px;background:hsl(' + (i * 37 % 360) + ',60%,92%)';
      box.appendChild(p);
    }
    document.body.appendChild(box);
    window.__sj = {frames: [], scrolls: [], maxY: 0, rec: false};
    const f = t => { if (window.__sj.rec) window.__sj.frames.push(t); requestAnimationFrame(f); };
    requestAnimationFrame(f);
    addEventListener('scroll', () => { const s = window.__sj; if (s.rec) { s.scrolls.push(performance.now()); s.maxY = Math.max(s.maxY, scrollY); } }, {passive: true});
  }
  scrollTo(0, 0); window.__sj.frames = []; window.__sj.scrolls = []; window.__sj.maxY = 0; window.__sj.rec = true;
  return document.documentElement.scrollHeight;
})()
"""
READ_JS = "(() => { const s = window.__sj; s.rec = false; return JSON.stringify({frames: s.frames, scrolls: s.scrolls, maxY: s.maxY, dpr: devicePixelRatio, ih: innerHeight}); })()"


def adb(*a, timeout=30):
    return subprocess.run(["adb", *a], capture_output=True, text=True, timeout=timeout).stdout.replace("\r", "")


def screen_size():
    out = adb("shell", "wm size")
    for line in reversed(out.splitlines()):          # "Override size" हो तो वही
        if "size:" in line:
            w, h = line.split(":")[1].strip().split("x"); return int(w), int(h)
    return 1080, 2400


def analyse(frames, scrolls):
    """scroll window (पहला -> आखिरी scroll event, +100ms) के भीतर के frame intervals।"""
    if len(scrolls) < 2 or len(frames) < 3:
        return None
    t0, t1 = scrolls[0], scrolls[-1] + 100
    fr = [t for t in frames if t0 <= t <= t1]
    iv = [b - a for a, b in zip(fr, fr[1:]) if b > a]
    if len(iv) < 10:
        return None
    iv_sorted = sorted(iv)
    pct = lambda p: round(iv_sorted[min(len(iv_sorted) - 1, int(p / 100 * len(iv_sorted)))], 2)
    vsync = min(statistics.median(iv), 1000 / 60 + 0.5)            # device refresh (≤60Hz मानकर)
    janky = [x for x in iv if x > 1.5 * vsync]
    dur = (fr[-1] - fr[0]) / 1000
    return {"frames": len(fr), "duration_s": round(dur, 2), "fps": round((len(fr) - 1) / dur, 1) if dur else 0,
            "p50_ms": pct(50), "p90_ms": pct(90), "p99_ms": pct(99), "max_ms": round(max(iv), 2),
            "vsync_ms": round(vsync, 2), "janky_frames": len(janky), "janky_pct": round(100 * len(janky) / len(iv), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--devtools", default="http://127.0.0.1:9222")
    ap.add_argument("--match", default="example.org")
    ap.add_argument("--out", required=True)
    ap.add_argument("--swipes", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=60)
    a = ap.parse_args()
    res = {"method": "rAF intervals during real adb touch swipes (CDP)", "match": a.match}
    if websocket is None:
        res["harness_error"] = "websocket-client missing"; json.dump(res, open(a.out + ".json", "w"), indent=1); print(res["harness_error"]); return 2
    page, err, dl = None, None, time.time() + a.timeout
    while time.time() < dl and not page:
        try:
            tl = json.load(urllib.request.urlopen(a.devtools + "/json/list", timeout=5))
            page = next((t for t in tl if t.get("type") == "page" and a.match in t.get("url", "")), None)
        except Exception as e:
            err = e
        if not page: time.sleep(2)
    if not page:
        res["harness_error"] = f"page not found: {err}"; json.dump(res, open(a.out + ".json", "w"), indent=1); print(res["harness_error"]); return 2
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
    mid = [0]

    def ev(expr):
        mid[0] += 1; ws.send(json.dumps({"id": mid[0], "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid[0]: return m.get("result", {}).get("result", {}).get("value")

    res["scroll_height_px"] = ev(SETUP_JS); time.sleep(1)
    w, h = screen_size(); x = w // 2; y_lo, y_hi = int(h * 0.78), int(h * 0.30)
    res["screen"] = f"{w}x{h}"
    for i in range(a.swipes):                              # ज़्यादातर नीचे, बीच-बीच में ऊपर — असली पढ़ने जैसा
        if i % 4 == 3: adb("shell", f"input swipe {x} {y_hi} {x} {y_lo} 250")
        else: adb("shell", f"input swipe {x} {y_lo} {x} {y_hi} 250")
        time.sleep(0.35)
    time.sleep(1)
    raw = json.loads(ev(READ_JS) or "{}")
    ws.close()
    res["scroll_events"] = len(raw.get("scrolls", [])); res["max_scroll_y_css_px"] = raw.get("maxY", 0)
    res["metrics"] = analyse(raw.get("frames", []), raw.get("scrolls", []))
    json.dump(res, open(a.out + ".json", "w"), indent=1)
    m = res["metrics"]
    ok = res["scroll_events"] > 0 and res["max_scroll_y_css_px"] > 500 and m is not None
    print(("OK " if ok else "BAD ") + json.dumps({k: res[k] for k in ("scroll_events", "max_scroll_y_css_px", "screen")}) + " " + json.dumps(m))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
