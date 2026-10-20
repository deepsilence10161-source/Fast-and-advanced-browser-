#!/usr/bin/env python3
"""CI-only same-APK startup screening, one performance flag at a time; never weakens security.

am start -W TotalTime is a process-cold diagnostic, NOT Macrobenchmark TTFD, page LCP or a Chrome comparison.
Warm native config -> verify only the named Java cached booleans -> measure the NEXT cold processes.
No preference edits, profile clears, key deletion, TLS exceptions or arbitrary command-line input.
"""
import argparse
import hashlib
import json
import os
import random
import re
import shlex
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from safety_update_e2e import checked_adb, pref_root, prepare_browser, read_prefs, root_device, stop_browser
from shield_e2e import open_internal, page_text, targets
from startup_netlog import CMDLINE_FILE, CMDLINE_JS, close_all_tabs, resolve_launcher
from art_startup import dexopt_status
from speed_e2e import socket_up

FEATURES = (
    "AndroidStartupImprovements", "AndroidSystemFontPrewarming", "TweakApplicationPreloadMoveWarmUp",
    "AndroidWarmUpSpareRendererWithTimeout", "SQLitePersistentCookieStoreEarlyInit", "EarlyCookieLoadOnPreconnect",
)
MODES = {"shipped": None, **{"without_" + f: f for f in FEATURES}}
CACHED = ("AndroidStartupImprovements", "TweakApplicationPreloadMoveWarmUp")
CACHE_PREFIX = "Chrome.Flags.CachedFlag."
CRASH = "Chrome.Flags.CrashStreakBeforeCache"
SAFE = "Chrome.Flags.SafeModeRunsLeft"
DEVTOOLS = "http://127.0.0.1:9222"
NONCE = "--swiftra-startup-ablation-id="


def mode_flags(mode, nonce):
    if mode not in MODES or not re.fullmatch(r"[a-zA-Z0-9_-]+", nonce):
        raise ValueError("invalid allowlisted ablation mode/receipt")
    feature = MODES[mode]
    return ("_ " + NONCE + nonce + (" --disable-features=" + feature if feature else "") + "\n").encode()


def flags_ok(command_line, mode, nonce):
    try:
        args = shlex.split(command_line)
    except ValueError:
        return False
    if NONCE + nonce not in args:
        return False
    disabled, enabled = set(), set()
    for arg in args:
        if arg.startswith("--disable-features="):
            disabled.update(arg.split("=", 1)[1].split(","))
        elif arg.startswith("--enable-features="):
            enabled.update(arg.split("=", 1)[1].split(","))
        elif arg.startswith(("--ignore-certificate", "--disable-web-security", "--no-sandbox",
                             "--disable-field-trial-config", "--disable-background-networking")):
            return False
    expected = {MODES[mode]} if MODES[mode] else set()
    # Exact overrides: no privacy/Safe Browsing/Keystore switch can ride along.
    return disabled == expected and not enabled


