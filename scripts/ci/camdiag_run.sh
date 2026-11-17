#!/bin/bash
# CI-only: what does the emulated FRONT camera deliver, and does android.media.FaceDetector see a face at 0/90/180/270?
# Usage: camdiag_run.sh <outdir> <helper.apk>   (current adb device). No browser involved.
set -u
OUT=$1; APK=$2; mkdir -p "$OUT"
adb wait-for-device; adb root >/dev/null 2>&1; sleep 2; adb wait-for-device
adb install -r "$APK" | tail -1
adb shell pm grant com.swiftra.cliphelper android.permission.CAMERA
adb logcat -c
adb shell am start -W -n com.swiftra.cliphelper/.Main --es mode cam >/dev/null
for i in $(seq 1 40); do
  sleep 1
  adb logcat -d -s CLIPHELPER:I | grep -q "CAMDIAG done" && break
done
adb logcat -d -s CLIPHELPER:I | grep CAMDIAG | tee "$OUT/camdiag.txt"
adb pull /sdcard/Android/data/com.swiftra.cliphelper/files/frame.pgm "$OUT/frame.pgm" 2>&1 | tail -1
ls -la "$OUT"
