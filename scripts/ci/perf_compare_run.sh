#!/bin/bash
# Usage: perf_compare_run.sh <personal.apk> <personal_package>
set -u
APK=$1; PKG=$2; OUT=out/perf; mkdir -p "$OUT"
timeout 180 adb wait-for-device
echo "install: $(timeout 300 adb install -r "$APK" 2>&1 | tr -d '\r' | tail -1)"
for round in 1 2; do
  timeout 1500 python3 -u scripts/ci/perf_compare.py --packages com.android.chrome "$PKG" --runs 7 --out "$OUT/round$round.json" 2>&1 | tee -a "$OUT/perf.txt"
  timeout 1500 python3 -u scripts/ci/perf_compare.py --packages "$PKG" com.android.chrome --runs 7 --out "$OUT/round${round}_rev.json" 2>&1 | tee -a "$OUT/perf.txt"
done
exit 0
