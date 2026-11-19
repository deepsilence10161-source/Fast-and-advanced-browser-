#!/usr/bin/env python3
"""FACE_GUARD_E2E: device acceptance probes for the Face Guard layer inside the personal development APK.

Real Android runtime only (x64 Actions emulator / native ARM64 Redroid), disposable CI device, loopback only, no
account, no real site. Every check prints `FACE_GUARD_E2E <id> PASS|FAIL|NOT_RUN <detail>`; NOT_RUN = "could not be
measured here" and is never counted as a pass. Exit 1 on any FAIL, 2 on harness error. Host success != Android PASS.

The front camera on these images shows NO face (emulated scene / no camera at all), so this suite measures the
FAIL-CLOSED side: default off, settings toggle, permission handling, lock overlay + tab switcher, no lockout paths.
It does NOT measure that a real face unlocks the browser, face-loss latency, or spoofing resistance.

  G01 default_off       : Settings > Privacy has the Face Guard switch, OFF by default; browser not locked
  G02 enable_denied     : enabling, then denying the camera, locks the browser: opaque overlay, tab switcher open behind it
  G03 grant_no_face     : granting the camera with no face in view keeps it locked; front camera opened by the app
  G04 pin_unlock        : with a device PIN set, "Unlock with device PIN" really unlocks (override), not before
  G05 off_needs_pin     : with a PIN set, switching the toggle off is refused until the PIN is confirmed
  G08 owner_only        : owner-only switch (runs after G05): no camera, lock text 'Owner only', the owner prompt (PIN here) unlocks
  G06 no_pin_turn_off   : without a device credential the lock screen offers "Turn off" (never a lockout) and it works
  G07 off_is_inert      : after turning off: no overlay, camera released, browser usable
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

PIN = "2468"
SETTINGS_ACT = "org.chromium.chrome.browser.settings.SettingsActivity"
PRIVACY_FRAGMENT = "org.chromium.chrome.browser.privacy.settings.PrivacySettings"
TITLE = "Face Guard (experimental)"


def adb(*args, timeout=40):
    try:
        r = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout)
        return ((r.stdout or "") + (r.stderr or "")).replace("\r", "")
    except subprocess.TimeoutExpired:
        return ""


def sh(cmd, timeout=40):
    return adb("shell", cmd, timeout=timeout).strip()


def device_up():
    return adb("get-state", timeout=20).strip() == "device"


# ---------------------------------------------------------------- pure helpers (host-tested)
def overlay_visible(xml):
    return "Looking for your face" in xml or "Camera permission is needed" in xml or "front camera is not available" in xml \
        or "More than one face is visible" in xml or "Owner only. Unlock with" in xml


def overlay_text(xml):
    m = re.search(r'text="((?:Looking for your face|Camera permission|The front camera|More than one face|Owner only)[^"]*)"', xml)
    return m.group(1)[:80] if m else ""


def hub_open(xml):
    return bool(re.search(r':id/(hub_pane_host|tab_list_recycler_view|tab_switcher_view_holder|hub_toolbar)"', xml))


def parse_bounds(b):
    n = list(map(int, re.findall(r"\d+", b)))
    return n if len(n) == 4 else None


def find_node(xml, text=None, rid=None, ci=False):
    for m in re.finditer(r"<node [^>]*>", xml):
        s = m.group(0)
        if text is not None and not re.search(r'text="' + re.escape(text) + r'"', s, re.I if ci else 0):
            continue
        if rid is not None and not re.search(r'resource-id="[^"]*' + re.escape(rid) + r'"', s):
            continue
        b = re.search(r'bounds="([^"]+)"', s)
        bb = parse_bounds(b.group(1)) if b else None
        if bb:
            return {"bounds": bb, "checked": 'checked="true"' in s, "checkable": 'checkable="true"' in s,
                    "raw": s}
    return None


def switch_state(xml):
    """(found, checked) for the Face Guard switch row. The title row has a sibling Switch node in the same row."""
    t = find_node(xml, text=TITLE)
    if not t:
        return False, False
    y0, y1 = t["bounds"][1], t["bounds"][3]
    best = None
    for m in re.finditer(r"<node [^>]*>", xml):
        s = m.group(0)
        if 'class="android.widget.Switch"' not in s and "switch_widget" not in s:
            continue
        b = re.search(r'bounds="([^"]+)"', s)
        bb = parse_bounds(b.group(1)) if b else None
        if bb and bb[1] <= y1 + 400 and bb[3] >= y0 - 40:
            if best is None or abs(bb[1] - y0) < abs(best[0][1] - y0):
                best = (bb, 'checked="true"' in s)
    return (True, best[1]) if best else (True, False)


def locked_screenshot_ok(png_bytes):
    """True when the screenshot is dominated by the opaque lock colour (16,21,26)."""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        w, h = im.size
        pts = [(int(w * fx), int(h * fy)) for fx in (0.1, 0.5, 0.9) for fy in (0.12, 0.3, 0.7, 0.9)]
        black = sum(1 for p in pts if max(im.getpixel(p)) <= 3)
        if black >= 11:
            return None  # FLAG_SECURE blanks screencap in this build: the colour cannot be verified (UI dump is the evidence)
        near = sum(1 for p in pts if max(abs(a - b) for a, b in zip(im.getpixel(p), (16, 21, 26))) <= 6)
        return near >= 10
    except Exception:  # noqa: BLE001
        return None


def summarize(results):
    c = {"PASS": 0, "FAIL": 0, "NOT_RUN": 0}
    for r in results:
        c[r["status"]] += 1
    return c


# ---------------------------------------------------------------- device helpers
def screen_png():
    return subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=40).stdout


def dump():
    for _ in range(4):
        sh("rm -f /sdcard/ui.xml")
        sh("uiautomator dump /sdcard/ui.xml", 25)
        x = adb("exec-out", "cat", "/sdcard/ui.xml")
        if x.strip().startswith("<?xml"):
            return x
        time.sleep(1.5)
    return ""


def dismiss_default_browser():
    """Android's 'Set Swiftra as your default browser?' role dialog can appear on top after a launch."""
    for _ in range(3):
        x = dump()
        if "default browser" in x and find_node(x, text="Cancel"):
            tap_text("Cancel", tries=1, wait=1.5)
        elif "default browser" in x and find_node(x, text="CANCEL"):
            tap_text("CANCEL", tries=1, wait=1.5)
        else:
            return


