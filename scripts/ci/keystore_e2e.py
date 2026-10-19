#!/usr/bin/env python3
"""KEYSTORE_E2E (patch 0021): cookies are encrypted with the Android-Keystore-protected key, not the public v10 key.

Upstream Chrome Android encrypts cookie values (and local card/IBAN data) through OSCryptAsync, whose only Android
provider is PosixKeyProvider with a constant key from the public source ("v10"). Patch 0021 adds a provider with a
random per-install AES-256-GCM key that is stored only wrapped by a non-exportable Keystore key ("sw1").

Steps (loopback only: runner 127.0.0.1:PORT via `adb reverse`, no real site, no account):
  1. /set   -> Set-Cookie swiftra_e2e=<random token>
  2. app to background, poll the Cookies SQLite file (root read: emulator `adb root` / Redroid) until the row exists
  3. wrap path:   encrypted_value starts with b"sw1", value is empty, the token is in no DB file in plain text
  4. unwrap path: force-stop, restart, /echo -> the browser sends the same cookie back (decrypted after restart)
Prints KEYSTORE_E2E PASS / FAIL / NOT_RUN. NOT_RUN when the row could not be read, or the build has no 0021
(v10 prefix and no wrapped key in the app preferences).
"""
import argparse
import http.server
import json
import os
import secrets
import sqlite3
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shield_e2e import adb  # noqa: E402
from startup_netlog import read_app_file  # noqa: E402

PORT = 8791
NAME = "swiftra_e2e"
PREF_KEY = "swiftra_oscrypt_wrapped_v1"
HITS = []
TOKEN = {"v": ""}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        HITS.append({"path": self.path, "cookie": self.headers.get("Cookie", "")})
        body = b"<!doctype html><title>ok</title><p>ok</p>"
        self.send_response(200)
        if self.path.startswith("/set"):
            self.send_header("Set-Cookie", f"{NAME}={TOKEN['v']}; Max-Age=3600; Path=/")
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def cookie_row(files):
    """files: {basename: bytes} of one Cookies database (+ -wal / -journal). Returns (value, encrypted_value) or None."""
    if not files.get("Cookies"):
        return None
    with tempfile.TemporaryDirectory() as d:
        for n, b in files.items():
            if b:
                with open(os.path.join(d, n), "wb") as f:
                    f.write(b)
        try:
            con = sqlite3.connect(os.path.join(d, "Cookies"))
            r = con.execute("SELECT value, encrypted_value FROM cookies WHERE name=?", (NAME,)).fetchone()
            con.close()
        except sqlite3.Error:
            return None
    return (r[0], bytes(r[1] or b"")) if r else None


def verdict(res):
    row = res.get("row")
    if not row:
        return "not_run"
    value, enc_prefix = row["value"], row["enc_prefix"]
    if enc_prefix != "sw1":
        if not res.get("wrapped_pref") and enc_prefix == "v10":
            return "not_run"                         # APK without 0021: upstream behaviour
        return "fail"
    if value or res.get("token_in_plaintext") or not res.get("restart_cookie_sent"):
        return "fail"
    return "pass"


def read_db(pkg):
    for base in (f"/data/data/{pkg}/app_chrome/Default/Network", f"/data/data/{pkg}/app_chrome/Default"):
        main, how = read_app_file(f"{base}/Cookies")
        if main:
            files = {"Cookies": main}
            for suf in ("-wal", "-journal"):
                b, _ = read_app_file(f"{base}/Cookies{suf}")
                if b:
                    files["Cookies" + suf] = b
            return base, files, how
    return None, {}, None


def open_url(pkg, url):
    adb("shell", "am", "start", "-W", "-a", "android.intent.action.VIEW", "-d", url, "-p", pkg, timeout=60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    TOKEN["v"] = secrets.token_hex(12)
    res = {"package": a.package}
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    adb("reverse", f"tcp:{PORT}", f"tcp:{PORT}")
    try:
        svc = adb("shell", "service", "check", "android.system.keystore2.IKeystoreService/default", timeout=20) or ""
        res["device_keystore2"] = "not found" not in svc and "found" in svc   # diagnosis if the provider is unavailable
        open_url(a.package, f"http://127.0.0.1:{PORT}/set")
        time.sleep(4)
        res["set_served"] = any(h["path"].startswith("/set") for h in HITS)
        adb("shell", "input", "keyevent", "KEYCODE_HOME")
        row, files, t0 = None, {}, time.time()
        while time.time() - t0 < 75 and not row:     # cookie store commits within ~30 s
            time.sleep(8)
            base, files, how = read_db(a.package)
            res["db"], res["read_via"] = base, how
            row = cookie_row(files)
        if row:
            res["row"] = {"value": row[0], "enc_prefix": row[1][:3].decode("latin-1"), "enc_len": len(row[1])}
        tok = TOKEN["v"].encode()
        res["token_in_plaintext"] = any(tok in b for b in files.values())
        prefs, _ = read_app_file(f"/data/data/{a.package}/shared_prefs/{a.package}_preferences.xml")
        res["wrapped_pref"] = bool(prefs and PREF_KEY.encode() in prefs)
        adb("shell", "am", "force-stop", a.package)
        time.sleep(2)
        adb("reverse", f"tcp:{PORT}", f"tcp:{PORT}")   # `adb root` (root reads) restarts adbd and drops reverses
        n0 = len(HITS)
        open_url(a.package, f"http://127.0.0.1:{PORT}/echo")
        t1 = time.time()
        while time.time() - t1 < 30 and not any(h["path"].startswith("/echo") for h in HITS[n0:]):
            time.sleep(1)
        echo = [h for h in HITS[n0:] if h["path"].startswith("/echo")]
        res["restart_echo_seen"] = bool(echo)
        res["restart_cookie_sent"] = any(f"{NAME}={TOKEN['v']}" in h["cookie"] for h in echo)
    except Exception as e:  # noqa: BLE001
        res["error"] = repr(e)[:300]
    finally:
        adb("shell", "am", "force-stop", a.package)
        adb("reverse", "--remove", f"tcp:{PORT}")
        srv.shutdown()
    res["verdict"] = verdict(res)
    with open(os.path.join(a.out, "keystore_e2e.json"), "w") as f:
        json.dump(res, f, indent=1)
    r = res.get("row") or {}
    print("KEYSTORE_E2E", {"pass": "PASS", "fail": "FAIL"}.get(res["verdict"], "NOT_RUN"),
          f"prefix={r.get('enc_prefix')} plain_value={bool(r.get('value'))} token_in_db={res.get('token_in_plaintext')}"
          f" wrapped_pref={res.get('wrapped_pref')} cookie_after_restart={res.get('restart_cookie_sent')}"
          f" keystore2={res.get('device_keystore2')}",
          res.get("error", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
