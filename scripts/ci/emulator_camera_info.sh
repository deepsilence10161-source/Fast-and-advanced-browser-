#!/bin/bash
# Prints what this emulator build documents for camera modes and what the booted guest reports. Read-only.
E=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/usr/local/lib/android/sdk}}/emulator/emulator
ls -la "$E" 2>&1 | head -2
for t in camera-front camera-back virtualscene-poster; do echo "=== -help-$t"; "$E" -help-$t 2>&1 | head -40; done
ls "$(dirname "$E")/resources" 2>&1 | head -30
echo "=== guest camera service"; adb shell dumpsys media.camera 2>&1 | head -60
adb shell pm list features | grep -i camera
