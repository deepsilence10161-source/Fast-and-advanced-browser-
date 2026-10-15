#!/bin/bash
# Chromium Android source build का एक "stage" — GitHub के मुफ़्त standard runner (4 CPU / 16 GB) पर।
#
# क्यों stages: पूरा Chromium build 4-core पर 6 घंटे की job-सीमा से लंबा है
# (docs.github.com/en/actions/reference/limits: "Job execution time 6 hours")।
# इसलिए हर stage समय-सीमा तक compile करता है, फिर पूरी build-state (src + out) को
# इसी repo के एक draft GitHub Release में रख देता है; अगला stage वहीं से आगे चलता है।
#
# हर stage एक जैसा है:
#   - state में src नहीं  -> fresh: source sync (tag पर, बिना history), deps, hooks, gn gen, src pack/upload
#   - state में src है    -> restore: src + पिछला out वापस (PAX tar, nanosecond mtime सुरक्षित)
#   - integrity watchdog: restore के बाद बचा काम (ninja -n) पिछले stage से ज़्यादा हो तो FAIL
#   - deadline तक ninja; फिर out pack/upload; build पूरा हो तो APK सत्यापित करके DONE
#
# Env (workflow से): TAG CPU STAGE DEADLINE(epoch) STATE(release tag) GH_TOKEN GITHUB_REPOSITORY
#                    OUTPUTS_DIR(APK/evidence के लिए) GITHUB_OUTPUT
set -euo pipefail
: "${TAG:?}" "${CPU:?}" "${STAGE:?}" "${DEADLINE:?}" "${STATE:?}" "${OUTPUTS_DIR:?}"
ROOT=/home/runner/cr                    # हर stage में एक ही absolute path (ninja/Java build configs के लिए)
OUTD=out/$CPU
PK=/home/runner/pk                      # pack/upload के लिए अस्थायी जगह
JOBS=${JOBS:-4}
log(){ echo "[$(date -u +%H:%M:%S)] $*"; }
out(){ echo "$1=$2" >> "${GITHUB_OUTPUT:-/dev/null}"; }
mkdir -p "$OUTPUTS_DIR" "$PK"
EVID="$OUTPUTS_DIR/stage-$STAGE.txt"; : > "$EVID"
ev(){ echo "$*" | tee -a "$EVID"; }

# ---------- 0. args.gn (इसी का hash state की पहचान का हिस्सा है) ----------
ARGS=$(cat <<EOF
target_os = "android"
target_cpu = "$CPU"
is_debug = false
is_official_build = false
is_component_build = false
symbol_level = 0
blink_symbol_level = 0
v8_symbol_level = 0
dcheck_always_on = false
use_siso = false
use_remoteexec = false
treat_warnings_as_errors = false
android_static_analysis = "off"
EOF
)

# ---------- 1. runner तैयार करना ----------
log "runner: $(nproc) CPU, $(free -g | awk '/Mem:/{print $2}') GB RAM"; df -h / /mnt 2>/dev/null | sed 's/^/  /'
log "free disk: बड़े, अनावश्यक preinstalled toolchains हटाना"
sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache \
  /usr/local/share/boost /usr/share/swift /usr/local/share/powershell /usr/local/julia* /opt/az \
  /usr/share/miniconda /usr/local/aws-cli /usr/local/share/chromium /opt/microsoft /opt/google \
  /usr/lib/jvm /usr/local/lib/node_modules 2>/dev/null || true
sudo docker system prune -af >/dev/null 2>&1 || true
sudo swapoff -a 2>/dev/null || true; sudo rm -f /mnt/swapfile /swapfile
sudo fallocate -l 16G /mnt/swap16 && sudo chmod 600 /mnt/swap16 && sudo mkswap -q /mnt/swap16 && sudo swapon /mnt/swap16
df -h / /mnt | sed 's/^/  /'; free -g | sed 's/^/  /'
ev "runner_cpu=$(nproc) ram_gb=$(free -g | awk '/Mem:/{print $2}') root_free=$(df -BG --output=avail / | tail -1 | tr -d ' ')"

