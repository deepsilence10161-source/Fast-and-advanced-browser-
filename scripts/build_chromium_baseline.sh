#!/bin/bash
# Full Chromium Android source build at the Chrome Stable commit — WITH a hard preflight guard.
# Official minimum (android_build_instructions.md): x86-64 Linux, >=8 GB RAM (16+ recommended), >=100 GB free disk.
# Never starts a large fetch on an undersized host. Exit 3 = preflight refused.
# Usage: build_chromium_baseline.sh [--preflight-only] [--commit <sha>] [--workdir <dir>]
set -euo pipefail
COMMIT=43a195105613ac83c21d3f14de279f4a045c7da0   # Chrome Stable 155.0.8059.80 (Chromium Dash, 2026-10-15)
WORK=${WORK:-$HOME/chromium}; PRE=0
while [ $# -gt 0 ]; do case "$1" in --preflight-only) PRE=1;; --commit) COMMIT=$2; shift;; --workdir) WORK=$2; shift;; esac; shift; done
mkdir -p "$WORK"
arch=$(uname -m); ram_gb=$(awk '/MemTotal/{printf "%d", $2/1024/1024}' /proc/meminfo)
disk_gb=$(df -BG --output=avail "$WORK" | tail -1 | tr -dc 0-9)
echo "preflight: arch=$arch ram=${ram_gb}GB free_disk=${disk_gb}GB (need x86_64, >=8GB RAM, >=100GB disk)"
ok=1
[ "$arch" = x86_64 ] || { echo "REFUSE: not x86_64"; ok=0; }
[ "$ram_gb" -ge 8 ] || { echo "REFUSE: RAM < 8GB"; ok=0; }
[ "$disk_gb" -ge 100 ] || { echo "REFUSE: free disk < 100GB"; ok=0; }
[ $ok = 1 ] || exit 3
[ $PRE = 1 ] && { echo "preflight OK"; exit 0; }
# --- below runs only on a qualified host (not yet executed in this project) ---
[ -d "$WORK/depot_tools" ] || git clone --depth 1 https://chromium.googlesource.com/chromium/tools/depot_tools.git "$WORK/depot_tools"
export PATH="$PATH:$WORK/depot_tools"; cd "$WORK"
[ -d src ] || fetch --nohooks --no-history android
cd src && git fetch --depth 1 origin "$COMMIT" && git checkout -q FETCH_HEAD
gclient sync -D --force --nohooks --no-history --revision "src@$COMMIT"
build/install-build-deps.sh --android --no-prompt
gclient runhooks
gn gen out/Release --args='target_os="android" target_cpu="arm64" is_debug=false is_official_build=false symbol_level=0 blink_symbol_level=0'
autoninja -C out/Release chrome_public_apk
ls -la out/Release/apks/
