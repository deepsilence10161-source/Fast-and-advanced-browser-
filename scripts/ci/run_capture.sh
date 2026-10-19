#!/bin/bash
# emulator-runner के अंदर एक line में चलाने हेतु wrapper
set -u
T=$1; OUT=out/$T; mkdir -p "$OUT"; timeout 120 adb wait-for-device; timeout 20 adb logcat -G 16M >/dev/null 2>&1; timeout 30 adb logcat -c
# source build (branding patch के बाद package बदल सकता है): package BUILD_INFO के aapt2 badging से
ART_PKG=$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "$OUT/BUILD_INFO.txt" 2>/dev/null | head -1); ART_PKG=${ART_PKG:-org.chromium.chrome}
# A baseline/older APK without the feature must be NOT_RUN, not a false browser FAIL.
safety_update_supported() {
  grep -Eq '^[[:space:]]*0005-safety-hub-no-false-up-to-date[.]patch[[:space:]]*$' "$OUT/BUILD_INFO.txt" 2>/dev/null &&
    grep -Eq '^[[:space:]]*0020-swiftra-update-channel[.]patch[[:space:]]*$' "$OUT/BUILD_INFO.txt" 2>/dev/null
}
# The legacy keystore script exits 0 for NOT_RUN too; a focused postcondition must check evidence.
keystore_probe_passed() {
  [ "$1" -eq 0 ] && grep -Eq '^KEYSTORE_E2E PASS prefix=sw1 plain_value=False token_in_db=False wrapped_pref=True cookie_after_restart=True keystore2=True([[:space:]]|$)' "$2"
}
# Focused acceptance on the same already-built APK. Not a replacement for full release E2E:
# workflows explicitly skip publish in this mode; e2e_gate also rejects its missing full-suite markers.
if [ "${2:-full}" = safety_update ]; then
  safety_update_supported || { echo 'SAFETY_UPDATE_E2E NOT_RUN build lacks 0005+0020'; exit 2; }
  APK_FILE=$(find dl -name ChromePublic.apk 2>/dev/null | head -1)
  [ -n "$APK_FILE" ] || { echo 'SAFETY_UPDATE_E2E NOT_RUN no source APK'; exit 2; }
  timeout 900 python3 -u scripts/ci/safety_update_e2e.py --package "$ART_PKG" --apk "$APK_FILE" --out "$OUT/safety_update" 2>&1 | tee "$OUT/safety_update_e2e.txt"
  rc=${PIPESTATUS[0]}; echo "safety_update_e2e exit=$rc" | tee -a "$OUT/journey.log"
  # On 0021 builds, prove the provider still encrypts/decrypts after the private-pref fixture cycle.
  if [ "$rc" -eq 0 ] && grep -Eq '^[[:space:]]*0021-swiftra-keystore-oscrypt[.]patch[[:space:]]*$' "$OUT/BUILD_INFO.txt"; then
    timeout 240 python3 -u scripts/ci/keystore_e2e.py --package "$ART_PKG" --out "$OUT/keystore" 2>&1 | tee "$OUT/keystore_e2e.txt"
    kr=${PIPESTATUS[0]}; echo "keystore_e2e exit=$kr" | tee -a "$OUT/journey.log"
    keystore_probe_passed "$kr" "$OUT/keystore_e2e.txt" || rc=1
  fi
  exit "$rc"
fi
case "$T" in
  chrome_ref) timeout 2400 python3 scripts/ui_capture.py --package com.android.chrome --label "$T" --out "$OUT" ;;
  chromium_*) timeout 2400 python3 scripts/ui_capture.py --package "$ART_PKG" --label "$T" --out "$OUT" --apk "$(find dl -name ChromePublic.apk | head -1)" ;;
esac
echo "ui_capture exit=$?" | tee -a "$OUT/journey.log"
# static security + branding audit of the tested APK (tools/security/apk_audit.py; no device needed)
APK_FILE=$(find dl -name ChromePublic.apk 2>/dev/null | head -1)
if [ -n "$APK_FILE" ]; then
  timeout 600 python3 tools/security/apk_audit.py --apk "$APK_FILE" --json "$OUT/apk_audit.json" 2>&1 | grep -v "^WARNING\|DEBUG" | tee "$OUT/apk_audit.txt"
  echo "apk_audit exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
