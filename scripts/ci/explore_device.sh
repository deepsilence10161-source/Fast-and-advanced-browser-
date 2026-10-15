#!/bin/bash
# Exploratory device probe: Chrome version on the image, ARM64 translation, snapshot install/launch.
set -u; OUT=${OUT:-out}; mkdir -p "$OUT"
P(){ echo "### $*" | tee -a "$OUT/probe.txt"; }
adb wait-for-device
P "device"; { adb shell getprop ro.build.version.release; adb shell getprop ro.build.version.sdk; adb shell getprop ro.product.cpu.abilist; adb shell getprop ro.dalvik.vm.native.bridge; adb shell wm size; adb shell wm density; } | tee -a "$OUT/probe.txt"
P "chrome on image"; adb shell dumpsys package com.android.chrome | grep -E "versionName|versionCode|codePath" | head -5 | tee -a "$OUT/probe.txt"
P "webview"; adb shell dumpsys webviewupdate | grep -iE "Current WebView package|version" | head -3 | tee -a "$OUT/probe.txt"
for d in dl/arm64 dl/desktop_x64; do
  [ -d "$d" ] || continue
  for apk in $(find "$d" -name '*.apk' | sort); do
    P "aapt badging $apk"; "$ANDROID_HOME"/build-tools/*/aapt2 dump badging "$apk" 2>/dev/null | grep -E "^package:|native-code|sdkVersion|launchable-activity" | head -5 | tee -a "$OUT/probe.txt"
  done
done
try_app(){ # $1=label $2=apk
  local label=$1 apk=$2
  P "install $label"; timeout 300 adb install -r -g "$apk" 2>&1 | tail -2 | tee -a "$OUT/probe.txt"
  local pkg; pkg=$("$ANDROID_HOME"/build-tools/*/aapt2 dump badging "$apk" 2>/dev/null | sed -n "s/^package: name='\([^']*\)'.*/\1/p" | head -1)
  P "launch $label ($pkg)"; adb logcat -c
  adb shell monkey -p "$pkg" -c android.intent.category.LAUNCHER 1 2>&1 | tail -1 | tee -a "$OUT/probe.txt"
  sleep 25
  adb shell pidof "$pkg" | tee -a "$OUT/probe.txt" || echo "NOT RUNNING" | tee -a "$OUT/probe.txt"
  adb exec-out screencap -p > "$OUT/$label.png"
  adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1 && adb pull /sdcard/ui.xml "$OUT/$label.xml" >/dev/null 2>&1
  adb logcat -d -b crash > "$OUT/$label.crash.txt" 2>&1; P "crash buffer lines: $(wc -l < "$OUT/$label.crash.txt")"
  adb logcat -d | grep -iE "FATAL|native_bridge|ndk_translation|libc.*Fatal" | head -20 > "$OUT/$label.logcat-grep.txt"
  adb shell am force-stop "$pkg"
}
# Chrome on image (reference)
adb logcat -c; adb shell monkey -p com.android.chrome -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 15
adb exec-out screencap -p > "$OUT/chrome_image.png"; adb shell am force-stop com.android.chrome
A=$(find dl/arm64 -name 'ChromePublic.apk' | head -1); [ -n "$A" ] && try_app chromium_arm64 "$A"
D=$(find dl/desktop_x64 -name '*.apk' | grep -i -E 'chrome' | head -1); [ -n "$D" ] && try_app chromium_desktop_x64 "$D"
ls -la "$OUT"
