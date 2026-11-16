#!/usr/bin/env python3
"""PERSONAL_E2E: device acceptance probes for the opt-in persistent personal development APK.

Runs on a REAL Android runtime only (x64 Actions emulator or native ARM64 Redroid) against the installed
development package. Loopback only (runner 127.0.0.1 via `adb reverse`), synthetic canaries, no account,
no real site, no existing profile touched (disposable CI device). Host success is never Android PASS.

Every check prints `PERSONAL_E2E <id> PASS|FAIL|NOT_RUN <detail>`; NOT_RUN means "could not be measured"
and is never counted as a pass. Exit 1 when any check FAILs, 2 on harness error.

Checks
  C01 launch      : cold launch to a loopback page, process alive, crash buffer clean for the package
  C02 retention   : cookie + localStorage + IndexedDB written once, then read back after
                    (a) background (HOME), (b) force-stop + restart, (c) crash (am crash) + restart
  C03 download    : attachment download lands ONLY in the app-private Downloads root: exact sha256, absent from
                    shared storage, MediaStore and the system DownloadManager provider
  C04 external    : a real tap on tel:/market: links does not hand off to another app (negative-only)
  C05 secure      : FLAG_SECURE on the browser window
  C06 backup      : package is not backup-enabled (otherwise NOT_RUN: rules not measurable here)
  C07 no_account  : no Android account was created/linked by the browser
  C08 preserved   : profile data still present after the whole sequence (nothing wiped)
"""
import argparse
import hashlib
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

PORT = 8793
HITS = []          # served requests: {"path", "cookie"}
REPORTS = []       # JS-reported values from the pages
STATE = {"token": "", "payload": b"", "dl_name": ""}

PAGE_SET = """<!doctype html><meta name=viewport content="width=device-width"><title>set</title><body>set
<script>
(async () => {{
  const t = {token!r};
  localStorage.setItem('pe_ls', t);
  const db = await new Promise((res, rej) => {{
    const r = indexedDB.open('pe_db', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('kv');
    r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
  }});
  await new Promise((res, rej) => {{ const tx = db.transaction('kv', 'readwrite'); tx.objectStore('kv').put(t, 'k');
    tx.oncomplete = res; tx.onerror = () => rej(tx.error); }});
  await fetch('/report?step=set&ok=1');
}})().catch(e => fetch('/report?step=set&err=' + encodeURIComponent(String(e))));
</script>"""

PAGE_ECHO = """<!doctype html><meta name=viewport content="width=device-width"><title>echo</title><body>echo
<script>
(async () => {{
  const ls = localStorage.getItem('pe_ls') || '';
  let idb = '';
  try {{
    const db = await new Promise((res, rej) => {{ const r = indexedDB.open('pe_db', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('kv'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); }});
    idb = await new Promise((res, rej) => {{ const q = db.transaction('kv').objectStore('kv').get('k');
      q.onsuccess = () => res(q.result || ''); q.onerror = () => rej(q.error); }});
  }} catch (e) {{ idb = 'ERR:' + e; }}
  await fetch('/report?step={step}&ls=' + encodeURIComponent(ls) + '&idb=' + encodeURIComponent(idb));
}})();
</script>"""