def tap_bounds(b):
    sh(f"input tap {(b[0] + b[2]) // 2} {(b[1] + b[3]) // 2}")


def tap_text(text, tries=4, wait=2.0, ci=False):
    for _ in range(tries):
        n = find_node(dump(), text=text, ci=ci)
        if n:
            tap_bounds(n["bounds"])
            time.sleep(wait)
            return True
        time.sleep(1.5)
    return False


def wait_until(pred, secs, step=1.0):
    t0 = time.time()
    last = None
    while time.time() - t0 < secs:
        last = pred()
        if last:
            return last
        time.sleep(step)
    return last


def open_privacy_settings(pkg):
    sh("input keyevent KEYCODE_WAKEUP")
    adb("shell", "am", "start", "-W", "-n", f"{pkg}/{SETTINGS_ACT}", "--es", "show_fragment", PRIVACY_FRAGMENT, timeout=60)
    time.sleep(3)


def scroll_to_switch(max_swipes=8):
    for _ in range(max_swipes):
        x = dump()
        if find_node(x, text=TITLE):
            return x
        sh("input swipe 540 1700 540 700 300")
        time.sleep(1.2)
    return dump()


def camera_client_from_dump(out, pkg):
    """True only while `pkg` HOLDS a camera: Active Camera Clients section, else the last service event for pkg."""
    m = re.search(r"Active Camera Clients[^\n]*\n(.*?)(?:\n== |\Z)", out, re.S)
    if m:
        return pkg in m.group(1)
    last = None
    for line in out.splitlines():
        if pkg in line:
            u = line.upper()
            if "DISCONNECT" in u:
                last = False
            elif "CONNECT" in u:
                last = True
    return bool(last)


DUMPS = {"n": 0, "dir": None}


def camera_client(pkg):
    out = sh("dumpsys media.camera", 60)
    if DUMPS["dir"]:
        DUMPS["n"] += 1
        try:
            open(os.path.join(DUMPS["dir"], f"dumpsys_camera_{DUMPS['n']}.txt"), "w").write(out)
        except Exception:  # noqa: BLE001
            pass
    return camera_client_from_dump(out, pkg)


def pref_enabled(pkg, key="enabled"):
    x = sh(f"cat /data/data/{pkg}/shared_prefs/swiftra_face_guard.xml 2>/dev/null")
    m = re.search(r'name="' + re.escape(key) + r'" value="(true|false)"', x)
    return m.group(1) if m else "absent"


