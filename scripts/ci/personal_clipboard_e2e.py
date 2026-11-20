#!/usr/bin/env python3
"""PERSONAL_CLIP: does text copied inside the personal browser reach the SYSTEM clipboard? (real Android runtime)

A CI-only helper app (tools/clip_helper) is the observer: it is launched in the foreground and logs what Android's
system ClipboardManager holds. Synthetic canary tokens, loopback only, no account, no real site.
Every line: `PERSONAL_CLIP <id> PASS|FAIL|NOT_RUN <detail>`; NOT_RUN = could not be measured (never a pass).
Exit 1 on any FAIL, 2 on harness error.

  K00 control      : helper can set + read a canary on the system clipboard (otherwise the rest is NOT_RUN)
  K01 web_copy     : Ctrl+C on web-page text must NOT replace the system clipboard
  K02 web_paste    : the page must NOT receive the system clipboard text on Ctrl+V
  K03 urlbar_copy  : copying text typed in the NATIVE URL bar must NOT reach the system clipboard
  K04 find_in_page : same for the native Find-in-page text field (a leak here = FAIL; unproven = NOT_RUN)
  X01 settings_field: PROBE (never gates, never FAIL): the Settings > Homepage custom-address EditText, i.e. a native
                      field that 0109 does NOT patch. Reported as LEAK / CONTAINED / NOT_RUN to MEASURE the audit gap.
"""
import argparse
import http.server
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import personal_e2e as P  # noqa: E402

PORT = P.PORT
HELPER = "com.swiftra.cliphelper"
REPORTS = []
TOKEN = {"v": ""}

PAGE = """<!doctype html><meta name=viewport content="width=device-width"><title>clip</title>
<body style="margin:8px"><textarea id=a rows=3 autofocus style="width:94vw;font-size:30px">web_{t}</textarea><br>
<textarea id=b rows=3 style="width:94vw;font-size:30px"></textarea>
<script>
const r=(s,v)=>fetch('/report?step='+s+'&v='+encodeURIComponent(v||''));
const sel=()=>{{const e=document.activeElement;return (e&&e.value!==undefined)?e.value.substring(e.selectionStart,e.selectionEnd):String(getSelection())}};
document.addEventListener('copy',()=>r('copy',sel()));
document.addEventListener('paste',e=>{{let t='';try{{t=e.clipboardData.getData('text/plain')}}catch(x){{}};r('paste',t)}});
document.getElementById('b').addEventListener('input',e=>r('b',e.target.value));
addEventListener('load',()=>r('ready',document.activeElement&&document.activeElement.id));
</script>"""


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/report":
            REPORTS.append({k: v[0] for k, v in q.items()})
            body, ct = b"ok", "text/plain"
        else:
            body, ct = PAGE.format(t=TOKEN["v"]).encode(), "text/html"
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


# ---------------------------------------------------------------- pure helpers (host-tested)
def parse_helper_get(logcat):
    """Last `CLIPHELPER GET` line -> ('none'|'text'|'error'|'missing', text)."""
    last = None
    for line in logcat.splitlines():
        if "CLIPHELPER" in line and (" GET " in line or "ERR " in line or "SET_OK" in line):
            last = line
    if last is None:
        return "missing", ""
    if "ERR " in last:
        return "error", last.split("ERR ", 1)[1][:120]
    m = re.search(r"GET text=\[(.*)\]\s*$", last)
    if m:
        return "text", m.group(1)
    if "GET none" in last:
        return "none", ""
    return "missing", ""


def classify_copy(sys_kind, sys_text, ctl, copied_marker, copy_observed):
    """K01/K03: PASS only if the copy demonstrably happened and the system clipboard still holds the control text."""
    if sys_kind != "text":
        return "NOT_RUN", f"helper could not read the system clipboard ({sys_kind})"
    if copied_marker in sys_text:
        return "FAIL", f"the copied canary reached the SYSTEM clipboard: [{sys_text}]"
    if not copy_observed:
        return "NOT_RUN", f"no in-browser evidence that the copy happened; system clipboard=[{sys_text}]"
    if sys_text == ctl:
        return "PASS", "copy happened inside the browser; system clipboard unchanged (still the control text)"
    return "FAIL", f"system clipboard changed to an unexpected value [{sys_text}]"


