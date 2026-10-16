#!/bin/bash
# UI journey के बाद device-स्तर की अतिरिक्त जाँचें (emulator और Redroid ARM64 दोनों पर)।
# Usage: device_checks.sh <target> <apk> [foreign-signed-apk]
#   foreign-signed-apk: वही APK पर किसी दूसरी (throwaway) key से signed — update protection का negative test
# Output: out/<target>/device_checks.txt (+ .json)। हर जाँच PASS/FAIL/SKIP; exit 0 (निर्णय summary में)।
set -u
T=$1; APK=$2; FOREIGN=${3:-}
OUT=out/$T; mkdir -p "$OUT"; R="$OUT/device_checks.txt"; : > "$R"
PKG=$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "$OUT/BUILD_INFO.txt" 2>/dev/null | head -1); PKG=${PKG:-org.chromium.chrome}
LABEL=$(sed -n "s/^application-label:'\(.*\)'$/\1/p" "$OUT/BUILD_INFO.txt" 2>/dev/null | head -1)
NONDEBUG=$(grep -q '^debuggable_apks = false' "$OUT/BUILD_INFO.txt" 2>/dev/null && echo 1 || echo 0)
P=0; F=0
res(){ echo "$1  $2${3:+ — $3}" | tee -a "$R"; case "$1" in PASS) P=$((P+1));; FAIL) F=$((F+1));; esac; }
sh(){ timeout "${2:-30}" adb shell "$1" 2>&1 | tr -d '\r'; }
echo "target=$T package=$PKG expected_label=${LABEL:-?} expect_nondebuggable=$NONDEBUG abi=$(sh 'getprop ro.product.cpu.abi') android=$(sh 'getprop ro.build.version.release')" | tee -a "$R"

# 1 package installed + launcher activity
sh "pm list packages $PKG" | grep -qx "package:$PKG" && res PASS "01 package installed ($PKG)" || res FAIL "01 package missing"
LA=$(sh "cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER $PKG" | tail -1)
[[ "$LA" == "$PKG/"* ]] && res PASS "02 launcher entry" "$LA" || res FAIL "02 launcher entry" "$LA"

# 3 label: launcher यही दिखाता है (aapt2 badging का application-label; system इसी resource से पढ़ता है)
# असली launcher: HOME -> app drawer (swipe up) -> uiautomator में label वाला icon; screenshot सबूत
if [ -n "$LABEL" ]; then
  FOUND=0
  for attempt in 1 2 3; do
    sh "input keyevent KEYCODE_HOME" >/dev/null; sleep 2
    sh "input swipe 540 2000 540 400 300" >/dev/null; sleep 3
    sh "uiautomator dump /sdcard/launcher.xml" 40 >/dev/null; timeout 20 adb pull /sdcard/launcher.xml "$OUT/launcher_drawer.xml" >/dev/null 2>&1
    if grep -qE "(text|content-desc)=\"$LABEL\"" "$OUT/launcher_drawer.xml" 2>/dev/null; then FOUND=1; break; fi
  done
  timeout 20 adb exec-out screencap -p > "$OUT/launcher_drawer.png" 2>/dev/null
  HOMEPKG=$(grep -o 'package="[^"]*"' "$OUT/launcher_drawer.xml" 2>/dev/null | sort | uniq -c | sort -rn | head -1 | grep -o '"[^"]*"')
  [ $FOUND = 1 ] && res PASS "03 launcher app drawer में \"$LABEL\"" "launcher=$HOMEPKG, screenshot launcher_drawer.png" \
                 || res FAIL "03 launcher app drawer में \"$LABEL\" नहीं मिला" "launcher=${HOMEPKG:-?}"
else res SKIP "03 label" "BUILD_INFO में label नहीं"; fi

# 4 non-debuggable: run-as must fail; package flags must not contain DEBUGGABLE
FL=$(sh "dumpsys package $PKG" 60 | grep -m1 -E "^\s+flags=\[" | tr -s ' ')
RA=$(sh "run-as $PKG id")
if [ "$NONDEBUG" = 1 ]; then
  if ! grep -q DEBUGGABLE <<<"$FL" && grep -qiE "not debuggable|unknown package|run-as:" <<<"$RA" && ! grep -q "uid=" <<<"$RA"; then
    res PASS "04 non-debuggable" "flags:${FL# } | run-as: $RA"
  else res FAIL "04 non-debuggable" "flags:${FL# } | run-as: $RA"; fi
else
  res SKIP "04 non-debuggable" "build debuggable है (baseline)"
