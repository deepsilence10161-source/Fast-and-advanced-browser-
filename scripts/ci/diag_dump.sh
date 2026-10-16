#!/bin/bash
# Process death/crash diagnosis (emulator और Redroid दोनों): launch probe + ApplicationExitInfo + पूरा logcat + tombstones।
# क्यों: Redroid run 38907136262 में "app died, no saved state" पर crash buffer खाली था और filtered logcat_tail
# में कारण नहीं था। Android का ApplicationExitInfo (dumpsys activity exit-info) हर मौत का कारण बताता है
# (CRASH_NATIVE / SIGNALED / LOW_MEMORY / ANR / INITIALIZATION_FAILURE ...)।
# Usage: diag_dump.sh <target> [package]     Output: out/<T>/diag/*      exit 0 हमेशा।
set -u
T=$1; OUT=out/$T/diag; mkdir -p "$OUT"
PKG=${2:-$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "out/$T/BUILD_INFO.txt" 2>/dev/null | head -1)}; PKG=${PKG:-org.chromium.chrome}
a(){ timeout "${2:-30}" adb shell "$1" 2>&1 | tr -d '\r'; }

# 1) launch probe: साफ़ शुरुआत से 25 s तक हर सेकंड process ज़िंदा है या नहीं + foreground activity
{
  echo "package=$PKG"
  a "am force-stop $PKG"; timeout 10 adb logcat -c 2>/dev/null
  echo "--- am start -W"; a "am start -W -a android.intent.action.VIEW -d https://example.org $PKG" 60
  for s in $(seq 1 25); do
    P=$(a "pidof $PKG"); FG=$(a "dumpsys activity activities" | grep -m1 -E "mResumedActivity|topResumedActivity" | grep -oE "[a-z0-9_.]+/[A-Za-z0-9_.$]+" | head -1)
    echo "t=${s}s pid=${P:-DEAD} fg=${FG:-?}"; sleep 1
  done
} > "$OUT/launch_probe.txt" 2>&1
timeout 60 adb logcat -d -b all > "$OUT/logcat_probe_all.txt" 2>/dev/null

# 2) हर दर्ज मौत का कारण (सबसे ज़रूरी)
a "dumpsys activity exit-info $PKG" 60 > "$OUT/exit_info.txt"

# 3) tombstones (Redroid userdebug: adbd root हो सकता है), ANR traces, crash/system buffers
{ a "ls -l /data/tombstones" ; } > "$OUT/tombstones_ls.txt"
for f in $(a "ls /data/tombstones" | grep -E '^tombstone_[0-9]+$' | tail -3); do a "cat /data/tombstones/$f" 30 | head -400 > "$OUT/$f.txt"; done
a "ls -l /data/anr" > "$OUT/anr_ls.txt"
timeout 30 adb logcat -d -b crash > "$OUT/logcat_crash.txt" 2>/dev/null
timeout 60 adb logcat -d -b main,system,events > "$OUT/logcat_full.txt" 2>/dev/null
a "dumpsys meminfo $PKG" 60 > "$OUT/meminfo.txt"
a "dmesg" 30 | tail -200 > "$OUT/dmesg_tail.txt"
a "getprop" > "$OUT/getprop.txt"

# 4) सारांश (मानव-पठनीय)
{
  echo "== launch probe (आखिरी 5)"; tail -5 "$OUT/launch_probe.txt"
  echo "== exit reasons (ApplicationExitInfo)"; grep -E "reason=|description=|status=|importance=" "$OUT/exit_info.txt" | head -24
  echo "== fatal markers"; grep -hE "Fatal signal|FATAL EXCEPTION|Abort message|Cmdline:|signal [0-9]+ \(|backtrace:|lowmemorykiller|Killing [0-9]+:$PKG|has died|crashed|SIGSEGV|SIGABRT|SIGILL|SIGTRAP" \
      "$OUT"/logcat_probe_all.txt "$OUT"/tombstone_*.txt 2>/dev/null | cut -c1-260 | head -40
} > "$OUT/SUMMARY.txt" 2>&1
cat "$OUT/SUMMARY.txt"
exit 0