def block_order(block):
    names = list(MODES)
    shift = (block // 2) * 3 % len(names)
    names = names[shift:] + names[:shift]
    return list(reversed(names)) if block % 2 else names


def cache_receipt(raw):
    wanted = {CACHE_PREFIX + f: f for f in CACHED}
    result = {f: None for f in CACHED}
    result.update({"crash_streak": 0, "safe_runs_left": 0})
    for node in pref_root(raw):
        name = node.get("name")
        if name in wanted and node.tag == "boolean" and node.get("value") in ("true", "false"):
            result[wanted[name]] = node.get("value") == "true"
        elif name in (CRASH, SAFE) and node.tag == "int":
            result["crash_streak" if name == CRASH else "safe_runs_left"] = int(node.get("value", "-1"))
    return result  # Only two public flag booleans + counters, NEVER other private preference values.


def cache_ok(receipt, mode):
    return (all(receipt.get(f) is (MODES[mode] != f) for f in CACHED)
            and receipt.get("crash_streak") == 0 and receipt.get("safe_runs_left") == 0)


def parse_launch(text):
    def number(label):
        m = re.search(r"(?m)^" + label + r":\s*(\d+)", text)
        return int(m.group(1)) if m else None
    m = re.search(r"(?m)^LaunchState:\s*(\w+)", text)
    return {"total_ms": number("TotalTime"), "wait_ms": number("WaitTime"),
            "launch_state": m.group(1) if m else None, "status_ok": bool(re.search(r"(?m)^Status:\s*ok", text))}


def sample_ok(sample):
    return (sample.get("status_ok") and sample.get("launch_state") == "COLD"
            and isinstance(sample.get("total_ms"), int) and sample["total_ms"] > 0
            and sample.get("pid_gone_before") and sample.get("pid")
            and sample.get("pid") != sample.get("old_pid") and sample.get("flags_file_matches")
            and sample.get("cache_before_ok") and sample.get("cache_after_ok"))


def median(xs):
    return round(statistics.median(xs), 2) if xs else None


def summarize(rows, blocks, runs):
    summary = {}
    for mode in MODES:
        samples = [s["total_ms"] for r in rows if r["mode"] == mode for s in r["samples"] if sample_ok(s)]
        summary[mode] = {"valid_n": len(samples), "expected_n": blocks * runs, "median_ms": median(samples),
                         "min_ms": min(samples) if samples else None, "max_ms": max(samples) if samples else None}
        if mode == "shipped":
            continue
        deltas = []
        for block in range(blocks):
            group = {r["mode"]: [s["total_ms"] for s in r["samples"] if sample_ok(s)]
                     for r in rows if r["block"] == block}
            a, b = group.get("shipped", []), group.get(mode, [])
            if len(a) == runs and len(b) == runs and median(a):
                deltas.append(round(100 * (median(b) / median(a) - 1), 4))
        summary[mode]["block_delta_pct"] = deltas  # positive = slower; NOT a promotion decision
        summary[mode]["median_block_delta_pct"] = median(deltas)
        if deltas:
            rng = random.Random(155805980)
            boots = sorted(statistics.median(rng.choices(deltas, k=len(deltas))) for _ in range(4000))
            summary[mode]["block_bootstrap_95_pct"] = [round(boots[100], 3), round(boots[3899], 3)]
    return summary


def pid_of(package):
    # pidof legitimately exits 1 while stopped. Reject transport errors rather than treating them as stopped.
    import subprocess
    r = subprocess.run(["adb", "shell", "pidof", package], capture_output=True, timeout=15)
    if r.returncode not in (0, 1) or (r.returncode and (r.stdout.strip() or r.stderr.strip())):
        raise RuntimeError("could not read browser PID")
    return r.stdout.decode().strip().split()[0] if r.stdout.strip() else None


def file_exists(path):
    import subprocess
    r = subprocess.run(["adb", "shell", "test", "-f", path], capture_output=True, timeout=15)
    if r.returncode not in (0, 1) or (r.returncode and (r.stdout.strip() or r.stderr.strip())):
        raise RuntimeError("could not inspect command-line file")
    return r.returncode == 0


def snapshot_flags():
    if not file_exists(CMDLINE_FILE):
        return None
    return {"raw": checked_adb("exec-out", "cat", CMDLINE_FILE),
            "mode": checked_adb("shell", "stat", "-c", "%a", CMDLINE_FILE).strip().decode("ascii")}


def write_flags(raw, mode="644"):
    """Atomic acknowledged stdin write; exact bytes checked, old file never truncated on a dropped pipe."""
    if not re.fullmatch(r"[0-7]{3,4}", mode):
        raise ValueError("invalid command-line file mode")
    tmp = CMDLINE_FILE + ".startup-ablation.tmp"
    if file_exists(tmp):
        raise RuntimeError("unexpected command-line staging file")
    exists = file_exists(CMDLINE_FILE)
    metadata = checked_adb("shell", "stat", "-c", "%u:%g", CMDLINE_FILE).strip() if exists else None
    context = checked_adb("shell", "ls", "-Zd", CMDLINE_FILE).split()[0] if exists else None
    q, t = shlex.quote(CMDLINE_FILE), shlex.quote(tmp)
    create = "cp -p %s %s" % (q, t) if exists else ": > %s" % t
    try:
        checked_adb("shell", "-T", "umask 077; " + create + " && cat > " + t + " && chmod " + mode + " " + t,
                    raw_input=raw)
        if checked_adb("exec-out", "cat", tmp) != raw:
            raise RuntimeError("command-line staging bytes did not round-trip")
        if context and b":" in context:
            checked_adb("shell", "chcon", context.decode("ascii"), tmp)
        if metadata and checked_adb("shell", "stat", "-c", "%u:%g", tmp).strip() != metadata:
            raise RuntimeError("command-line owner changed")
        if context and checked_adb("shell", "ls", "-Zd", tmp).split()[0] != context:
            raise RuntimeError("command-line context changed")
        checked_adb("shell", "mv", "-f", tmp, CMDLINE_FILE)
    finally:
        checked_adb("shell", "rm", "-f", tmp)


def restore_flags(snapshot):
    if snapshot is None:
        checked_adb("shell", "rm", "-f", CMDLINE_FILE)
        return not file_exists(CMDLINE_FILE)
    write_flags(snapshot["raw"], snapshot["mode"])
    return (checked_adb("exec-out", "cat", CMDLINE_FILE) == snapshot["raw"]
            and checked_adb("shell", "stat", "-c", "%a", CMDLINE_FILE).strip().decode() == snapshot["mode"])


def installed_sha(package):
    paths = checked_adb("shell", "pm", "path", package).decode().splitlines()
    files = [line[len("package:"):].strip() for line in paths if line.startswith("package:") and line.endswith("/base.apk")]
    if len(files) != 1:
        raise RuntimeError("installed base APK not uniquely identifiable")
    value = checked_adb("shell", "sha256sum", files[0]).decode().split()[0]
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise RuntimeError("installed APK hash unavailable")
    return value


def receipt(package):
    path = "/data/data/%s/shared_prefs/%s_preferences.xml" % (package, package)
    return cache_receipt(read_prefs(path))


def launch(package, component):
    out = checked_adb("shell", "am", "start", "-W", "-n", component,
                      "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", timeout=75)
    return out.decode("utf-8", "replace")


def activate(package, component, mode, nonce, socket, settle):
    """Unmeasured warm-up; never pretend the current native override changed pre-native Java already."""
    expected = mode_flags(mode, nonce)
    attempts = []
    for attempt in range(3):
        stop_browser(package)
        write_flags(expected)
        launch(package, component)
        deadline, forwarded = time.monotonic() + 60, False
        ready = False
        while time.monotonic() < deadline:
            if pid_of(package) and socket_up(socket) is not False:
                if not forwarded:
                    checked_adb("forward", "tcp:9222", "localabstract:" + socket)
                    forwarded = True
                if targets(DEVTOOLS):
                    ready = True
                    break
            time.sleep(1)
        if not ready:
            raise RuntimeError("warm-up DevTools receipt unavailable")
        url = "chrome://version/?startup_ablation=" + nonce
        open_internal(DEVTOOLS, url)
        deadline, command_line = time.monotonic() + 20, ""
        while time.monotonic() < deadline:
            command_line = page_text(DEVTOOLS, url, CMDLINE_JS) or ""
            if command_line:
                break
            time.sleep(1)
        ok = flags_ok(command_line, mode, nonce)
        closed = close_all_tabs(DEVTOOLS)
        if closed.get("error") or closed.get("closed") != closed.get("pages"):
            raise RuntimeError("warm-up tabs were not all closed")
        time.sleep(settle)
        stop_browser(package)
        cached = receipt(package)
        attempts.append({"cli_verified": ok, "cached": cached, "closed_tabs": closed.get("closed", 0)})
        if ok and cache_ok(cached, mode):
            return {"attempts": attempts, "receipt_verified": True}
    raise RuntimeError("cached Java flags or safe-mode receipt did not converge")


def cold_sample(package, component, mode, expected, settle):
    before = receipt(package)
    old = pid_of(package)
    stop_browser(package)
    gone = pid_of(package) is None
    same = checked_adb("exec-out", "cat", CMDLINE_FILE) == expected
    sample = parse_launch(launch(package, component))
    sample.update({"old_pid": old, "pid_gone_before": gone, "pid": pid_of(package),
                   "flags_file_matches": same, "cache_before_ok": cache_ok(before, mode)})
    time.sleep(settle)
    stop_browser(package)
    after = receipt(package)
    sample.update({"cached_after": after, "cache_after_ok": cache_ok(after, mode)})
    sample["valid"] = bool(sample_ok(sample))
    return sample


def complete(result):
    expected = {(b, m) for b in range(result["blocks"]) for m in MODES}
    rows = result.get("rows", [])
    return (not result.get("error") and result.get("flags_restored") and result.get("shipped_cache_reprimed")
            and result.get("compile_reset") and result.get("same_apk") and result.get("compile_ok")
            and "speed" in result.get("dexopt_before", [])
            and result.get("dexopt_before") == result.get("dexopt_after")
            and re.fullmatch(r"[a-f0-9]{64}", result.get("apk_sha256", ""))
            and result.get("installed_sha_before") == result.get("installed_sha_after") == result.get("apk_sha256")
            and len(rows) == len(expected) and {(r["block"], r["mode"]) for r in rows} == expected
            and all(r["warmup"]["receipt_verified"] and len(r["samples"]) == result["runs"]
                    and all(sample_ok(s) for s in r["samples"]) for r in rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--apk", required=True)
    ap.add_argument("--build-info", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blocks", type=int, default=4)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--settle", type=float, default=6)
    ap.add_argument("--socket", default="chrome_devtools_remote")
    a = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", a.package):
        ap.error("invalid Android package")
    if not (2 <= a.blocks <= 8 and a.blocks % 2 == 0 and 2 <= a.runs <= 10 and 3 <= a.settle <= 15):
        ap.error("bounded even blocks >=2, runs>=2 and settle>=3 required")
    info = Path(a.build_info).read_text()
    expected_sha = re.search(r"(?m)^--- sha256\n([a-f0-9]{64})$", info)
    if not expected_sha or any(p not in info.splitlines() for p in ["0016-swiftra-speedpack.py", "0021-swiftra-keystore-oscrypt.patch"]):
        ap.error("source build with 0016+0021 and APK SHA required")
    apk_sha = hashlib.sha256(Path(a.apk).read_bytes()).hexdigest()
    if apk_sha != expected_sha.group(1):
        ap.error("APK does not match source BUILD_INFO")
    os.makedirs(a.out, exist_ok=True)
    res = {"package": a.package, "blocks": a.blocks, "runs": a.runs, "settle_s": a.settle, "modes": MODES,
           "metric": "am start -W TotalTime; process-cold, not TTFD/LCP/physical/current-Chrome proof",
           "compile_mode": "speed AOT; diagnostic, not install-default verify", "apk_sha256": apk_sha,
           "driver_commit": os.environ.get("GITHUB_SHA"),
           "rows": [], "no_direct_preference_edits": True, "security_settings": "unchanged, performance-only allowlist",
           "flags_restored": False, "shipped_cache_reprimed": False, "compile_reset": False}
    snapshot, disposable, comp, flags_snapshotted = None, False, None, False
    try:
        root_device()  # Must precede APK installation, root edits and cleanup eligibility.
        disposable = True
        res["device"] = {p: checked_adb("shell", "getprop", p).decode().strip() for p in
                         ("ro.hardware", "ro.product.cpu.abi", "ro.build.version.sdk")}
        snapshot = snapshot_flags()
        flags_snapshotted = True
        prepare_browser(a.package, a.apk, a.out)
        checked_adb("shell", "settings", "put", "global", "adb_enabled", "1")
        checked_adb("shell", "am", "set-debug-app", "--persistent", a.package)
        comp = resolve_launcher(a.package)
        if not comp:
            raise RuntimeError("launcher unavailable")
        res["installed_sha_before"] = installed_sha(a.package)
        if res["installed_sha_before"] != apk_sha:
            raise RuntimeError("installed APK hash mismatch")
        stop_browser(a.package)
        out = checked_adb("shell", "cmd", "package", "compile", "-m", "speed", "-f", a.package, timeout=900)
        res["compile_ok"] = out.strip() == b"Success"
        res["dexopt_before"] = dexopt_status(a.package)
        if not res["compile_ok"] or "speed" not in res["dexopt_before"]:
            raise RuntimeError("fixed AOT compilation state not verified")
        for block in range(a.blocks):
            for i, mode in enumerate(block_order(block)):
                nonce = "b%dm%d" % (block, i)
                warm = activate(a.package, comp, mode, nonce, a.socket, a.settle)
                row = {"block": block, "position": i, "mode": mode, "warmup": warm, "samples": []}
                res["rows"].append(row)
                for _ in range(a.runs):
                    sample = cold_sample(a.package, comp, mode, mode_flags(mode, nonce), a.settle)
                    row["samples"].append(sample)
                    if not sample["valid"]:
                        raise RuntimeError("invalid cold sample or Java cache receipt")
                print("STARTUP_ABLATION_BLOCK", block, mode, "median_ms=" + str(median([s["total_ms"] for s in row["samples"]])), flush=True)
                Path(a.out, "startup_ablation.json").write_text(json.dumps(res, indent=1) + "\n")
        res["dexopt_after"] = dexopt_status(a.package)
        if res["dexopt_after"] != res["dexopt_before"]:
            raise RuntimeError("compilation state changed during ablation")
        res["installed_sha_after"] = installed_sha(a.package)
        res["same_apk"] = res["installed_sha_after"] == res["installed_sha_before"] == apk_sha
    except Exception as e:  # fixed errors or type only; never print private prefs/command-line data
        res["error"] = str(e) if type(e) is RuntimeError else type(e).__name__ + " (private details withheld)"
    finally:
        if disposable:
            if comp:
                try:
                    activate(a.package, comp, "shipped", "cleanup", a.socket, a.settle)
                    res["shipped_cache_reprimed"] = True
                except Exception as e:
                    res["cache_restore_error"] = type(e).__name__
            try:
                stop_browser(a.package)
                res["flags_restored"] = bool(restore_flags(snapshot)) if flags_snapshotted else False
                checked_adb("shell", "cmd", "package", "compile", "--reset", a.package, timeout=300)
                res["compile_reset"] = "verify" in dexopt_status(a.package)
            except Exception as e:
                res["restore_error"] = type(e).__name__
    res["summary"] = summarize(res["rows"], a.blocks, a.runs)
    res["candidate_promoted"] = False
    res["verdict"] = "measured" if complete(res) else "partial" if res["rows"] else "not_run"
    Path(a.out, "startup_ablation.json").write_text(json.dumps(res, indent=1) + "\n")
    print("STARTUP_ABLATION", "MEASURED" if res["verdict"] == "measured" else "NOT_RUN", "rows=" + str(len(res["rows"])),
          "restored=" + str(res["flags_restored"]), res.get("error", ""), flush=True)
    return 0 if res["verdict"] == "measured" else 2


if __name__ == "__main__":
    sys.exit(main())