mkdir -p "$ROOT"
[ -d "$ROOT/depot_tools" ] || git clone -q --depth 1 https://chromium.googlesource.com/chromium/tools/depot_tools.git "$ROOT/depot_tools"
export PATH="$ROOT/depot_tools:$PATH" DEPOT_TOOLS_UPDATE=0 DEPOT_TOOLS_METRICS=0 GCLIENT_SUPPRESS_GIT_VERSION_WARNING=1

R="$GITHUB_REPOSITORY"
assets(){ gh release view "$STATE" -R "$R" --json assets -q '.assets[].name' 2>/dev/null || true; }
fetch_asset(){ gh release download "$STATE" -R "$R" -p "$1" -O - ; }
upload(){ local i; for i in 1 2 3 4; do gh release upload "$STATE" -R "$R" --clobber "$@" && return 0; log "upload retry $i"; sleep $((i*15)); done; return 1; }

if ! gh release view "$STATE" -R "$R" >/dev/null 2>&1; then
  gh release create "$STATE" -R "$R" --draft --target "${GITHUB_SHA:-main}" -t "$STATE (build state, not a release)" \
    -n "Chromium $TAG $CPU staged-build state. Internal; deleted after the APK is verified." >/dev/null
  log "state release बनाया: $STATE"
fi
A=$(assets)
if grep -qx DONE <<<"$A"; then log "state DONE है — build पहले ही पूरा"; out done true; ev "status=already-done"; exit 0; fi

# ---------- 2. fresh या restore ----------
cd "$ROOT"
if ! grep -q '^src\.tar\.zst\.part' <<<"$A"; then
  MODE=fresh; log "MODE=fresh: Chromium $TAG source sync (बिना history)"
  t0=$(date +%s)
  mkdir -p src && git -C src init -q && git -C src remote add origin https://chromium.googlesource.com/chromium/src.git
  git -C src fetch -q --depth 1 origin "refs/tags/$TAG" && git -C src checkout -q FETCH_HEAD
  COMMIT=$(git -C src rev-parse HEAD); ev "tag=$TAG commit=$COMMIT"
  cat > .gclient <<EOF
solutions = [{"name": "src", "url": "https://chromium.googlesource.com/chromium/src.git", "managed": False,
  "custom_deps": {}, "custom_vars": {"checkout_pgo_profiles": False}}]
target_os = ["android"]
EOF
  gclient sync --nohooks --no-history -D -j 8 >"$PK/sync.log" 2>&1 || { tail -50 "$PK/sync.log"; exit 1; }
  ev "sync_seconds=$(( $(date +%s)-t0 ))"
  t1=$(date +%s)
  src/build/install-build-deps.sh --android --no-prompt --no-chromeos-fonts --no-arm >"$PK/deps.log" 2>&1 || { tail -40 "$PK/deps.log"; exit 1; }
  (cd src && gclient runhooks) >"$PK/hooks.log" 2>&1 || { tail -50 "$PK/hooks.log"; exit 1; }
  ev "deps_hooks_seconds=$(( $(date +%s)-t1 ))"
  mkdir -p "src/$OUTD"; printf '%s\n' "$ARGS" > "src/$OUTD/args.gn"
  (cd src && buildtools/linux64/gn gen "$OUTD") | tail -2
  echo "$COMMIT" > "$ROOT/COMMIT"
  du -sh src 2>/dev/null | sed 's/^/  src total: /'
  du -sh src/third_party src/chrome src/out 2>/dev/null | sed 's/^/  /'
  log "src pack + upload (out/ और .git बाहर; PAX = nanosecond mtime)"; t2=$(date +%s)
  tar --format=posix --exclude=./src/out --exclude-vcs -C "$ROOT" -cf - ./src ./.gclient ./COMMIT \
    | zstd -T0 -3 -q | split -b 1900m -d -a 3 - "$PK/src.tar.zst.part"
  (cd "$PK" && sha256sum src.tar.zst.part* > src.sha256)
  ev "src_pack_bytes=$(cat "$PK"/src.tar.zst.part* | wc -c)"
  for f in "$PK"/src.tar.zst.part*; do upload "$f"; rm -f "$f"; done; upload "$PK/src.sha256"
  ev "src_pack_upload_seconds=$(( $(date +%s)-t2 ))"