def classify_paste(page_values, ctl, paste_event_seen):
    joined = " ".join(page_values)
    if ctl in joined:
        return "FAIL", f"page received the system clipboard text: {page_values}"
    if not paste_event_seen:
        return "NOT_RUN", "no paste event reached the page"
    return "PASS", f"paste event reached the page without the system clipboard text: {page_values}"


def find_edit_text(xml):
    """Bounds of the first android.widget.EditText node in a uiautomator dump, or None."""
    for m in re.finditer(r"<node [^>]*>", xml):
        n = m.group(0)
        if 'class="android.widget.EditText"' in n:
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n)
            if b:
                return list(map(int, b.groups()))
    return None


def edit_text_value(xml):
    """text attribute of the first android.widget.EditText node (diagnostics for the X01 probe)."""
    for m in re.finditer(r"<node [^>]*>", xml):
        n = m.group(0)
        if 'class="android.widget.EditText"' in n:
            t = re.search(r'\btext="([^"]*)"', n)
            return t.group(1) if t else None
    return None


def summarize(results):
    c = {"PASS": 0, "FAIL": 0, "NOT_RUN": 0}
    for r in results:
        c[r["status"]] += 1
    return c


# ---------------------------------------------------------------- device helpers
def combo(*codes):
    P.sh("input keycombination " + " ".join(str(c) for c in codes))


CTRL, KA, KC, KV, KX = 113, 29, 31, 50, 52


def helper(mode, text=None):
    P.adb("logcat", "-c")
    args = ["shell", "am", "start", "-W", "-n", f"{HELPER}/.Main", "--es", "mode", mode]
    if text is not None:
        args += ["--es", "text", text]
    P.adb(*args, timeout=60)
    t0 = time.time()
    while time.time() - t0 < 15:
        out = P.adb("logcat", "-d", "-s", "CLIPHELPER:I")
        kind, txt = parse_helper_get(out)
        if kind != "missing":
            return kind, txt
        time.sleep(1)
    return "missing", ""


