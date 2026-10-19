#!/usr/bin/env python3
"""Native Safety check acceptance for patches 0005 v2 + 0020, on a disposable Android CI device.

Unlike update_e2e.py's future-dated offer, the positive case uses the REAL production
manifest and the app's normal download/signature/persistence path. No harness-generated
'last verified' timestamp is used for that case. The rejected-signature cases use the
existing signed public fixture, modified by one byte, via adb reverse.

Only the swiftra_update_* SharedPreferences entries are reset/restored (rooted CI
emulator/Redroid only). The app is stopped before each edit; unrelated prefs, including
the wrapped OSCrypt key, are preserved and never printed or saved to artifacts.
A rejected request does not invalidate a genuine check younger than 48 h: test that
explicitly, as well as absent, stale and future-clock verification timestamps.
"""
import argparse
import copy
import http.server
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shield_e2e import adb, find_text, screenshot, tap, to_browser, ui_nodes  # noqa: E402
from startup_netlog import CMDLINE_FILE, resolve_launcher  # noqa: E402
from update_e2e import REL, fetch, tamper  # noqa: E402

PORT = 8792
PREFIX = "swiftra_update_"
LAST_OK = PREFIX + "last_ok_ms"
RECENT_MS = 48 * 3600 * 1000
EXPECTED = {
    "bad_fresh": "unavailable",
    "good_production": "current",
    "bad_recent": "current",
    "bad_stale": "unavailable",
    "bad_future": "unavailable",
}
TITLES = {
    "can't check swiftra version": "unavailable",
    "swiftra is up to date": "current",
    "swiftra is out of date": "outdated",
}


def pref_root(raw):
    # AOSP FastXmlSerializer writes &#0; .. &#31; for controls inside Java strings.
    # Android can read these, but Expat/ElementTree rejects the XML-1.0-forbidden ones (error 14).
    # Decode ONLY those references losslessly in memory; do not strip/sanitize unrelated values.
    text = raw.decode("utf-8")
    if any(mark in text for mark in ("<!DOCTYPE", "<!ENTITY", "<![CDATA[")):
        raise RuntimeError("unsupported SharedPreferences XML construct")
    prefix = "__SWIFTRA_XML_CONTROL_"
    while prefix in text:
        prefix += "_"
    controls = {}

    def substitute(match):
        value = match.group(1)
        point = int(value[1:], 16) if value.startswith("x") else int(value)
        if not (0 <= point < 32 and point not in (9, 10, 13)):
            return match.group(0)
        token = prefix + str(len(controls)) + "__"
        controls[token] = chr(point)
        return token

    escaped = re.sub(r"&#(x[0-9A-Fa-f]+|[0-9]+);", substitute, text)
    root = ET.fromstring(escaped)
    if root.tag != "map":
        raise ValueError("unexpected SharedPreferences root")

    def restore(value):
        if value is not None:
            for token, char in controls.items():
                value = value.replace(token, char)
        return value

    for node in root.iter():
        if prefix in node.tag or any(prefix in key for key in node.attrib):
            raise RuntimeError("control reference outside SharedPreferences values")
        node.text, node.tail = restore(node.text), restore(node.tail)
        for key, value in node.attrib.items():
            node.set(key, restore(value))
    return root


def prefs_bytes(root):
    # ElementTree can hold controls in Python strings but emits raw invalid XML. Put them back
    # in Android's numeric-reference form before any bytes reach disk. This also preserves NULs.
    text = ET.tostring(root, encoding="unicode", xml_declaration=True)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", lambda m: "&#%d;" % ord(m.group(0)), text)
    return text.encode("utf-8")


def update_nodes(raw):
    return [copy.deepcopy(n) for n in pref_root(raw) if n.get("name", "").startswith(PREFIX)]


def replace_update_nodes(raw, nodes):
    root = pref_root(raw)
    for n in list(root):
        if n.get("name", "").startswith(PREFIX):
            root.remove(n)
    root.extend(copy.deepcopy(nodes))
    return prefs_bytes(root)


def with_last_ok(raw, timestamp):
    nodes = [n for n in update_nodes(raw) if n.get("name") != LAST_OK]
    nodes.append(ET.Element("long", {"name": LAST_OK, "value": str(timestamp)}))
    return replace_update_nodes(raw, nodes)