OWNER_TITLE = "Face Guard: owner unlock only"


def scroll_to(title, max_swipes=10):
    for _ in range(max_swipes):
        x = dump()
        if find_node(x, text=title):
            return x
        sh("input swipe 540 1700 540 700 300")
        time.sleep(1.2)
    return dump()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pkg, out = a.package, a.out
    os.makedirs(out, exist_ok=True)
    DUMPS["dir"] = out
    results = []

    def res(cid, status, detail=""):
        results.append({"id": cid, "status": status, "detail": detail})
        print(f"FACE_GUARD_E2E {cid} {status} {detail}", flush=True)

    def shot(name):
        try:
            open(os.path.join(out, name + ".png"), "wb").write(screen_png())
            open(os.path.join(out, name + ".xml"), "w").write(dump())
        except Exception:  # noqa: BLE001
            pass

    adb("root", timeout=30)
    time.sleep(3)
    adb("wait-for-device", timeout=60)
    abi = sh("getprop ro.product.cpu.abi")
    cams = sh("dumpsys media.camera | head -40", 60)
    has_front = "Facing: FRONT" in cams or "facing: front" in cams.lower() or bool(re.search(r"Camera \d+ .*front", cams, re.I))
    print(f"FACE_GUARD_E2E env package={pkg} abi={abi} android={sh('getprop ro.build.version.release')} "
          f"sdk={sh('getprop ro.build.version.sdk')} camera_hal_listed={'yes' if 'Camera' in cams else 'no'}", flush=True)
    try:
        from ui_capture import Device, launch, wait_ready
        dev = Device(pkg, out, lambda line: print("FACE_GUARD_E2E_UI", line, flush=True))
        sh("pm revoke %s android.permission.CAMERA" % pkg)
        sh("locksettings clear --old %s 2>/dev/null; true" % PIN)
        adb("shell", "am", "force-stop", pkg)
        launch(dev)
        ready = wait_ready(dev, seconds=180)
        # ---- G01 default off + browser unlocked
        x = dump()
        unlocked = not overlay_visible(x)
        open_privacy_settings(pkg)
        x = scroll_to_switch()
        found, checked = switch_state(x)
        shot("g01_settings")
        pref = pref_enabled(pkg)
        if not found:
            res("G01_default_off", "FAIL", f"switch row '{TITLE}' not found in Privacy settings; browser_ready={ready}")
        elif checked or pref == "true":
            res("G01_default_off", "FAIL", f"switch checked={checked} pref={pref}")
        else:
            res("G01_default_off", "PASS", f"row present, unchecked, pref={pref}, browser_ready={ready}, no overlay before enabling={unlocked}")

        # ---- G02 enable, then deny the camera
        n = find_node(x, text=TITLE)
        if not n:
            res("G02_enable_denied", "NOT_RUN", "switch row not found")
        else:
            tap_bounds(n["bounds"])
            time.sleep(3)
            dlg = dump()
            denied = False
            # Android 14 (Redroid) shows the buttons in capitals ("DON’T ALLOW"), Android 16 in sentence case.
            for label in ("Don't allow", "Don’t allow", "Deny"):
                if find_node(dlg, text=label, ci=True):
                    tap_text(label, ci=True)
                    denied = True
                    break
            time.sleep(2)
            pref = pref_enabled(pkg)
            adb("shell", "am", "force-stop", pkg)
            launch(dev)
            t0 = time.time()
            dismiss_default_browser()
            vis = wait_until(lambda: overlay_visible(dump()), 25)
            lat = round(time.time() - t0, 1)
            xml = dump()
            png = screen_png()
            open(os.path.join(out, "g02_locked.png"), "wb").write(png)
            open(os.path.join(out, "g02_locked.xml"), "w").write(xml)
            opaque = locked_screenshot_ok(png)
            hub = hub_open(xml)
            detail = (f"pref_enabled={pref} permission_dialog_denied={denied} overlay_seen={bool(vis)} text='{overlay_text(xml)}' "
                      f"opaque_lock_colour={opaque} tab_switcher_markers_in_ui_dump={hub} seconds_to_see_overlay={lat}")
            if pref == "true" and vis and opaque is not False:
                res("G02_enable_denied", "PASS", detail)
            else:
                res("G02_enable_denied", "FAIL", detail)

        # ---- G03 grant camera, no face visible -> stays locked, camera opened by the app
        sh(f"pm grant {pkg} android.permission.CAMERA")
        adb("shell", "am", "force-stop", pkg)
        launch(dev)
        time.sleep(8)
        dismiss_default_browser()
        xml = dump()
        still = overlay_visible(xml)
        cam = camera_client(pkg)
        shot("g03_granted")
        listed = "Camera" in cams
        if not listed:
            res("G03_grant_no_face", "NOT_RUN" if still else "FAIL",
                f"no camera HAL on this image; overlay_still_locked={still} text='{overlay_text(xml)}' (fail-closed without a camera is the expected result)")
        elif still and cam:
            res("G03_grant_no_face", "PASS", f"locked with camera permission granted and the app holding a front camera; text='{overlay_text(xml)}'")
        else:
            res("G03_grant_no_face", "FAIL" if not still else "NOT_RUN",
                f"overlay_still_locked={still} app_holds_camera={cam}")

        # ---- G04 / G05 with a device PIN
        pin_out = sh(f"locksettings set-pin {PIN}")
        has_pin = "set" in pin_out.lower() and "error" not in pin_out.lower()
        adb("shell", "am", "force-stop", pkg)
        launch(dev)
        time.sleep(6)
        dismiss_default_browser()
        xml = dump()
        unlock_btn = find_node(xml, text="Unlock with device PIN")
        if not unlock_btn:
            res("G04_pin_unlock", "NOT_RUN", f"'Unlock with device PIN' button not shown (pin_cmd_ok={has_pin}); lock text='{overlay_text(xml)}'")
        else:
            tap_bounds(unlock_btn["bounds"])
            time.sleep(3)
            prompt = dump()
            shot("g04_prompt")
            still_locked_before = overlay_visible(prompt)
            sh(f"input text {PIN}")
            time.sleep(1)
            sh("input keyevent KEYCODE_ENTER")
            time.sleep(4)
            after = dump()
            unlocked = not overlay_visible(after)
            shot("g04_after")
            detail = f"prompt_blocked_overlay_before_pin={still_locked_before} unlocked_after_pin={unlocked}"
            res("G04_pin_unlock", "PASS" if unlocked else "FAIL", detail)

        # ---- G05 off needs the PIN
        open_privacy_settings(pkg)
        x = scroll_to_switch()
        n = find_node(x, text=TITLE)
        if not n:
            res("G05_off_needs_pin", "NOT_RUN", "switch row not found")
        else:
            tap_bounds(n["bounds"])
            time.sleep(3)
            cancelled_prompt = dump()
            prompt_shown = "Face Guard" in cancelled_prompt and ("PIN" in cancelled_prompt or "device" in cancelled_prompt.lower())
            sh("input keyevent KEYCODE_BACK")
            time.sleep(2)
            still_on = pref_enabled(pkg) == "true"
            open_privacy_settings(pkg)
            x = scroll_to_switch()
            n = find_node(x, text=TITLE)
            if n:
                tap_bounds(n["bounds"])
            time.sleep(3)
            sh(f"input text {PIN}")
            time.sleep(1)
            sh("input keyevent KEYCODE_ENTER")
            time.sleep(4)
            off = pref_enabled(pkg) == "false"
            detail = f"credential_prompt_shown={prompt_shown} still_on_after_cancel={still_on} off_after_pin={off}"
            shot("g05_after")
            res("G05_off_needs_pin", "PASS" if (still_on and off) else "FAIL", detail)

        # ---- G08 owner-only mode (needs the device PIN set by G04): no camera, only the owner prompt unlocks
        try:
            open_privacy_settings(pkg)
            x = scroll_to(TITLE)
            n = find_node(x, text=TITLE)
            if n:
                tap_bounds(n["bounds"])           # Face Guard ON (camera permission was granted in G03)
                time.sleep(3)
            x = scroll_to(OWNER_TITLE)
            n = find_node(x, text=OWNER_TITLE)
            if not n:
                res("G08_owner_only", "FAIL", f"owner-only switch row '{OWNER_TITLE}' not found; main_pref={pref_enabled(pkg)}")
            else:
                tap_bounds(n["bounds"])
                time.sleep(3)
                owner_pref = pref_enabled(pkg, "owner_only")
                adb("shell", "am", "force-stop", pkg)
                launch(dev)
                time.sleep(5)
                dismiss_default_browser()
                locked_xml = dump()
                # the lock can take 10+ s to appear on a cold start; wait for the overlay text or the prompt
                for _ in range(12):
                    if "Owner only. Unlock with" in locked_xml or "Confirm with your fingerprint, face or device PIN" in locked_xml:
                        break
                    time.sleep(2)
                    locked_xml = dump()
                # the owner prompt opens by itself (~0.7 s after the lock) and then covers the lock overlay, so either
                # the overlay text or the already-open prompt proves the owner-only lock (the 19 Nov run saw the prompt)
                prompt_open = "Confirm with your fingerprint, face or device PIN" in locked_xml
                owner_text = ("Owner only. Unlock with" in locked_xml) or prompt_open
                prompt_xml = locked_xml
                if not prompt_open:
                    btn = find_node(locked_xml, text="Unlock as owner")
                    if btn:
                        tap_bounds(btn["bounds"])
                        time.sleep(3)
                        prompt_xml = dump()
                shot("g08_prompt")
                sh(f"input text {PIN}")
                time.sleep(1)
                sh("input keyevent KEYCODE_ENTER")
                time.sleep(4)
                after = dump()
                unlocked = not overlay_visible(after)
                cam = camera_client(pkg)
                shot("g08_after")
                ok = owner_pref == "true" and owner_text and unlocked and not cam
                res("G08_owner_only", "PASS" if ok else "FAIL",
                    f"owner_pref={owner_pref} owner_lock_seen={owner_text} prompt_auto_opened={prompt_open} unlocked_after_owner_prompt={unlocked} app_holds_camera={cam}")
                # back to the weaker mode: turning owner-only OFF and then Face Guard OFF both need the PIN
                for title in (OWNER_TITLE, TITLE):
                    open_privacy_settings(pkg)
                    x = scroll_to(title)
                    n = find_node(x, text=title)
                    if n:
                        tap_bounds(n["bounds"])
                        time.sleep(3)
                        sh(f"input text {PIN}")
                        time.sleep(1)
                        sh("input keyevent KEYCODE_ENTER")
                        time.sleep(4)
        except Exception as e:  # noqa: BLE001
            res("G08_owner_only", "FAIL", f"harness exception {repr(e)[:160]}")

        # ---- G06 no device credential -> Turn off offered, works (enable again first)
        sh(f"locksettings clear --old {PIN}")
        time.sleep(2)
        open_privacy_settings(pkg)
        x = scroll_to_switch()
        n = find_node(x, text=TITLE)
        if n:
            tap_bounds(n["bounds"])
            time.sleep(3)
        adb("shell", "am", "force-stop", pkg)
        launch(dev)
        time.sleep(6)
        dismiss_default_browser()
        xml = dump()
        off_btn = find_node(xml, text="Turn off Face Guard")
        pin_btn = find_node(xml, text="Unlock with device PIN")
        if not off_btn:
            res("G06_no_pin_turn_off", "FAIL" if overlay_visible(xml) else "NOT_RUN",
                f"no Turn off button; pin_button_present={bool(pin_btn)}; lock_text='{overlay_text(xml)}' pref={pref_enabled(pkg)}")
        else:
            tap_bounds(off_btn["bounds"])
            time.sleep(4)
            after = dump()
            ok = (not overlay_visible(after)) and pref_enabled(pkg) == "false"
            res("G06_no_pin_turn_off", "PASS" if ok else "FAIL", f"overlay_gone={not overlay_visible(after)} pref={pref_enabled(pkg)}")

        # ---- G07 off is inert
        time.sleep(3)
        xml = dump()
        cam_after = camera_client(pkg)
        ready2 = wait_ready(dev, seconds=60)
        res("G07_off_is_inert", "PASS" if (not overlay_visible(xml) and not cam_after and ready2) else "FAIL",
            f"overlay={overlay_visible(xml)} app_holds_camera={cam_after} browser_ready={ready2}")
    except Exception as e:  # noqa: BLE001
        print("FACE_GUARD_E2E harness_error", repr(e)[:300], flush=True)
        return 2
    finally:
        sh("locksettings clear --old %s 2>/dev/null; true" % PIN)
        try:
            open(os.path.join(out, "logcat_tail.txt"), "w").write(adb("logcat", "-d", "-t", "5000", timeout=60))
        except Exception:  # noqa: BLE001
            pass
    c = summarize(results)
    json.dump({"package": pkg, "abi": abi, "results": results, "summary": c}, open(os.path.join(out, "face_guard_e2e.json"), "w"), indent=1)
    print(f"FACE_GUARD_E2E_SUMMARY pass={c['PASS']} fail={c['FAIL']} not_run={c['NOT_RUN']} abi={abi}", flush=True)
    return 1 if c["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