fi
# synthetic long-chat fixture in the SAME browser on the emulator (not real Arena)
PKG=$([ "$T" = chrome_ref ] && echo com.android.chrome || echo "$ART_PKG")
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
# सही platform label: Redroid (container, native arm64) बनाम emulator
case "$(timeout 15 adb shell getprop ro.hardware | tr -d '\r')" in redroid) PLAT=android-redroid-container;; ranchu|goldfish) PLAT=android-emulator;; *) PLAT=android-device;; esac
timeout 20 adb forward tcp:9222 "localabstract:${SOCK:-chrome_devtools_remote}"
timeout 200 python3 scripts/ci/run_chat_fixture.py --platform "$PLAT:$T" --out "$OUT/chat_fixture" --timeout 180 2>&1 | tee "$OUT/chat_fixture.txt"
echo "chat_fixture exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
kill $HTTP_PID 2>/dev/null
# Swiftra Shield (patches/0006): local canaries + Google's harmless test pages -> interstitial
if [ "$T" != chrome_ref ]; then
  timeout 1500 python3 scripts/ci/shield_e2e.py --package "$PKG" --out "$OUT/shield" 2>&1 | tee "$OUT/shield_e2e.txt"
  echo "shield_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # c2d: browser-initiated traffic from a cold start (NetLog from process start; last step: may use adb root)
  timeout 300 python3 scripts/ci/startup_netlog.py --package "$PKG" --out "$OUT/startup" 2>&1 | tee "$OUT/startup_netlog.txt"
  echo "startup_netlog exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # patches/0010: HTTPS-First (balanced) + third-party cookies blocked, checked by behaviour (local mapped hosts)
  timeout 240 python3 scripts/ci/advanced_e2e.py --package "$PKG" --out "$OUT/advanced" 2>&1 | tee "$OUT/advanced_e2e.txt"
  echo "advanced_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # patches/0020: signed update channel -> upstream "Update Swiftra" menu item/badge (signed vs tampered manifest)
  timeout 300 python3 scripts/ci/update_e2e.py --package "$PKG" --out "$OUT/update" 2>&1 | tee "$OUT/update_e2e.txt"
  echo "update_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # 0005 v2 + 0020: native Safety check, actual production signature check + rejected/stale/future fixtures.
  # Only update prefs are temporarily changed; the wrapped OSCrypt key and unrelated prefs are preserved.
  if safety_update_supported; then
    timeout 600 python3 -u scripts/ci/safety_update_e2e.py --package "$PKG" --out "$OUT/safety_update" 2>&1 | tee "$OUT/safety_update_e2e.txt"
    echo "safety_update_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  else
    echo 'SAFETY_UPDATE_E2E NOT_RUN build lacks 0005+0020' | tee "$OUT/safety_update_e2e.txt"
  fi
  # Speed (0016 Speed Pack + 0012 ad blocker): same APK, chromium_defaults vs swiftra, alternated; local mapped hosts
  timeout 1500 python3 -u scripts/ci/speed_e2e.py --package "$PKG" --out "$OUT/speed" --socket "${SOCK:-chrome_devtools_remote}" 2>&1 | tee "$OUT/speed_e2e.txt"
  echo "speed_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  timeout 90 adb logcat -b all -d 2>/dev/null | gzip -6 > "$OUT/logcat_speed_e2e.txt.gz"   # kept before any later logcat -c
  # repeat visits (SPA with cached assets; cold restart + warm): chromium_defaults / swiftra / swiftra_lcpp candidate
  # 4 cycles: with 2 the 6-vs-6 medians swung +-15% between runs (39202833756 vs 39218924046), too noisy to decide
  timeout 1700 python3 -u scripts/ci/repeat_e2e.py --cycles 4 --package "$PKG" --out "$OUT/repeat" --socket "${SOCK:-chrome_devtools_remote}" 2>&1 | tee "$OUT/repeat_e2e.txt"
  echo "repeat_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  timeout 90 adb logcat -b all -d 2>/dev/null | gzip -6 > "$OUT/logcat_repeat_e2e.txt.gz"   # kept before any later logcat -c
  # cold-start trace (diagnostic for startup speed work; never fails the job)
  timeout 240 python3 scripts/ci/startup_trace.py --package "$PKG" --out "$OUT/startup_trace" 2>&1 | tee "$OUT/startup_trace.txt"
  echo "startup_trace exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # ART compile state vs cold start (install/verify vs speed-profile vs speed): is a baseline profile worth it?
  timeout 1200 python3 scripts/ci/art_startup.py --package "$PKG" --out "$OUT/art_startup" 2>&1 | tee "$OUT/art_startup.txt"
  echo "art_startup exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
  # patches/0021: cookies encrypted with the Keystore-protected key ("sw1"), readable after restart (last: root reads may restart adbd)
  timeout 240 python3 scripts/ci/keystore_e2e.py --package "$PKG" --out "$OUT/keystore" 2>&1 | tee "$OUT/keystore_e2e.txt"
  echo "keystore_e2e exit=${PIPESTATUS[0]}" | tee -a "$OUT/journey.log"
fi
timeout 60 adb logcat -d | grep -iE "chromium|chrome|FATAL|AndroidRuntime|ndk_translation|DEBUG" | tail -400 > "$OUT/logcat_tail.txt"
exit 0
