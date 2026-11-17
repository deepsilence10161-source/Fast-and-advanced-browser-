#!/usr/bin/env python3
"""FACE_GUARD_E2E (face scenarios): the emulator's FRONT camera renders a committed image, so the real camera2 pipeline
(FaceCameraSource -> FaceGrayConverter -> android.media.FaceDetector -> FaceGuardPolicy -> overlay/tab switcher) is
exercised end to end on a real Android runtime. Used only on the x64 emulator (Redroid has no camera).

  --scenario one  : one face in view  -> the browser must UNLOCK (lock overlay disappears) and stay unlocked
  --scenario two  : two faces in view -> the browser must STAY LOCKED with the "More than one face" message
  --variant rot90 : sensor frame rotated so the app sees the picture upright (acceptance)
  --variant rot0  : upright sensor frame (the app sees it sideways): INFORMATION ONLY, reported NOT_RUN, never PASS

Prints `FACE_GUARD_E2E <id> PASS|FAIL|NOT_RUN <detail>` plus a timeline of overlay observations. The measured times
are uiautomator-polling bounds (about +-1.5 s); they are NOT the policy latency (lockDelay 300 ms).
"""
import argparse
import json
import re
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import face_guard_e2e as G  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scenario", choices=["one", "two"], required=True)
    ap.add_argument("--variant", choices=["rot90", "rot0"], default="rot90")
    a = ap.parse_args()
    pkg = a.package
    os.makedirs(a.out, exist_ok=True)
    results = []

    def res(cid, status, detail=""):
        results.append({"id": cid, "status": status, "detail": detail})
        print(f"FACE_GUARD_E2E {cid} {status} {detail}", flush=True)

    G.adb("root", timeout=30)
    time.sleep(3)
    G.adb("wait-for-device", timeout=60)
    abi = G.sh("getprop ro.product.cpu.abi")
    print(f"FACE_GUARD_E2E env package={pkg} abi={abi} scenario={a.scenario} variant={a.variant}", flush=True)
    try:
        from ui_capture import Device, launch, wait_ready
        dev = Device(pkg, a.out, lambda line: print("FACE_GUARD_E2E_UI", line, flush=True))
        G.sh(f"pm grant {pkg} android.permission.CAMERA")
        G.adb("shell", "am", "force-stop", pkg)
        launch(dev)
        ready = wait_ready(dev, seconds=180)
        G.open_privacy_settings(pkg)
        x = G.scroll_to_switch()
        n = G.find_node(x, text=G.TITLE)
        if not n:
            res("H00_enable", "FAIL", f"switch row not found; browser_ready={ready}")
            raise SystemExit(finish(a, results, abi, 1))
        G.tap_bounds(n["bounds"])
        time.sleep(2)
        pref = G.pref_enabled(pkg)
        res("H00_enable", "PASS" if pref == "true" else "FAIL", f"pref_enabled={pref} (camera pre-granted with pm grant)")
        G.adb("shell", "am", "force-stop", pkg)
        time.sleep(1)
        t0 = time.time()
        launch(dev)
        timeline, first_unlock, ever_other = [], None, False
        last_text = ""
        while time.time() - t0 < 60:
            xml = G.dump()
            if "default browser" in xml:
                G.dismiss_default_browser()
                continue
            vis = G.overlay_visible(xml)
            txt = G.overlay_text(xml)
            t = round(time.time() - t0, 1)
            if not timeline or timeline[-1][1] != vis or txt != last_text:
                timeline.append((t, vis, txt))
            last_text = txt
            if "More than one face" in txt:
                ever_other = True
            if not vis and first_unlock is None and G.sh(f"pidof {pkg}"):
                first_unlock = t
                if a.scenario == "one":
                    break
            if a.scenario == "two" and t > 30:
                break
            time.sleep(0.6)
        print("FACE_GUARD_E2E timeline", json.dumps(timeline), flush=True)
        try:
            open(os.path.join(a.out, f"{a.scenario}_{a.variant}_end.png"), "wb").write(G.screen_png())
            open(os.path.join(a.out, f"{a.scenario}_{a.variant}_end.xml"), "w").write(G.dump())
        except Exception:  # noqa: BLE001
            pass
        cam = G.camera_client(pkg)
        if a.scenario == "one":
            stable = None
            if first_unlock is not None:
                time.sleep(10)
                stable = not G.overlay_visible(G.dump())
            detail = (f"first_unlocked_after_launch_s={first_unlock} stayed_unlocked_10s_more={stable} "
                      f"app_holds_camera={cam} variant={a.variant}")
            if a.variant != "rot90":
                res("H01_one_face_unlocks_orientation_probe", "NOT_RUN", "information only: " + detail)
            elif first_unlock is not None and stable:
                res("H01_one_face_unlocks", "PASS", detail)
            else:
                res("H01_one_face_unlocks", "FAIL", detail + f" timeline={timeline[:6]}")
        else:
            still = G.overlay_visible(G.dump())
            detail = (f"locked_throughout={first_unlock is None and still} message_seen_more_than_one_face={ever_other} "
                      f"app_holds_camera={cam} variant={a.variant}")
            if a.variant != "rot90":
                res("H02_two_faces_orientation_probe", "NOT_RUN", "information only: " + detail)
            elif first_unlock is None and still and ever_other:
                res("H02_two_faces_stay_locked", "PASS", detail)
            else:
                res("H02_two_faces_stay_locked", "FAIL", detail + f" timeline={timeline[:6]}")
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:  # noqa: BLE001
        print("FACE_GUARD_E2E harness_error", repr(e)[:300], flush=True)
        return 2
    return finish(a, results, abi, 0)


def finish(a, results, abi, rc):
    try:
        open(os.path.join(a.out, "logcat_tail.txt"), "w").write(G.adb("logcat", "-d", "-t", "4000", timeout=60))
        full = G.adb("logcat", "-d", "-t", "40000", timeout=90)
        keep = [l for l in full.splitlines() if "AccessibilityNodeInfoDumper" not in l and "uiautomator" not in l.lower()
                and re.search(r"com\.swiftra\.personaldev|FATAL|AndroidRuntime|tombstone|DEBUG|CameraService|Camera2|CameraDevice|ActivityManager: (Process|Start|Killing)|libc|SIGSEGV|ANR", l)]
        open(os.path.join(a.out, "logcat_filtered.txt"), "w").write("\n".join(keep[-3000:]))
        open(os.path.join(a.out, "logcat_crash.txt"), "w").write(G.adb("logcat", "-d", "-b", "crash", timeout=60))
    except Exception:  # noqa: BLE001
        pass
    c = G.summarize(results)
    json.dump({"scenario": a.scenario, "variant": a.variant, "abi": abi, "results": results, "summary": c},
              open(os.path.join(a.out, f"face_guard_face_{a.scenario}_{a.variant}.json"), "w"), indent=1)
    print(f"FACE_GUARD_E2E_SUMMARY pass={c['PASS']} fail={c['FAIL']} not_run={c['NOT_RUN']} abi={abi}", flush=True)
    return 1 if (c["FAIL"] or rc) else 0


if __name__ == "__main__":
    sys.exit(main())
