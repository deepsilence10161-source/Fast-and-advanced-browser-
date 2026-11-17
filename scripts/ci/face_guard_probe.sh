#!/bin/bash
# Usage: face_guard_probe.sh <out-dir>
# Compiles the REAL FaceGrayConverter + PresenceFaceAnalyzer plus the probe against the SDK android.jar, dexes it with d8,
# runs it with app_process on the CURRENT adb device against tests/fixtures/face_guard/*.jpg and writes <out>/face_probe.txt.
# Device-level analyzer evidence only: it does NOT exercise the camera, the APK, Settings or the lock UI.
set -u
OUT=${1:?out dir}; mkdir -p "$OUT"; L="$OUT/face_probe.txt"; : > "$L"
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/usr/local/lib/android/sdk}}
D8=$(ls -d "$SDK"/build-tools/*/d8 2>/dev/null | sort -V | tail -1)
AJ=$(ls -d "$SDK"/platforms/android-*/android.jar 2>/dev/null | sort -V | tail -1)
[ -x "$D8" ] && [ -f "$AJ" ] || { echo "FACE_PROBE NOT_RUN no d8/android.jar under $SDK" | tee -a "$L"; exit 2; }
W=$(mktemp -d); P=tools/face_guard
F=$P/src/org/chromium/chrome/browser/swiftra/faceguard
javac -nowarn -Xlint:none -cp "$AJ" -d "$W/cls" $F/FaceGrayConverter.java $F/PresenceFaceAnalyzer.java \
  $P/device_probe/org/chromium/chrome/browser/swiftra/faceguard/FaceProbeBridge.java $P/device_probe/FaceProbeMain.java 2>&1 | grep -v "^Note:" | tee -a "$L"
[ -d "$W/cls" ] || { echo "FACE_PROBE FAIL compile" | tee -a "$L"; exit 1; }
"$D8" --min-api 29 --lib "$AJ" --output "$W" $(find "$W/cls" -name '*.class') 2>&1 | tee -a "$L"
timeout 60 adb wait-for-device
adb shell rm -rf /data/local/tmp/fgprobe; adb shell mkdir -p /data/local/tmp/fgprobe/img
adb push "$W/classes.dex" /data/local/tmp/fgprobe/probe.dex >/dev/null
adb push tests/fixtures/face_guard/. /data/local/tmp/fgprobe/img/ >/dev/null
echo "device abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r') android=$(adb shell getprop ro.build.version.release | tr -d '\r')" | tee -a "$L"
timeout 240 adb shell "CLASSPATH=/data/local/tmp/fgprobe/probe.dex app_process /system/bin FaceProbeMain /data/local/tmp/fgprobe/img" 2>&1 | tr -d '\r' | tee -a "$L"
grep -q FACE_PROBE_DONE "$L" || { echo "FACE_PROBE FAIL probe did not finish" | tee -a "$L"; exit 1; }