def last_ok(raw):
    ns = [n for n in pref_root(raw) if n.get("name") == LAST_OK]
    if not ns:
        return 0
    if len(ns) != 1 or ns[0].tag != "long":
        raise ValueError("invalid verification timestamp preference")
    return int(ns[0].get("value", "0"))


def normalize(text):
    return " ".join(text.replace("\u2019", "'").replace("\u2018", "'").lower().split())


def page_state(xml, package, version):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return {"state": None, "states": [], "page_title": False, "version": False, "play_store": False}
    texts = []
    for n in root.iter("node"):
        if n.get("package") != package:
            continue
        b = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds", ""))
        if not b:
            continue
        x1, y1, x2, y2 = map(int, b.groups())
        if x2 > x1 and y2 > y1 and n.get("text"):
            texts.append(n.get("text"))
    normal = [normalize(t) for t in texts]
    states = sorted({TITLES[t] for t in normal if t in TITLES})
    return {
        "state": states[0] if len(states) == 1 else None,
        "states": states,
        "page_title": "safety check" in normal,
        "version": bool(version) and "version " + version.lower() in normal,
        "play_store": any(t == "go to google play" for t in normal),
        "texts": texts,
    }


def case_pass(name, case):
    ui = case.get("ui", {})
    if not (ui.get("page_title") and ui.get("version") and not ui.get("play_store")
            and ui.get("state") == EXPECTED.get(name) and len(ui.get("states", [])) == 1):
        return False
    if name == "good_production":
        return case.get("verified_by_app") is True and case.get("last_ok_before") == 0
    return (case.get("manifest_fetched") is True and case.get("signature_rejected") is True
            and case.get("last_ok_before") == case.get("last_ok_after"))


def verdict(result):
    if result.get("setup_error") or result.get("unsupported"):
        return "not_run"
    cases = result.get("cases", {})
    if not cases:
        return "not_run"
    if result.get("error") or result.get("restored") is not True or set(cases) != set(EXPECTED):
        return "fail"
    return "pass" if all(case_pass(n, c) for n, c in cases.items()) else "fail"


def checked_adb(*args, raw_input=None, timeout=45):
    r = subprocess.run(["adb", *args], input=raw_input, capture_output=True, timeout=timeout)
    if r.returncode:
        # Never include stdout/stderr: private SharedPreferences can contain wrapped key material.
        raise RuntimeError("adb operation failed (exit %d)" % r.returncode)
    return r.stdout


def root_device():
    hardware = checked_adb("shell", "getprop", "ro.hardware").strip()
    if hardware not in (b"ranchu", b"goldfish", b"redroid"):
        raise RuntimeError("refusing private-pref fixtures on a physical or unknown Android device")
    if checked_adb("shell", "id", "-u").strip() != b"0":
        checked_adb("root")
        checked_adb("wait-for-device", timeout=60)
    if checked_adb("shell", "id", "-u").strip() != b"0":
        raise RuntimeError("rooted disposable CI Android device required")


def stop_browser(package):
    # SharedPreferences.apply() is asynchronous. Android flushes queued writes on Activity stop;
    # do not kill immediately after first-run preference updates (AOSP SharedPreferencesImpl).
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    time.sleep(2)
    checked_adb("shell", "am", "force-stop", package)


