#!/bin/bash
# Usage: personal_clipboard_run.sh <target> <personal.apk> <helper.apk>
set -u
T=$1; APK=$2; HELP=$3; OUT=out/$T; mkdir -p "$OUT"; L="$OUT/personal_clip.txt"; : > "$L"
timeout 180 adb wait-for-device
PKG=$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "$OUT/BUILD_INFO.txt" | head -1)
[ -n "$PKG" ] || { echo "PERSONAL_RUN NOT_RUN no package in BUILD_INFO" | tee -a "$L"; exit 2; }
case "$PKG" in com.swiftra.app|org.chromium.*|com.android.*|com.google.*) echo "PERSONAL_RUN REFUSED ordinary package $PKG" | tee -a "$L"; exit 2;; esac
echo "target=$T package=$PKG apk_sha256=$(sha256sum "$APK" | cut -d' ' -f1) helper_sha256=$(sha256sum "$HELP" | cut -d' ' -f1)" | tee -a "$L"
for f in "$APK" "$HELP"; do IN=$(timeout 300 adb install -r "$f" 2>&1 | tr -d '\r' | tail -1); echo "install $(basename "$f"): $IN" | tee -a "$L"; [ "$IN" = Success ] || exit 1; done
pip install -q websocket-client >/dev/null 2>&1 || true
timeout 1200 python3 -u scripts/ci/${E2E_SCRIPT:-personal_clipboard_e2e.py} --package "$PKG" --out "$OUT/clip" 2>&1 | tee -a "$L"
exit "${PIPESTATUS[0]}"