else
  MODE=restore; log "MODE=restore"
  t0=$(date +%s)
  fetch_asset src.sha256 > "$PK/src.sha256"
  for p in $(grep -o 'src\.tar\.zst\.part[0-9]*' "$PK/src.sha256"); do
    fetch_asset "$p" > "$PK/$p"; (cd "$PK" && grep " $p\$" src.sha256 | sha256sum -c --quiet) || { echo "checksum FAIL $p"; exit 1; }
    cat "$PK/$p"; rm -f "$PK/$p"
  done | zstd -dc -T0 | tar -x -C "$ROOT"
  COMMIT=$(cat "$ROOT/COMMIT"); ev "tag=$TAG commit=$COMMIT"
  src/build/install-build-deps.sh --android --no-prompt --no-chromeos-fonts --no-arm >"$PK/deps.log" 2>&1 || { tail -40 "$PK/deps.log"; exit 1; }
  if grep -q '^progress.json$' <<<"$A"; then
    fetch_asset progress.json > "$PK/progress.json"
    PREV=$(python3 -c "import json;print(json.load(open('$PK/progress.json'))['out_prefix'])")
    fetch_asset "$PREV.sha256" > "$PK/out.sha256"
    for p in $(grep -o "$PREV\.tar\.zst\.part[0-9]*" "$PK/out.sha256"); do
      fetch_asset "$p" > "$PK/$p"; (cd "$PK" && grep " $p\$" out.sha256 | sha256sum -c --quiet) || { echo "checksum FAIL $p"; exit 1; }
      cat "$PK/$p"; rm -f "$PK/$p"
    done | zstd -dc -T0 | tar -x -C "$ROOT/src"
  else
    mkdir -p "src/$OUTD"; printf '%s\n' "$ARGS" > "src/$OUTD/args.gn"; (cd src && buildtools/linux64/gn gen "$OUTD") | tail -2
  fi
  ev "restore_seconds=$(( $(date +%s)-t0 ))"
fi
# args अपरिवर्तित हों (state की पहचान)
diff <(printf '%s\n' "$ARGS") "src/$OUTD/args.gn" >/dev/null || { echo "args.gn बदल गया — state mismatch"; exit 1; }

NINJA=src/third_party/ninja/ninja; [ -x "$NINJA" ] || NINJA=ninja
remaining(){ "$NINJA" -C "src/$OUTD" -n chrome_public_apk 2>/dev/null | grep -o '^\[[0-9]*/[0-9]*\]' | tail -1 | tr -d '[]' | cut -d/ -f2; }
REM0=$(remaining); REM0=${REM0:-0}; ev "remaining_edges_at_start=$REM0"
if [ -f "$PK/progress.json" ]; then
  PREVREM=$(python3 -c "import json;print(json.load(open('$PK/progress.json'))['remaining_edges'])")
  ev "remaining_edges_prev_stage_end=$PREVREM"
  # watchdog: restore से पूरा हुआ काम दोबारा dirty हो गया तो रुकें (mtime/restore गड़बड़)
  if [ "$REM0" -gt $(( PREVREM + PREVREM/50 + 50 )) ]; then echo "WATCHDOG FAIL: restore के बाद काम बढ़ गया ($PREVREM -> $REM0)"; exit 1; fi
fi

# ---------- 3. deadline तक compile ----------
NOW=$(date +%s); BUDGET=$(( DEADLINE - NOW ))
log "compile: budget ${BUDGET}s, -j$JOBS, $REM0 edges बाकी"
RC=0
if [ "$BUDGET" -gt 300 ]; then
  ( while sleep 600; do free -g | awk '/Mem:/{printf "mem used %sG; ",$3} /Swap:/{printf "swap used %sG; ",$3}'; df -BG --output=avail / | tail -1 | sed 's/^/disk free /'; done ) &
  MON=$!
  set +e
  timeout -s INT -k 180 "$BUDGET" "$NINJA" -C "src/$OUTD" -j "$JOBS" chrome_public_apk > "$PK/ninja.log" 2>&1
  RC=$?; set -e; kill $MON 2>/dev/null || true
  grep -E '^\[[0-9]+/[0-9]+\]' "$PK/ninja.log" | tail -3; grep -E 'FAILED|error:' "$PK/ninja.log" | head -20 || true