def wait_for(step, since, secs=20):
    t0 = time.time()
    while time.time() - t0 < secs:
        got = [r for r in REPORTS[since:] if r.get("step") == step]
        if got:
            return got[-1]
        time.sleep(1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pkg = a.package
    os.makedirs(a.out, exist_ok=True)
    TOKEN["v"] = secrets.token_hex(8)
    tok = TOKEN["v"]
    ctl = "ctl_" + tok
    results = []
    probes = []

    def res_probe(cid, status, detail=""):
        probes.append({"id": cid, "status": status, "detail": detail})
        print(f"PERSONAL_CLIP_PROBE {cid} {status} {detail}", flush=True)

    def res(cid, status, detail=""):
        results.append({"id": cid, "status": status, "detail": detail})
        print(f"PERSONAL_CLIP {cid} {status} {detail}", flush=True)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    P.go_root()
    P.reverse()
    url = f"http://127.0.0.1:{PORT}/clip"
    print(f"PERSONAL_CLIP env package={pkg} abi={P.sh('getprop ro.product.cpu.abi')} sdk={P.sh('getprop ro.build.version.sdk')}", flush=True)
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from ui_capture import Device, launch, wait_ready  # noqa: E402
        dev = Device(pkg, a.out, lambda line: print("PERSONAL_CLIP_UI", line, flush=True))
        P.adb("shell", "am", "force-stop", pkg)
        launch(dev)
        wait_ready(dev, seconds=180)

        # K00 control
        k, t = helper("set", ctl)
        k2, t2 = helper("get")
        control_ok = (k2 == "text" and t2 == ctl)
        res("K00_control", "PASS" if control_ok else "NOT_RUN", f"set={k} get={k2}[{t2}]")

        # K01 web copy (up to 3 attempts: the emulator is slow; every attempt taps into the textarea first)
        w, h = 1080, 2400
        m = re.search(r"(\d+)x(\d+)", P.sh("wm size"))
        if m:
            w, h = int(m.group(1)), int(m.group(2))
        ax, ay, by = w // 2, int(h * 0.17), int(h * 0.31)   # textarea a / b centres (page starts under the toolbar)
        observed, cp, rdy = False, None, None
        for attempt in range(3):
            since = len(REPORTS)
            P.open_url(pkg, url)
            rdy = wait_for("ready", since, 40)
            time.sleep(3)
            P.sh(f"input tap {ax} {ay}")
            time.sleep(1)
            combo(CTRL, KA)
            time.sleep(1)
            combo(CTRL, KC)
            cp = wait_for("copy", since, 8)
            observed = bool(cp) and tok in (cp.get("v") or "")
            if observed:
                break
        sk, st = helper("get")
        if not control_ok:
            res("K01_web_copy", "NOT_RUN", "control failed")
        else:
            s_, d = classify_copy(sk, st, ctl, "web_" + tok, observed)
            res("K01_web_copy", s_, d + f" attempts={attempt + 1} page_ready={bool(rdy)} copy_event={cp}")

        # K02 web paste (system clipboard holds ctl; the browser clipboard holds web_<tok> from K01)
        helper("set", ctl)
        vals, seen = [], False
        for attempt in range(3):
            since = len(REPORTS)
            P.open_url(pkg, url)
            wait_for("ready", since, 40)
            time.sleep(3)
            P.sh(f"input tap {ax} {by}")
            time.sleep(1)
            combo(CTRL, KV)
            time.sleep(3)
            vals = [r.get("v", "") for r in REPORTS[since:] if r.get("step") in ("paste", "b")]
            seen = any(r.get("step") == "paste" for r in REPORTS[since:])
            if seen:
                break
        if not control_ok:
            res("K02_web_paste", "NOT_RUN", "control failed")
        else:
            s_, d = classify_paste(vals, ctl, seen)
            res("K02_web_paste", s_, d + f" attempts={attempt + 1}")

        # K03 native URL bar copy
        helper("set", ctl)
        P.adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", f"http://127.0.0.1:{PORT}/plain", "-p", pkg, timeout=60)
        time.sleep(4)
        xml = ""
        node = None
        for _ in range(4):
            xml = dev.dump() if hasattr(dev, "dump") else ""
            m = re.search(r'<node [^>]*resource-id="[^"]*url_bar"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
            if m:
                node = list(map(int, m.groups()))
                break
            time.sleep(2)
        if not node:
            res("K03_urlbar_copy", "NOT_RUN", "url_bar node not found in UI dump")
        else:
            P.sh(f"input tap {(node[0]+node[2])//2} {(node[1]+node[3])//2}")
            time.sleep(2)
            P.sh("input keyevent KEYCODE_MOVE_END")
            combo(CTRL, KA)
            P.sh("input keyevent 67")  # DEL
            P.sh(f"input text omni_{tok}")
            time.sleep(1)
            combo(CTRL, KA)
            combo(CTRL, KC)
            time.sleep(1)
            P.sh("input keyevent 67")
            combo(CTRL, KV)
            time.sleep(2)
            xml2 = dev.dump() if hasattr(dev, "dump") else ""
            pasted_back = ("omni_" + tok) in xml2
            P.sh("input keyevent KEYCODE_BACK")
            sk, st = helper("get")
            if not control_ok:
                res("K03_urlbar_copy", "NOT_RUN", "control failed")
            else:
                s, d = classify_copy(sk, st, ctl, "omni_" + tok, pasted_back)
                res("K03_urlbar_copy", s, d + f" pasted_back_into_url_bar={pasted_back}")

        # K04 find-in-page text field (native EditText inside the find toolbar)
        try:
            helper("set", ctl)
            P.adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", f"http://127.0.0.1:{PORT}/plain", "-p", pkg, timeout=60)
            time.sleep(4)
            opened = bool(dev.tap(r"(?i)^more options$|menu_button", wait=2.0, tries=3)) and bool(dev.tap(r"(?i)find in page", wait=2.0, tries=3))
            if not opened:
                res("K04_find_in_page_copy", "NOT_RUN", "could not open Find in page through the UI")
            else:
                P.sh(f"input text find_{tok}")
                time.sleep(1)
                combo(CTRL, KA)
                combo(CTRL, KC)
                time.sleep(1)
                P.sh("input keyevent 67")
                combo(CTRL, KV)
                time.sleep(2)
                pasted_back = ("find_" + tok) in (dev.dump() or "")
                sk, st = helper("get")
                if not control_ok:
                    res("K04_find_in_page_copy", "NOT_RUN", "control failed")
                else:
                    s, d = classify_copy(sk, st, ctl, "find_" + tok, pasted_back)
                    res("K04_find_in_page_copy", s, d + f" pasted_back_into_find_field={pasted_back}")
        except Exception as e:  # noqa: BLE001
            res("K04_find_in_page_copy", "NOT_RUN", "harness: " + repr(e)[:160])

        # X01 probe: a native Settings text field that no patch touches (measures the unaudited gap, never gates)
        try:
            helper("set", ctl)
            P.adb("shell", "am", "start", "-W", "-n", f"{pkg}/org.chromium.chrome.browser.settings.SettingsActivity",
                  "--es", "show_fragment", "org.chromium.chrome.browser.homepage.settings.HomepageSettings", timeout=60)
            time.sleep(4)
            edit = None
            for _ in range(3):
                x = dev.dump() or ""
                edit = find_edit_text(x)
                if edit:
                    break
                dev.tap(r"(?i)custom|enter custom web address", wait=2.0, tries=1)   # select the custom-address radio
                time.sleep(2)
            if not edit:
                res_probe("X01_settings_field", "NOT_RUN", "no EditText found on the Homepage settings page")
            else:
                P.sh(f"input tap {(edit[0]+edit[2])//2} {(edit[1]+edit[3])//2}")
                time.sleep(1)
                combo(CTRL, KA)
                P.sh("input keyevent 67")
                P.sh(f"input text set_{tok}")
                time.sleep(1)
                combo(CTRL, KA)
                combo(CTRL, KC)
                time.sleep(1)
                _, st_copy = helper("get")   # the copy step alone: this is the exact path that LEAKED on 6589062
                # native paste reads the SYSTEM clipboard, so pasting cannot show a contained copy. Use CUT instead:
                # it provably ran when the typed canary disappears from the field; the system clipboard must stay
                # the control text. (An unpatched field would put the canary on the system clipboard = LEAK.)
                before = edit_text_value(dev.dump() or "")
                P.adb("logcat", "-c")
                combo(CTRL, KA)
                combo(CTRL, KX)
                time.sleep(1.5)
                after = edit_text_value(dev.dump() or "")
                # The Settings field rewrites its text (http://.../), so the field content is no proof. The patched
                # handler logs the LENGTH only (tag SwiftraClip) when it handled copy/cut: that proves the action ran.
                log = P.adb("logcat", "-d", "-s", "SwiftraClip:I", timeout=30)
                typed_back = "contained edit-text copy/cut" in log   # name kept: True = the patched handler ran
                print(f"PERSONAL_CLIP_PROBE X01 diag field_before={before!r} field_after={after!r} handler_log={typed_back}", flush=True)
                sk, st = helper("get")
                if not control_ok or sk != "text":
                    res_probe("X01_settings_field", "NOT_RUN", f"control or helper unavailable ({sk})")
                elif ("set_" + tok) in st or ("set_" + tok) in (st_copy or ""):
                    res_probe("X01_settings_field", "LEAK", f"the canary reached the SYSTEM clipboard: [{st}]")
                elif typed_back and st == ctl:
                    res_probe("X01_settings_field", "CONTAINED", "the contained handler ran (SwiftraClip log) and the system clipboard is unchanged")
                else:
                    res_probe("X01_settings_field", "NOT_RUN", f"handler not demonstrated (handler_log={typed_back}) system=[{st}]")
        except Exception as e:  # noqa: BLE001
            res_probe("X01_settings_field", "NOT_RUN", "harness: " + repr(e)[:160])
    except Exception as e:  # noqa: BLE001
        print("PERSONAL_CLIP harness_error", repr(e)[:300], flush=True)
        return 2
    finally:
        try:
            open(os.path.join(a.out, "logcat_tail.txt"), "w").write(P.adb("logcat", "-d", "-t", "3000", timeout=60))
        except Exception:  # noqa: BLE001
            pass
    c = summarize(results)
    json.dump({"package": pkg, "results": results, "probes": probes, "summary": c}, open(os.path.join(a.out, "personal_clip.json"), "w"), indent=1)
    print(f"PERSONAL_CLIP_SUMMARY pass={c['PASS']} fail={c['FAIL']} not_run={c['NOT_RUN']}", flush=True)
    return 1 if c["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
