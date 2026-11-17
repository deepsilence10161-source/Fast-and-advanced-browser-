#!/bin/bash
# Usage: face_guard_e2e_run.sh <target> <apk>
# Installs the DEVELOPMENT personal APK (Face Guard suite) on the CURRENT adb device and runs scripts/ci/face_guard_e2e.py.
# Never publishes anything. Result files: out/<target>/face_guard_e2e*.{txt,json}
set -u
T=$1; APK=$2; OUT=out/$T; mkdir -p "$OUT"; L="$OUT/face_guard_e2e.txt"; : > "$L"
timeout 180 adb wait-for-device
PKG=$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "$OUT/BUILD_INFO.txt" | head -1)
[ -n "$PKG" ] || { echo "FACE_GUARD_E2E NOT_RUN no package in BUILD_INFO" | tee -a "$L"; exit 2; }
case "$PKG" in com.swiftra.app|org.chromium.*|com.android.*|com.google.*) echo "FACE_GUARD_E2E REFUSED ordinary package $PKG" | tee -a "$L"; exit 2;; esac
timeout 30 adb logcat -G 16M >/dev/null 2>&1; timeout 30 adb logcat -c
echo "target=$T package=$PKG abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r') apk_sha256=$(sha256sum "$APK" | cut -d' ' -f1)" | tee -a "$L"
IN=$(timeout 300 adb install -r "$APK" 2>&1 | tr -d '\r' | tail -1); echo "install: $IN" | tee -a "$L"
[ "$IN" = Success ] || { echo "FACE_GUARD_E2E FAIL install ($IN)" | tee -a "$L"; exit 1; }
FL=$(adb shell dumpsys package "$PKG" | grep -m1 -E "^\s+flags=\[" | tr -s ' ')
if grep -q DEBUGGABLE <<<"$FL"; then echo "FACE_GUARD_E2E FAIL debuggable build" | tee -a "$L"; exit 1; fi
echo "package flags:$FL" | tee -a "$L"
timeout 1500 python3 -u scripts/ci/face_guard_e2e.py --package "$PKG" --out "$OUT/face_guard_e2e" 2>&1 | tee -a "$L"
exit "${PIPESTATUS[0]}"