fi

# install output पूरा log में (केवल आखिरी line पर भरोसा नहीं — x64 run 38904972738 में खाली मिली थी)
IL="$OUT/device_checks_install.log"; : > "$IL"
inst(){ local tag=$1; shift; local t0=$SECONDS o rc
  o=$(timeout 300 adb install "$@" 2>&1); rc=$?
  printf '=== %s: adb install %s (rc=%s, %ss)\n%s\n' "$tag" "$*" "$rc" "$((SECONDS-t0))" "$o" | tr -d '\r' >> "$IL"
  printf '%s' "$o" | tr -d '\r' | grep -v '^[[:space:]]*$' | tail -1; }
sig(){ sh "dumpsys package $PKG" 60 | grep -m1 -oE 'signatures:\[[^]]*\]'; }

# 5 update with the same key (in-place upgrade keeps data)
sh "am force-stop $PKG"
U=$(inst 05 -r "$APK")
[ "$U" = Success ] && res PASS "05 same-key update (install -r)" || res FAIL "05 same-key update" "$U"

# 6 update with a different key must be rejected (protects users from fake updates)
if [ -n "$FOREIGN" ] && [ -f "$FOREIGN" ]; then
  S0=$(sig); U=$(inst 06 -r "$FOREIGN"); S1=$(sig)
  FULL=$(sed -n '/^=== 06:/,$p' "$IL")
  if grep -q "INSTALL_FAILED_UPDATE_INCOMPATIBLE" <<<"$FULL" && [ -n "$S0" ] && [ "$S0" = "$S1" ]; then
    res PASS "06 foreign-key update rejected" "INSTALL_FAILED_UPDATE_INCOMPATIBLE; installed signer unchanged $S1"
  else
    res FAIL "06 foreign-key update NOT rejected" "last='$U' signer_before='$S0' after='$S1' (पूरा: device_checks_install.log)"
  fi
else res SKIP "06 foreign-key update" "foreign APK नहीं दिया"; fi

# 7 real touch-scroll frame pacing on a web page (CDP rAF; gfxinfo/HWUI web content के frames नहीं गिनता)
sh "am start -a android.intent.action.VIEW -d https://example.org $PKG" >/dev/null; sleep 6
DS=""; for i in 1 2 3 4 5 6; do DS=$(sh "cat /proc/net/unix" | grep -o '@chrome_devtools_remote[A-Za-z0-9_]*' | head -1 | tr -d '@'); [ -n "$DS" ] && break; sleep 3; done
timeout 20 adb forward tcp:9222 "localabstract:${DS:-chrome_devtools_remote}" >/dev/null 2>&1
SJ=$(timeout 150 ${DC_SCROLL_CMD:-python3 scripts/ci/scroll_jank.py} --out "$OUT/scroll_jank" 2>&1 | tail -1)   # DC_SCROLL_CMD: केवल unit test
case "$SJ" in OK*) res PASS "07 touch scroll measured (software GPU, संख्या प्रतिनिधि नहीं)" "${SJ#OK }";; *) res FAIL "07 touch scroll" "${SJ:-no output}";; esac
timeout 15 adb exec-out screencap -p > "$OUT/scroll_after.png" 2>/dev/null

# 8 process alive, no crash during checks
PID=$(sh "pidof $PKG"); CR=$(timeout 30 adb logcat -d -b crash 2>/dev/null | grep -c "$PKG" || true)
[ -n "$PID" ] && [ "${CR:-0}" = 0 ] && res PASS "08 alive, crash buffer clean" "pid=$PID" || res FAIL "08 crash/dead" "pid=${PID:-none} crash_lines=$CR"

# 9 uninstall + clean reinstall
U1=$(timeout 120 adb uninstall "$PKG" 2>&1 | tr -d '\r' | tail -1); U2=$(inst 09 "$APK")
[ "$U1" = Success ] && [ "$U2" = Success ] && res PASS "09 uninstall + reinstall" || res FAIL "09 uninstall/reinstall" "$U1 / $U2"

echo "DEVICE_CHECKS: $P पास, $F विफल" | tee -a "$R"
python3 - "$R" "$OUT/device_checks.json" <<'EOF'
import json,sys
rows=[l.rstrip('\n') for l in open(sys.argv[1]) if l[:4] in ('PASS','FAIL','SKIP')]
json.dump([{"status":l.split()[0],"check":l[6:]} for l in rows],open(sys.argv[2],'w'),ensure_ascii=False,indent=1)
EOF
exit 0
