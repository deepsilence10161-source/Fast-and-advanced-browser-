#!/bin/bash
# emulator-runner के अंदर एक line में चलाने हेतु wrapper
set -u
T=$1; OUT=out/$T; mkdir -p "$OUT"; timeout 120 adb wait-for-device; timeout 30 adb logcat -c
case "$T" in
  chrome_ref) timeout 1500 python3 scripts/ui_capture.py --package com.android.chrome --label "$T" --out "$OUT" ;;
  chromium_*) timeout 1500 python3 scripts/ui_capture.py --package org.chromium.chrome --label "$T" --out "$OUT" --apk "$(find dl -name ChromePublic.apk | head -1)" ;;
esac
echo "ui_capture exit=$?" | tee -a "$OUT/journey.log"
# synthetic long-chat fixture in the SAME browser on the emulator (not real Arena)
PKG=$([ "$T" = chrome_ref ] && echo com.android.chrome || echo org.chromium.chrome)
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
timeout 20 adb forward tcp:9222 "localabstract:${SOCK:-chrome_devtools_remote}"
timeout 200 python3 scripts/ci/run_chat_fixture.py --platform "android-emulator:$T" --out "$OUT/chat_fixture" --timeout 180 2>&1 | tee "$OUT/chat_fixture.txt"
echo "chat_fixture exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
kill $HTTP_PID 2>/dev/null
timeout 60 adb logcat -d | grep -iE "chromium|chrome|FATAL|AndroidRuntime|ndk_translation|DEBUG" | tail -400 > "$OUT/logcat_tail.txt"
exit 0