else RC=124; fi
REM1=$(remaining); REM1=${REM1:-0}
ev "ninja_rc=$RC remaining_edges_at_end=$REM1"
tail -c 200000 "$PK/ninja.log" > "$OUTPUTS_DIR/ninja-tail-stage-$STAGE.log" 2>/dev/null || true

# ---------- 4. out state pack/upload ----------
PREFIX="out-s$STAGE"
if [ "$RC" -ne 0 ] || [ "$REM1" -ne 0 ]; then
  log "out pack + upload ($PREFIX)"; t3=$(date +%s)
  du -sh "src/$OUTD" | sed 's/^/  out: /'
  tar --format=posix -C "$ROOT/src" -cf - "$OUTD" | zstd -T0 -3 -q | split -b 1900m -d -a 3 - "$PK/$PREFIX.tar.zst.part"
  (cd "$PK" && sha256sum $PREFIX.tar.zst.part* > $PREFIX.sha256)
  ev "out_pack_bytes=$(cat "$PK"/$PREFIX.tar.zst.part* | wc -c)"
  for f in "$PK"/$PREFIX.tar.zst.part*; do upload "$f"; rm -f "$f"; done; upload "$PK/$PREFIX.sha256"
  python3 - "$PK/progress.json" <<EOF
import json,sys,time
json.dump({"tag":"$TAG","cpu":"$CPU","commit":"$COMMIT","stage":$STAGE,"out_prefix":"$PREFIX",
  "remaining_edges":$REM1,"ninja_rc":$RC,"time":int(time.time())},open(sys.argv[1],"w"))
EOF
  upload "$PK/progress.json"
  # पुराने out-s* assets हटाना
  for old in $(assets | grep -E '^out-s[0-9]+\.' | grep -v "^$PREFIX\." || true); do gh release delete-asset "$STATE" "$old" -R "$R" -y >/dev/null || true; done
  ev "out_pack_upload_seconds=$(( $(date +%s)-t3 ))"
fi
if [ "$RC" -ne 0 ] && [ "$RC" -ne 124 ]; then echo "BUILD ERROR (ninja rc=$RC) — state सुरक्षित, chain रुकी"; out done false; exit 1; fi
if [ "$REM1" -ne 0 ]; then log "समय समाप्त, $REM1 edges बाकी → अगला stage"; out done false; exit 0; fi

# ---------- 5. पूरा: APK सत्यापन ----------
APK="src/$OUTD/apks/ChromePublic.apk"; [ -f "$APK" ] || { echo "APK नहीं मिला"; exit 1; }
BT=$(ls -d src/third_party/android_sdk/public/build-tools/* | sort -V | tail -1)
export PATH="$ROOT/src/third_party/jdk/current/bin:$PATH"   # /usr/lib/jvm हटाया गया था; Chromium का अपना JDK
cp "$APK" "$OUTPUTS_DIR/ChromePublic-$TAG-$CPU.apk"
{
  echo "tag=$TAG"; echo "commit=$COMMIT"; echo "cpu=$CPU"; echo "built_on=github ubuntu-24.04 standard runner (staged)"
  echo "--- args.gn"; cat "src/$OUTD/args.gn"
  echo "--- sha256"; sha256sum "$APK" | cut -d' ' -f1
  echo "--- bytes"; stat -c %s "$APK"
  echo "--- clang"; cat src/third_party/llvm-build/Release+Asserts/cr_build_revision 2>/dev/null || true
  echo "--- apksigner verify"; "$BT/apksigner" verify --print-certs -v "$APK" 2>&1 | grep -vi warning | head -20
  echo "--- aapt2 badging"; "$BT/aapt2" dump badging "$APK" 2>/dev/null | grep -E "^(package|sdkVersion|targetSdkVersion|native-code|application-label):"
} > "$OUTPUTS_DIR/BUILD_INFO.txt"
cat "$OUTPUTS_DIR/BUILD_INFO.txt"
upload "$OUTPUTS_DIR/ChromePublic-$TAG-$CPU.apk" "$OUTPUTS_DIR/BUILD_INFO.txt"
echo done > "$PK/DONE"; upload "$PK/DONE"
out done true; ev "status=DONE"
