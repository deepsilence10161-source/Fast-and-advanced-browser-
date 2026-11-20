#!/bin/bash
# Usage: personal_egress_run.sh <target> <apk>   (development personal APK on the CURRENT adb device; measures only)
set -u
T=$1; APK=$2; OUT=out/$T; mkdir -p "$OUT"; L="$OUT/personal_egress.txt"; : > "$L"
timeout 180 adb wait-for-device
PKG=$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "$OUT/BUILD_INFO.txt" | head -1)
case "$PKG" in ""|com.swiftra.app|org.chromium.*|com.android.*|com.google.*) echo "PERSONAL_EGRESS REFUSED package '$PKG'" | tee -a "$L"; exit 2;; esac
echo "target=$T package=$PKG apk_sha256=$(sha256sum "$APK" | cut -d' ' -f1)" | tee -a "$L"
IN=$(timeout 300 adb install -r "$APK" 2>&1 | tr -d '\r' | tail -1); echo "install: $IN" | tee -a "$L"
[ "$IN" = Success ] || { echo "PERSONAL_EGRESS FAIL install" | tee -a "$L"; exit 1; }
adb root >/dev/null 2>&1; sleep 3; adb wait-for-device
timeout 900 python3 -u scripts/ci/personal_egress_audit.py --package "$PKG" --out "$OUT" 2>&1 | tee -a "$L"
exit "${PIPESTATUS[0]}"
