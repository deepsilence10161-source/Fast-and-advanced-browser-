#!/bin/bash
# Usage: chrome_reference_run.sh <helper.apk>
# Measures the stock Google Chrome that ships on the emulator image with the SAME scripts used on the personal build.
# Report only (never gates). The Chrome version is whatever the image carries and is recorded below.
set -u
HELP=$1; PKG=com.android.chrome; OUT=out/chrome_ref_x64; mkdir -p "$OUT"; L="$OUT/chrome_ref.txt"; : > "$L"
timeout 180 adb wait-for-device
adb root >/dev/null 2>&1; sleep 3; adb wait-for-device
echo "CHROME_REF package=$PKG present=$(adb shell pm list packages "$PKG" | tr -d '\r')" | tee -a "$L"
echo "CHROME_REF version=$(adb shell dumpsys package "$PKG" | grep -m1 versionName | tr -d '\r ') sdk=$(adb shell getprop ro.build.version.sdk | tr -d '\r') image=$(adb shell getprop ro.build.fingerprint | tr -d '\r')" | tee -a "$L"
IN=$(timeout 300 adb install -r "$HELP" 2>&1 | tr -d '\r' | tail -1); echo "install helper: $IN" | tee -a "$L"
mkdir -p "$OUT/egress" "$OUT/forensics" "$OUT/clip" "$OUT/af" "$OUT/cred"
timeout 900 python3 -u scripts/ci/personal_egress_audit.py --package "$PKG" --out "$OUT/egress" 2>&1 | tee -a "$L"
timeout 1200 python3 -u scripts/ci/personal_forensics_e2e.py --package "$PKG" --out "$OUT/forensics" 2>&1 | tee -a "$L"
timeout 1200 python3 -u scripts/ci/personal_clipboard_e2e.py --package "$PKG" --out "$OUT/clip" 2>&1 | tee -a "$L"
timeout 900 python3 -u scripts/ci/personal_autofill_e2e.py --package "$PKG" --out "$OUT/af" 2>&1 | tee -a "$L"
timeout 900 python3 -u scripts/ci/personal_cred_e2e.py --package "$PKG" --out "$OUT/cred" 2>&1 | tee -a "$L"
exit 0
