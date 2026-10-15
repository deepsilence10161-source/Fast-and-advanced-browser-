#!/bin/bash
# emulator-runner के अंदर एक line में चलाने हेतु wrapper
set -u
T=$1; OUT=out/$T; mkdir -p "$OUT"; adb wait-for-device; adb logcat -c
case "$T" in
  chrome_ref) timeout 1500 python3 scripts/ui_capture.py --package com.android.chrome --label "$T" --out "$OUT" ;;
  chromium_*) timeout 1500 python3 scripts/ui_capture.py --package org.chromium.chrome --label "$T" --out "$OUT" --apk "$(find dl -name ChromePublic.apk | head -1)" ;;
esac
echo "ui_capture exit=$?" | tee -a "$OUT/journey.log"
adb logcat -d | grep -iE "chromium|chrome|FATAL|AndroidRuntime|ndk_translation|DEBUG" | tail -400 > "$OUT/logcat_tail.txt"
exit 0
