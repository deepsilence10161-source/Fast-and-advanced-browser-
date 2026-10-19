#!/bin/bash
# emulator-runner के अंदर एक line में चलाने हेतु wrapper
set -u
T=$1; OUT=out/$T; mkdir -p "$OUT"; timeout 120 adb wait-for-device; timeout 20 adb logcat -G 16M >/dev/null 2>&1; timeout 30 adb logcat -c
# source build (branding patch के बाद package बदल सकता है): package BUILD_INFO के aapt2 badging से
ART_PKG=$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "$OUT/BUILD_INFO.txt" 2>/dev/null | head -1); ART_PKG=${ART_PKG:-org.chromium.chrome}
case "$T" in
  chrome_ref) timeout 2400 python3 scripts/ui_capture.py --package com.android.chrome --label "$T" --out "$OUT" ;;
  chromium_*) timeout 2400 python3 scripts/ui_capture.py --package "$ART_PKG" --label "$T" --out "$OUT" --apk "$(find dl -name ChromePublic.apk | head -1)" ;;
esac
echo "ui_capture exit=$?" | tee -a "$OUT/journey.log"
# static security + branding audit of the tested APK (tools/security/apk_audit.py; no device needed)
APK_FILE=$(find dl -name ChromePublic.apk 2>/dev/null | head -1)
if [ -n "$APK_FILE" ]; then
  timeout 600 python3 tools/security/apk_audit.py --apk "$APK_FILE" --json "$OUT/apk_audit.json" 2>&1 | grep -v "^WARNING\|DEBUG" | tee "$OUT/apk_audit.txt"
  echo "apk_audit exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
fi
# synthetic long-chat fixture in the SAME browser on the emulator (not real Arena)
PKG=$([ "$T" = chrome_ref ] && echo com.android.chrome || echo "$ART_PKG")
(cd experiments/chat-rendering && exec python3 -m http.server 8000 --bind 127.0.0.1 >/dev/null 2>&1) &
HTTP_PID=$!; sleep 1
timeout 20 adb reverse tcp:8000 tcp:8000
timeout 40 adb shell am start -a android.intent.action.VIEW -d "http://127.0.0.1:8000/fixture.html?n=300" "$PKG"
sleep 4
for i in 1 2 3 4 5 6; do
  ALLS=$(timeout 20 adb shell cat /proc/net/unix | grep -o '@[A-Za-z0-9_.]*devtools_remote[A-Za-z0-9_]*' | tr -d '@' | sort -u | tr '\n' ' ')
  SOCK=$(echo "$ALLS" | tr ' ' '\n' | grep -E '^chrome_devtools_remote' | head -1)
  [ -n "$SOCK" ] && break; sleep 5
done
echo "devtools sockets: ${ALLS:-none}; using: ${SOCK:-none}" | tee -a "$OUT/journey.log"
timeout 30 adb shell uiautomator dump /sdcard/fx.xml >/dev/null 2>&1; timeout 15 adb pull /sdcard/fx.xml "$OUT/chat_fixture_ui.xml" >/dev/null 2>&1
timeout 15 adb exec-out screencap -p > "$OUT/chat_fixture_device.png"
# सही platform label: Redroid (container, native arm64) बनाम emulator
case "$(timeout 15 adb shell getprop ro.hardware | tr -d '\r')" in redroid) PLAT=android-redroid-container;; ranchu|goldfish) PLAT=android-emulator;; *) PLAT=android-device;; esac
timeout 20 adb forward tcp:9222 "localabstract:${SOCK:-chrome_devtools_remote}"
timeout 200 python3 scripts/ci/run_chat_fixture.py --platform "$PLAT:$T" --out "$OUT/chat_fixture" --timeout 180 2>&1 | tee "$OUT/chat_fixture.txt"
echo "chat_fixture exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
kill $HTTP_PID 2>/dev/null
# Swiftra Shield (patches/0006): local canaries + Google's harmless test pages -> interstitial
if [ "$T" != chrome_ref ]; then
  timeout 1500 python3 scripts/ci/shield_e2e.py --package "$PKG" --out "$OUT/shield" 2>&1 | tee "$OUT/shield_e2e.txt"
  echo "shield_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # c2d: browser-initiated traffic from a cold start (NetLog from process start; last step: may use adb root)
  timeout 300 python3 scripts/ci/startup_netlog.py --package "$PKG" --out "$OUT/startup" 2>&1 | tee "$OUT/startup_netlog.txt"
  echo "startup_netlog exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # patches/0010: HTTPS-First (balanced) + third-party cookies blocked, checked by behaviour (local mapped hosts)
  timeout 240 python3 scripts/ci/advanced_e2e.py --package "$PKG" --out "$OUT/advanced" 2>&1 | tee "$OUT/advanced_e2e.txt"
  echo "advanced_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # patches/0020: signed update channel -> upstream "Update Swiftra" menu item/badge (signed vs tampered manifest)
  timeout 300 python3 scripts/ci/update_e2e.py --package "$PKG" --out "$OUT/update" 2>&1 | tee "$OUT/update_e2e.txt"
  echo "update_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # Speed (0016 Speed Pack + 0012 ad blocker): same APK, chromium_defaults vs swiftra, alternated; local mapped hosts
  timeout 1500 python3 -u scripts/ci/speed_e2e.py --package "$PKG" --out "$OUT/speed" --socket "${SOCK:-chrome_devtools_remote}" 2>&1 | tee "$OUT/speed_e2e.txt"
  echo "speed_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  timeout 90 adb logcat -b all -d 2>/dev/null | gzip -6 > "$OUT/logcat_speed_e2e.txt.gz"   # kept before any later logcat -c
  # repeat visits (SPA with cached assets; cold restart + warm): chromium_defaults / swiftra / swiftra_lcpp candidate
  timeout 900 python3 -u scripts/ci/repeat_e2e.py --package "$PKG" --out "$OUT/repeat" --socket "${SOCK:-chrome_devtools_remote}" 2>&1 | tee "$OUT/repeat_e2e.txt"
  echo "repeat_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  timeout 90 adb logcat -b all -d 2>/dev/null | gzip -6 > "$OUT/logcat_repeat_e2e.txt.gz"   # kept before any later logcat -c
  # cold-start trace (diagnostic for startup speed work; never fails the job)
  timeout 240 python3 scripts/ci/startup_trace.py --package "$PKG" --out "$OUT/startup_trace" 2>&1 | tee "$OUT/startup_trace.txt"
  echo "startup_trace exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # ART compile state vs cold start (install/verify vs speed-profile vs speed): is a baseline profile worth it?
  timeout 1200 python3 scripts/ci/art_startup.py --package "$PKG" --out "$OUT/art_startup" 2>&1 | tee "$OUT/art_startup.txt"
  echo "art_startup exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
fi
timeout 60 adb logcat -d | grep -iE "chromium|chrome|FATAL|AndroidRuntime|ndk_translation|DEBUG" | tail -400 > "$OUT/logcat_tail.txt"
exit 0