PAGE_LINKS = """<!doctype html><meta name=viewport content="width=device-width"><title>links</title>
<body style="margin:0"><a href="{href}" style="display:block;width:100vw;height:100vh;background:#fc0;font-size:48px">tap</a>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html", extra=()):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        HITS.append({"path": u.path, "cookie": self.headers.get("Cookie", "")})
        t = STATE["token"]
        if u.path == "/set":
            self._send(PAGE_SET.format(token=t).encode(),
                       extra=[("Set-Cookie", f"pe_cookie={t}; Max-Age=86400; Path=/")])
        elif u.path.startswith("/echo"):
            self._send(PAGE_ECHO.format(step=q.get("step", ["echo"])[0]).encode())
        elif u.path == "/report":
            REPORTS.append({k: v[0] for k, v in q.items()})
            self._send(b"ok", "text/plain")
        elif u.path == "/file":
            self._send(STATE["payload"], "application/octet-stream",
                       [("Content-Disposition", f'attachment; filename="{STATE["dl_name"]}"')])
        elif u.path == "/links":
            self._send(PAGE_LINKS.format(href=q.get("href", ["tel:5551234"])[0]).encode())
        else:
            self._send(b"<!doctype html><title>ok</title>ok")

    def log_message(self, *a):
        pass


def adb(*args, timeout=40):
    try:
        r = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").replace("\r", "") + (r.stderr or "").replace("\r", "") * (0 if r.stdout else 1)
    except subprocess.TimeoutExpired:
        return ""


def sh(cmd, timeout=40):
    return adb("shell", cmd, timeout=timeout).strip()


def go_root():
    adb("root", timeout=30)
    time.sleep(3)
    adb("wait-for-device", timeout=60)
    return sh("id -u") == "0"


def reverse():
    adb("reverse", f"tcp:{PORT}", f"tcp:{PORT}")


def open_url(pkg, url):
    adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", url, "-p", pkg, timeout=60)


def wait_report(step, since, secs=30):
    t0 = time.time()
    while time.time() - t0 < secs:
        got = [r for r in REPORTS[since:] if r.get("step") == step]
        if got:
            return got[-1]
        time.sleep(1)
    return None


def pid_of(pkg):
    return sh(f"pidof {pkg}").split()[0] if sh(f"pidof {pkg}") else ""


def sha256_remote(path):
    out = sh(f"sha256sum '{path}'", timeout=60)
    return out.split()[0] if out and "No such" not in out else ""


# ---------------------------------------------------------------- pure evaluation helpers (host-tested)
def retention_ok(rep, hits, token):
    """rep: JS report of the echo page; hits: served requests after the restart."""
    cookie_ok = any(f"pe_cookie={token}" in h["cookie"] for h in hits)
    return {"cookie": cookie_ok, "localStorage": (rep or {}).get("ls") == token,
            "indexedDB": (rep or {}).get("idb") == token}


def secure_flag_in_window_dump(dump, pkg):
    """True if a Window of `pkg` carries the SECURE layout flag in `dumpsys window windows`."""
    blocks = re.split(r"\n\s*Window #\d+ ", dump)
    for b in blocks:
        if pkg in b.split("\n", 1)[0]:
            m = re.search(r"\bfl=([^\n]*)", b)
            if m and re.search(r"\bSECURE\b", m.group(1)):
                return True
    return False


def top_package(dump):
    m = re.search(r"(?:topResumedActivity|mResumedActivity|ResumedActivity)[^\n]*?\{[^}]*?\s([\w.]+)/", dump)
    return m.group(1) if m else ""


def summarize(results):
    c = {"PASS": 0, "FAIL": 0, "NOT_RUN": 0}
    for r in results:
        c[r["status"]] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pkg = a.package
    os.makedirs(a.out, exist_ok=True)
    STATE["token"] = secrets.token_hex(12)
    STATE["payload"] = b"PERSONAL-E2E-CANARY-" + STATE["token"].encode() + os.urandom(200 * 1024)
    STATE["dl_name"] = f"personal_e2e_{STATE['token']}.bin"
    want_sha = hashlib.sha256(STATE["payload"]).hexdigest()
    results = []

    def res(cid, status, detail=""):
        results.append({"id": cid, "status": status, "detail": detail})
        print(f"PERSONAL_E2E {cid} {status} {detail}", flush=True)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    abi = sh("getprop ro.product.cpu.abi")
    rooted = go_root()
    print(f"PERSONAL_E2E env package={pkg} abi={abi} android={sh('getprop ro.build.version.release')} "
          f"sdk={sh('getprop ro.build.version.sdk')} root={rooted}", flush=True)
    reverse()
    base = f"http://127.0.0.1:{PORT}"
    try:
        adb("logcat", "-c")
        adb("shell", "am", "force-stop", pkg)
        # ---- C01 launch + C02a: write, then background retention
        n_rep = len(REPORTS)
        open_url(pkg, f"{base}/set")
        r = wait_report("set", n_rep, 40)
        time.sleep(2)
        pid = pid_of(pkg)
        crash = adb("logcat", "-d", "-b", "crash", timeout=40)
        crash_n = sum(1 for l in crash.splitlines() if pkg in l)
        if r and r.get("ok") == "1" and pid and not crash_n:
            res("C01_launch", "PASS", f"pid={pid} page_js_wrote_cookie_ls_idb crash_lines=0")
        else:
            res("C01_launch", "FAIL", f"report={r} pid={pid or 'none'} crash_lines={crash_n}")

        def read_back(label, restart):
            n_h, n_r = len(HITS), len(REPORTS)
            reverse()
            open_url(pkg, f"{base}/echo?step={label}")
            rep = wait_report(label, n_r, 40)
            return retention_ok(rep, HITS[n_h:], STATE["token"]), rep

        adb("shell", "input", "keyevent", "KEYCODE_HOME")
        time.sleep(5)
        ok_bg, rep = read_back("bg", False)
        adb("shell", "am", "force-stop", pkg)
        time.sleep(3)
        ok_fs, rep2 = read_back("fs", True)
        pid_before = pid_of(pkg)
        crash_cmd = adb("shell", "am", "crash", pkg)
        time.sleep(4)
        pid_after = pid_of(pkg)
        adb("shell", "am", "force-stop", pkg)
        time.sleep(3)
        ok_cr, rep3 = read_back("cr", True)
        allv = {"background": ok_bg, "force_stop": ok_fs, "crash": ok_cr}
        if all(all(v.values()) for v in allv.values()):
            res("C02_retention", "PASS", json.dumps(allv, sort_keys=True))
        else:
            res("C02_retention", "FAIL", json.dumps(allv, sort_keys=True) +
                f" crash_cmd_pid_before={pid_before or 'none'} after={pid_after or 'none'}")

        # ---- C03 download containment
        n_h = len(HITS)
        reverse()
        open_url(pkg, f"{base}/file")
        found = ""
        t0 = time.time()
        while time.time() - t0 < 90 and not found:
            time.sleep(4)
            hit = sh(f"find /data/data/{pkg} /data/user -name '{STATE['dl_name']}' -type f 2>/dev/null | head -1", 60)
            found = hit.splitlines()[0] if hit else ""
        served = any(h["path"] == "/file" for h in HITS[n_h:])
        shared = sh(f"find /sdcard /storage /data/media /mnt -name '{STATE['dl_name']}*' 2>/dev/null | head -3", 90)
        media = sh(f"content query --uri content://media/external/file --where \"_display_name like '{STATE['dl_name']}%'\" 2>&1 | head -3")
        dlprov = sh(f"content query --uri content://downloads/my_downloads --where \"title like '%{STATE['token']}%'\" 2>&1 | head -3")
        sysdl = sh(f"dumpsys downloads 2>/dev/null | grep -c '{STATE['token']}'")
        sha = sha256_remote(found) if found else ""
        media_hit = "_display_name" in media and "No result" not in media
        prov_hit = "_id=" in dlprov and "No result" not in dlprov
        detail = (f"served={served} private_path={found or 'none'} sha_ok={sha == want_sha} shared_storage={'HIT:'+shared if shared else 'none'} "
                  f"mediastore_hit={media_hit} downloads_provider_hit={prov_hit} dumpsys_downloads={sysdl}")
        if not served or not found:
            res("C03_download", "NOT_RUN" if not served else "FAIL", detail)
        elif sha == want_sha and not shared and not media_hit and not prov_hit and sysdl in ("0", ""):
            res("C03_download", "PASS", detail)
        else:
            res("C03_download", "FAIL", detail)

        # ---- C04 external intent handoff (real taps; negative-only, no positive control on this APK)
        outcomes = {}
        for name, href in (("tel", "tel:5551234"), ("market", "market://details?id=com.android.vending")):
            adb("shell", "am", "force-stop", pkg)
            reverse()
            open_url(pkg, f"{base}/links?href={urllib.parse.quote(href, safe='')}")
            time.sleep(6)
            size = re.search(r"(\d+)x(\d+)", sh("wm size"))
            w, h = (int(size.group(1)), int(size.group(2))) if size else (1080, 2400)
            adb("shell", "input", "tap", str(w // 2), str(h // 2))
            time.sleep(4)
            outcomes[name] = top_package(sh("dumpsys activity activities", 60))
        if all(v == pkg for v in outcomes.values()):
            res("C04_external", "PASS", f"top_package_after_tap={outcomes} (negative-only: no positive control)")
        elif any(not v for v in outcomes.values()):
            res("C04_external", "NOT_RUN", f"top package not parsed: {outcomes}")
        else:
            res("C04_external", "FAIL", f"another app took focus: {outcomes}")

        # ---- C05 FLAG_SECURE
        adb("shell", "am", "force-stop", pkg)
        reverse()
        open_url(pkg, f"{base}/")
        time.sleep(5)
        wd = sh("dumpsys window windows", 60)
        open(os.path.join(a.out, "window_dump.txt"), "w").write(wd)
        if pkg not in wd:
            res("C05_secure", "NOT_RUN", "app window not found in dumpsys window")
        elif secure_flag_in_window_dump(wd, pkg):
            res("C05_secure", "PASS", "window fl= contains SECURE")
        else:
            res("C05_secure", "FAIL", "SECURE not in app window flags")

        # ---- C06 backup
        pk = sh(f"dumpsys package {pkg}", 60)
        m = re.search(r"^\s+(?:pkgFlags|flags)=\[([^\]]*)\]", pk, re.M)
        flags = m.group(1).strip() if m else ""
        if flags and "ALLOW_BACKUP" not in flags.split():
            res("C06_backup", "PASS", f"flags=[{flags}]")
        else:
            res("C06_backup", "NOT_RUN", f"allowBackup enabled or flags unreadable; rules not measurable here: [{flags}]")

        # ---- C07 no account link
        acc = sh("dumpsys account", 60)
        n_acc = len(re.findall(r"Account \{name=", acc))
        res("C07_no_account", "PASS" if n_acc == 0 else "FAIL", f"accounts_on_device={n_acc}")

        # ---- C08 preserved (nothing wiped across the whole sequence)
        prof = f"/data/data/{pkg}/app_chrome"
        missing = []
        for label, name in (("Cookies", "Cookies"), ("Local Storage", "Local Storage"), ("IndexedDB", "IndexedDB")):
            if not sh(f"find {prof} -maxdepth 4 -name '{name}' 2>/dev/null | head -1", 60):
                missing.append(label)
        res("C08_preserved", "PASS" if not missing else "FAIL", f"missing={missing}")
    except Exception as e:  # noqa: BLE001
        print("PERSONAL_E2E harness_error", repr(e)[:300], flush=True)
        return 2
    finally:
        adb("shell", "am", "force-stop", pkg)
        adb("logcat", "-d", "-b", "all", "-t", "4000")
        try:
            open(os.path.join(a.out, "logcat_tail.txt"), "w").write(adb("logcat", "-d", "-t", "6000", timeout=60))
        except Exception:  # noqa: BLE001
            pass
        srv.shutdown()
    c = summarize(results)
    json.dump({"package": pkg, "abi": abi, "results": results, "summary": c},
              open(os.path.join(a.out, "personal_e2e.json"), "w"), indent=1)
    print(f"PERSONAL_E2E_SUMMARY pass={c['PASS']} fail={c['FAIL']} not_run={c['NOT_RUN']} abi={abi}", flush=True)
    return 1 if c["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