def read_prefs(path):
    raw = checked_adb("exec-out", "cat", path)
    try:
        pref_root(raw)
    except ET.ParseError as e:
        # Metadata only. Never dump the malformed private file, an error excerpt, or key values.
        kind = "empty" if not raw else "abx" if raw.startswith(b"ABX\x00") else "xml" if raw.lstrip().startswith(b"<?xml") else "other"
        controls = len(re.findall(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", raw))
        raise RuntimeError("prefs parse refused: bytes=%d format=%s code=%s position=%s controls=%d" %
                           (len(raw), kind, e.code, e.position, controls)) from None
    return raw


def write_prefs(path, raw):
    # Stage in the private app directory, verify bytes AND uid/mode/SELinux label, then rename.
    # shell -T uses the shell-v2 stdin/exit protocol; exec-in can close without a remote-exit ack.
    # A dropped/truncated stdin or failed metadata operation must never truncate the original.
    pref_root(raw)
    tmp = path + ".swiftra_e2e.tmp"
    q, t = shlex.quote(path), shlex.quote(tmp)
    metadata = checked_adb("shell", "stat", "-c", "%u:%g:%a", path).strip()
    context = checked_adb("shell", "ls", "-Zd", path).split()[0]
    script = "umask 077; test ! -e %s.bak && test ! -e %s && test -f %s && cp -p %s %s && cat > %s" % (q, t, q, q, t, t)
    try:
        checked_adb("shell", "-T", script, raw_input=raw)
        if read_prefs(tmp) != raw:
            raise RuntimeError("SharedPreferences fixture write did not round-trip")
        if b":" in context:
            checked_adb("shell", "chcon", context.decode("ascii"), tmp)
        if (checked_adb("shell", "stat", "-c", "%u:%g:%a", tmp).strip() != metadata
                or checked_adb("shell", "ls", "-Zd", tmp).split()[0] != context):
            raise RuntimeError("SharedPreferences fixture metadata changed")
        checked_adb("shell", "mv", "-f", tmp, path)
    finally:
        checked_adb("shell", "rm", "-f", tmp)


def device_ms():
    return int(checked_adb("shell", "date", "+%s").strip()) * 1000


def open_safety(package, out, name, version):
    if not to_browser(package):
        return {"navigation_error": "no browser toolbar"}
    ns, _ = ui_nodes()
    menus = [n for n in ns if n["id"].endswith(":id/menu_button") and n["h"] > 0]
    if not menus:
        return {"navigation_error": "no menu button"}
    tap(menus[0])
    time.sleep(1)
    for title in ("Settings", "Safety check"):
        n, _ = find_text(title, scrolls=5)
        if not n:
            return {"navigation_error": "missing " + title}
        tap(n)
        time.sleep(2)
    # Good rows can be below warning rows; capture only when the actual row is visible.
    state, xml = {}, ""
    for i in range(6):
        _, xml = ui_nodes()
        state = page_state(xml, package, version)
        if state.get("states"):
            break
        if i < 5:
            adb("shell", "input", "swipe", "540", "1700", "540", "850", "350")
            time.sleep(1)
    with open(os.path.join(out, name + ".xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    screenshot(os.path.join(out, name + ".png"))
    return state


def run_case(package, comp, path, name, out, version, hits):
    before = last_ok(read_prefs(path))
    production = name == "good_production"
    flags = "_" if production else "_ --swiftra-update-manifest-url=http://127.0.0.1:%d/bad.json" % PORT
    checked_adb("shell", "-T", "cat > " + CMDLINE_FILE + " && chmod 644 " + CMDLINE_FILE,
                raw_input=(flags + "\n").encode())
    if checked_adb("exec-out", "cat", CMDLINE_FILE) != (flags + "\n").encode():
        raise RuntimeError("command-line fixture write did not round-trip")
    adb("logcat", "-c")
    n0, start_ms = len(hits), device_ms()
    checked_adb("shell", "am", "start", "-W", "-n", comp, "-a", "android.intent.action.VIEW", "-d", "about:blank", timeout=60)
    # Open the page first: SafetyHubFetchService itself subscribes to UpdateStatusProvider.
    ui = open_safety(package, out, name, version)
    deadline = time.monotonic() + 65
    after = last_ok(read_prefs(path))
    while time.monotonic() < deadline:
        if (production and after >= start_ms - 1000) or (not production and "/bad.json.sig" in hits[n0:]):
            break
        time.sleep(2)
        after = last_ok(read_prefs(path))
    # The async status may have changed while awaiting download/verification; re-enter and capture it.
    ui = open_safety(package, out, name, version)
    after = last_ok(read_prefs(path))
    log = adb("logcat", "-d", "-s", "SwiftraUpdate:*", "cr_SwiftraUpdate:*", timeout=30) or ""
    record = {
        "ui": ui,
        "last_ok_before": before,
        "last_ok_after": after,
        "manifest_fetched": "/bad.json" in hits[n0:] and "/bad.json.sig" in hits[n0:],
        "signature_rejected": "test manifest rejected: bad signature" in log,
        "verified_by_app": production and before == 0 and start_ms - 1000 <= after <= device_ms() + 1000,
        "source": "production HTTPS + app signature verifier" if production else "loopback tampered signed fixture",
    }
    record["pass"] = case_pass(name, record)
    print("SAFETY_CASE", name, "PASS" if record["pass"] else "FAIL", "state=" + str(ui.get("state")), flush=True)
    return record


def prepare_browser(package, apk, out):
    # Reuse the established no-account first-run handler, not the long screenshot/perf journey.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ui_capture import Device, launch, wait_ready  # noqa: E402
    checked_adb("install", "-r", "-g", apk, timeout=600)
    d = Device(package, out, lambda line: print("SAFETY_PREPARE", line, flush=True))
    launch(d)
    if not wait_ready(d, seconds=180):
        raise RuntimeError("no-account first run did not reach the browser")
    stop_browser(package)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--apk", help="focused CI: install this APK and finish no-account first run before testing")
    a = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", a.package):
        ap.error("invalid Android package")
    os.makedirs(a.out, exist_ok=True)
    result = {"package": a.package, "cases": {}, "restored": False}
    path = "/data/data/%s/shared_prefs/%s_preferences.xml" % (a.package, a.package)
    original, srv, thread = None, None, None
    hits = []
    try:
        root_device()
        if a.apk:
            prepare_browser(a.package, a.apk, a.out)
        # CommandLineInitUtil also checks ADB_ENABLED (fresh Redroid differs from a prepared full run).
        adb("shell", "settings", "put", "global", "adb_enabled", "1")
        stop_browser(a.package)
        result["stage"] = "read_original_prefs"
        original = update_nodes(read_prefs(path))
        comp = resolve_launcher(a.package)
        if not comp:
            raise RuntimeError("launcher not found")
        info = checked_adb("shell", "dumpsys", "package", a.package).decode("utf-8", "replace")
        m = re.search(r"versionName=(\S+)", info)
        if not m:
            raise RuntimeError("installed version not found")
        version = m.group(1)
        result["stage"] = "fetch_fixture"
        good, sig = fetch(REL + "swiftra-update-e2e.json"), fetch(REL + "swiftra-update-e2e.json.sig")
        bad = tamper(good)
        if not bad:
            raise RuntimeError("public signed test manifest unavailable")

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                hits.append(self.path)
                body = {"/bad.json": bad, "/bad.json.sig": sig}.get(self.path)
                self.send_response(200 if body is not None else 404)
                self.send_header("Content-Length", str(len(body or b"")))
                self.end_headers()
                if body is not None:
                    self.wfile.write(body)

            def log_message(self, *args):
                pass

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        adb("reverse", "tcp:%d" % PORT, "tcp:%d" % PORT)
        adb("shell", "am", "set-debug-app", "--persistent", a.package)
        for name in EXPECTED:
            result["stage"] = name + ":prepare"
            stop_browser(a.package)
            raw = read_prefs(path)
            if name in ("bad_fresh", "good_production"):
                raw = replace_update_nodes(raw, [])
            elif name == "bad_stale":
                raw = with_last_ok(raw, device_ms() - RECENT_MS - 60000)
            elif name == "bad_future":
                raw = with_last_ok(raw, device_ms() + 3600000)
            write_prefs(path, raw)
            result["stage"] = name + ":run"
            result["cases"][name] = run_case(a.package, comp, path, name, a.out, version, hits)
        result["stage"] = "done"
    except Exception as e:  # noqa: BLE001
        # Only our own fixed RuntimeError messages are safe; parser/third-party errors may expose private prefs.
        key = "error" if result["cases"] else "setup_error"
        result[key] = str(e) if type(e) is RuntimeError else type(e).__name__ + " (private details withheld)"
    finally:
        adb("shell", "am", "force-stop", a.package)
        if original is not None:
            try:
                write_prefs(path, replace_update_nodes(read_prefs(path), original))
                result["restored"] = True
            except Exception as e:  # noqa: BLE001
                result["restore_error"] = type(e).__name__
        adb("shell", "rm", "-f", CMDLINE_FILE)
        adb("reverse", "--remove", "tcp:%d" % PORT)
        if srv:
            srv.shutdown()
            srv.server_close()
        if thread:
            thread.join(timeout=5)
    result["verdict"] = verdict(result)
    with open(os.path.join(a.out, "safety_update_e2e.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    passed = sum(case_pass(n, c) for n, c in result["cases"].items())
    print("SAFETY_UPDATE_E2E", {"pass": "PASS", "fail": "FAIL"}.get(result["verdict"], "NOT_RUN"),
          "cases=%d/%d restored=%s stage=%s" % (passed, len(EXPECTED), result["restored"], result.get("stage")),
          result.get("error", result.get("setup_error", "")), flush=True)
    return {"pass": 0, "fail": 1, "not_run": 2}[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
