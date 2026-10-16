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
#                    SEED_STATE (वैकल्पिक): नई variant state खाली हो तो pristine src और शुरुआती out
#                    इसी (जैसे baseline) state से — patched build केवल बदले हिस्से compile करता है।
# इस परियोजना के source बदलाव: patches/series + patches/*.patch + patches/args.gn (scripts/ci/patches.py)।
set -euo pipefail
: "${TAG:?}" "${CPU:?}" "${STAGE:?}" "${DEADLINE:?}" "${STATE:?}" "${OUTPUTS_DIR:?}"
ROOT=${CR_ROOT:-/home/runner/cr}        # हर stage में एक ही absolute path (ninja/Java build configs के लिए)
OUTD=out/$CPU
PK=${CR_PK:-/home/runner/pk}            # pack/upload के लिए अस्थायी जगह
JOBS=${JOBS:-4}
log(){ echo "[$(date -u +%H:%M:%S)] $*"; }
out(){ echo "$1=$2" >> "${GITHUB_OUTPUT:-/dev/null}"; }
mkdir -p "$OUTPUTS_DIR" "$PK"
EVID="$OUTPUTS_DIR/stage-$STAGE.txt"; : > "$EVID"
ev(){ echo "$*" | tee -a "$EVID"; }

CI_DIR=$(cd "$(dirname "$(readlink -f "$0")")" && pwd); REPO_DIR=$(cd "$CI_DIR/../.." && pwd)
PDIR="$REPO_DIR/patches"
# ---------- 0. args.gn (base + patches/args.gn) ----------
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
EXTRA=$(python3 "$CI_DIR/patches.py" args "$PDIR")
if [ -n "$EXTRA" ]; then ARGS=$(printf '%s\n%s' "$ARGS" "$EXTRA"); fi
PATCH_HASH=$(python3 "$CI_DIR/patches.py" hash "$PDIR")
BUILD_KEY=$(printf '%s\n%s\n' "$PATCH_HASH" "$ARGS" | sha256sum | cut -c1-16)   # DONE इसी key का
EXP_PKG=$(sed -n 's/^ *chrome_public_manifest_package *= *"\([^"]*\)".*/\1/p' <<<"$ARGS" | tail -1)
EXP_PKG=${EXP_PKG:-org.chromium.chrome}

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
assets_of(){ gh release view "$1" -R "$R" --json assets -q '.assets[].name' 2>/dev/null || true; }
assets(){ assets_of "$STATE"; }
fetch_from(){ gh release download "$1" -R "$R" -p "$2" -O - ; }
fetch_asset(){ fetch_from "$STATE" "$1"; }
upload(){ local i; for i in 1 2 3 4; do gh release upload "$STATE" -R "$R" --clobber "$@" && return 0; log "upload retry $i"; sleep $((i*15)); done; return 1; }

if ! gh release view "$STATE" -R "$R" >/dev/null 2>&1; then
  gh release create "$STATE" -R "$R" --draft --target "${GITHUB_SHA:-main}" -t "$STATE (build state, not a release)" \
    -n "Chromium $TAG $CPU staged-build state. Internal; deleted after the APK is verified." >/dev/null
  log "state release बनाया: $STATE"
fi
A=$(assets)
ev "patch_hash=$PATCH_HASH build_key=$BUILD_KEY expected_package=$EXP_PKG"
if grep -qx DONE <<<"$A"; then
  D=$(fetch_asset DONE | head -1)
  # "done" = patch-mechanism से पहले का baseline DONE (b7a2f0d), उसी base args पर
  if [ "$D" = "$BUILD_KEY" ] || { [ "$D" = done ] && [ "$PATCH_HASH" = none ]; }; then log "state DONE है (इसी build key पर) — build पहले ही पूरा"; out done true; ev "status=already-done"; exit 0; fi
  log "DONE पुरानी key ($D) का — patches/args बदले, incremental build"; gh release delete-asset "$STATE" DONE -R "$R" -y >/dev/null
fi
# src और शुरुआती out कहाँ से: अपनी state, वरना SEED_STATE
SEED="${SEED_STATE:-}"; SA=""; [ -n "$SEED" ] && SA=$(assets_of "$SEED")
SRC_STATE=""; OUT_STATE=""
if grep -q '^src\.tar\.zst\.part' <<<"$A"; then SRC_STATE=$STATE; elif grep -q '^src\.tar\.zst\.part' <<<"$SA"; then SRC_STATE=$SEED; fi
if grep -qx progress.json <<<"$A"; then OUT_STATE=$STATE; elif [ -n "$SRC_STATE" ] && grep -qx progress.json <<<"$SA"; then OUT_STATE=$SEED; fi
ev "src_state=${SRC_STATE:-none} out_state=${OUT_STATE:-none}"

# ---------- 2. fresh या restore ----------
cd "$ROOT"
if [ -z "$SRC_STATE" ]; then
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
  fetch_from "$SRC_STATE" src.sha256 > "$PK/src.sha256"
  for p in $(grep -o 'src\.tar\.zst\.part[0-9]*' "$PK/src.sha256"); do
    fetch_from "$SRC_STATE" "$p" > "$PK/$p"; (cd "$PK" && grep " $p\$" src.sha256 | sha256sum -c --quiet) || { echo "checksum FAIL $p"; exit 1; }
    cat "$PK/$p"; rm -f "$PK/$p"
  done | zstd -dc -T0 | tar -x -C "$ROOT"
  COMMIT=$(cat "$ROOT/COMMIT"); ev "tag=$TAG commit=$COMMIT"
  src/build/install-build-deps.sh --android --no-prompt --no-chromeos-fonts --no-arm >"$PK/deps.log" 2>&1 || { tail -40 "$PK/deps.log"; exit 1; }
  if [ -n "$OUT_STATE" ]; then
    fetch_from "$OUT_STATE" progress.json > "$PK/progress.json"
    PREV=$(python3 -c "import json;print(json.load(open('$PK/progress.json'))['out_prefix'])")
    fetch_from "$OUT_STATE" "$PREV.sha256" > "$PK/out.sha256"
    for p in $(grep -o "$PREV\.tar\.zst\.part[0-9]*" "$PK/out.sha256"); do
      fetch_from "$OUT_STATE" "$p" > "$PK/$p"; (cd "$PK" && grep " $p\$" out.sha256 | sha256sum -c --quiet) || { echo "checksum FAIL $p"; exit 1; }
      cat "$PK/$p"; rm -f "$PK/$p"
    done | zstd -dc -T0 | tar -x -C "$ROOT/src"
  fi
  ev "restore_seconds=$(( $(date +%s)-t0 ))"
fi
# ---------- 2b. इस परियोजना के patches (pristine src पर; mtime स्थिर epoch पर — patches.py देखें) ----------
# पिछली patch-स्थिति progress.json में है (out state के साथ परमाणु), इसलिए restore हुआ out और उसकी patch-स्थिति हमेशा मेल खाते हैं
PREVP=-; [ -f "$PK/progress.json" ] && PREVP="$PK/progress.json"
python3 "$CI_DIR/patches.py" apply src "$PDIR" "$PREVP" "$PK/patches.json"
PATCH_CHANGED=$(python3 -c "import json;print(int(json.load(open('$PK/patches.json'))['changed']))")
cp "$PK/patches.json" "$OUTPUTS_DIR/patches.json"
ev "patch_changed=$PATCH_CHANGED"
# ---------- 2c. args.gn (बदले हों तो लिखें; gn gen हर बार — सस्ता और idempotent) ----------
ARGS_CHANGED=0
if [ ! -f "src/$OUTD/args.gn" ] || ! diff -q <(printf '%s\n' "$ARGS") "src/$OUTD/args.gn" >/dev/null; then
  if [ -f "src/$OUTD/args.gn" ]; then ARGS_CHANGED=1; log "args.gn बदले:"; diff "src/$OUTD/args.gn" <(printf '%s\n' "$ARGS") || true; fi
  mkdir -p "src/$OUTD"; printf '%s\n' "$ARGS" > "src/$OUTD/args.gn"
fi
(cd src && buildtools/linux64/gn gen "$OUTD") | tail -2
ev "args_changed=$ARGS_CHANGED"

NINJA=src/third_party/ninja/ninja; [ -x "$NINJA" ] || NINJA=ninja
source "$CI_DIR/stage_lib.sh"
remaining(){ count_remaining "$NINJA" "src/$OUTD" chrome_public_apk; }
REM0=$(remaining); REM0=${REM0:-0}; ev "remaining_edges_at_start=$REM0"
if [ -f "$PK/progress.json" ]; then
  PREVREM=$(python3 -c "import json;print(json.load(open('$PK/progress.json'))['remaining_edges'])")
  ev "remaining_edges_prev_stage_end=$PREVREM"
  # watchdog: restore से पूरा हुआ काम दोबारा dirty हो गया तो रुकें (mtime/restore गड़बड़)
  # (patches/args बदलने पर काम का बढ़ना अपेक्षित है — तब watchdog लागू नहीं)
  if [ "$PATCH_CHANGED" = 0 ] && [ "$ARGS_CHANGED" = 0 ] && [ "$REM0" -gt $(( PREVREM + PREVREM/50 + 50 )) ]; then echo "WATCHDOG FAIL: restore के बाद काम बढ़ गया ($PREVREM -> $REM0)"; exit 1; fi
fi

if [ "${CHECK_ONLY:-0}" = 1 ]; then ev "CHECK_ONLY: restore + gn + ninja -n सफल; कुल/बचे edges=$REM0"; out done false; exit 0; fi

# ---------- 3. deadline तक compile ----------
NOW=$(date +%s); BUDGET=$(( DEADLINE - NOW ))
log "compile: budget ${BUDGET}s, -j$JOBS, $REM0 edges बाकी"
RC=0
if [ "$BUDGET" -gt 300 ]; then
  # monitor अपने process group में (setsid): अंत में पूरा group बंद, ताकि orphan `sleep` output pipe न पकड़े रहे
  setsid bash -c 'while sleep 600; do free -g | awk '"'"'/Mem:/{printf "mem used %sG; ",$3} /Swap:/{printf "swap used %sG; ",$3}'"'"'; df -BG --output=avail / | tail -1 | sed "s/^/disk free /"; done' &
  MON=$!
  set +e
  timeout -s INT -k 180 "$BUDGET" "$NINJA" -C "src/$OUTD" -j "$JOBS" chrome_public_apk > "$PK/ninja.log" 2>&1
  RC=$?; set -e; kill -- -"$MON" 2>/dev/null || kill "$MON" 2>/dev/null || true
  { grep -E '^\[[0-9]+/[0-9]+\]' "$PK/ninja.log" | tail -3; grep -E 'FAILED|error:' "$PK/ninja.log" | head -20; } || true
else RC=124; fi
REM1=$(remaining); REM1=${REM1:-0}
ev "ninja_rc=$RC remaining_edges_at_end=$REM1"
tail -c 200000 "$PK/ninja.log" > "$OUTPUTS_DIR/ninja-tail-stage-$STAGE.log" 2>/dev/null || true

# ---------- 4. out state pack/upload ----------
# हर stage/run का अलग नाम: restore का स्रोत (पिछला out) नया pack पूरा upload होने तक अछूता रहे
# (एक ही नाम पर --clobber से upload बीच में विफल हो तो एकमात्र out state नष्ट हो सकती थी)
PREFIX="out-s$STAGE-r${GITHUB_RUN_ID:-0}-${GITHUB_RUN_ATTEMPT:-1}"
# हमेशा pack (build पूरा होने पर भी): आगे कोई कदम विफल हो तो काम न खोए (~1 GB, ~2 मिनट)
if true; then
  log "out pack + upload ($PREFIX)"; t3=$(date +%s)
  du -sh "src/$OUTD" | sed 's/^/  out: /'
  tar --format=posix -C "$ROOT/src" -cf - "$OUTD" | zstd -T0 -3 -q | split -b 1900m -d -a 3 - "$PK/$PREFIX.tar.zst.part"
  (cd "$PK" && sha256sum $PREFIX.tar.zst.part* > $PREFIX.sha256)
  ev "out_pack_bytes=$(cat "$PK"/$PREFIX.tar.zst.part* | wc -c)"
  for f in "$PK"/$PREFIX.tar.zst.part*; do upload "$f"; rm -f "$f"; done; upload "$PK/$PREFIX.sha256"
  python3 - "$PK/progress.json" "$PK/patches.json" <<EOF
import json,sys,time
pt=json.load(open(sys.argv[2])); pt.pop("changed",None)
json.dump({"tag":"$TAG","cpu":"$CPU","commit":"$COMMIT","stage":$STAGE,"out_prefix":"$PREFIX",
  "remaining_edges":$REM1,"ninja_rc":$RC,"time":int(time.time()),"patches":pt},open(sys.argv[1],"w"))
EOF
  upload "$PK/progress.json"
  # पुराने out-s* assets हटाना
  for old in $(assets | grep -E '^out-s[0-9]+(-r[0-9]+-[0-9]+)?\.' | grep -v "^$PREFIX\." || true); do gh release delete-asset "$STATE" "$old" -R "$R" -y >/dev/null || true; done
  ev "out_pack_upload_seconds=$(( $(date +%s)-t3 ))"
fi
if [ "$RC" -ne 0 ] && [ "$RC" -ne 124 ]; then echo "BUILD ERROR (ninja rc=$RC) — state सुरक्षित, chain रुकी"; out done false; exit 1; fi
if [ "$REM1" -ne 0 ]; then log "समय समाप्त, $REM1 edges बाकी → अगला stage"; out done false; exit 0; fi

# ---------- 5. पूरा: पहले APK सुरक्षित, फिर सत्यापन ----------
APK="src/$OUTD/apks/ChromePublic.apk"; [ -f "$APK" ] || { echo "APK नहीं मिला"; exit 1; }
NAME="ChromePublic-$TAG-$CPU.apk"
cp "$APK" "$OUTPUTS_DIR/$NAME"           # workflow artifact में भी जाएगा
upload "$OUTPUTS_DIR/$NAME"               # सबसे पहले: महँगा परिणाम कभी न खोए
set +e                                    # रिपोर्ट के कदम script को नहीं रोकेंगे; निर्णायक जाँचें नीचे स्पष्ट हैं
export PATH="$ROOT/src/third_party/jdk/current/bin:$PATH"   # /usr/lib/jvm हटाया गया था; Chromium का अपना JDK
BT=$(ls -d src/third_party/android_sdk/public/build-tools/* 2>/dev/null | sort -V | tail -1)
"$BT/apksigner" verify --print-certs -v "$APK" > "$PK/apksigner.txt" 2>&1; SIGRC=$?
"$BT/aapt2" dump badging "$APK" > "$PK/badging.txt" 2>&1; AAPTRC=$?
{
  echo "tag=$TAG"; echo "commit=$COMMIT"; echo "cpu=$CPU"; echo "built_on=github ubuntu-24.04 standard runner (staged, stage $STAGE)"
  echo "build_tools=$(basename "$BT")"
  echo "patch_hash=$PATCH_HASH build_key=$BUILD_KEY"
  echo "--- patches"; python3 -c "import json;[print(x) for x in json.load(open('$PK/patches.json'))['series']]"
  echo "--- args.gn"; cat "src/$OUTD/args.gn"
  echo "--- sha256"; sha256sum "$APK" | cut -d' ' -f1
  echo "--- bytes"; stat -c %s "$APK"
  echo "--- clang"; cat src/third_party/llvm-build/Release+Asserts/cr_build_revision 2>/dev/null
  echo "--- apksigner verify (rc=$SIGRC)"; grep -vi warning "$PK/apksigner.txt" | sed -n 1,25p
  echo "--- aapt2 badging (rc=$AAPTRC)"; grep -E "^(package|sdkVersion|targetSdkVersion|native-code|application-label):" "$PK/badging.txt"
} > "$OUTPUTS_DIR/BUILD_INFO.txt"
cat "$OUTPUTS_DIR/BUILD_INFO.txt"
set -e
upload "$OUTPUTS_DIR/BUILD_INFO.txt"
[ "$SIGRC" = 0 ] || { echo "apksigner verify विफल (rc=$SIGRC)"; out done false; exit 1; }
grep -q "^package: name='$EXP_PKG'" "$PK/badging.txt" || { echo "badging में अपेक्षित package ($EXP_PKG) नहीं"; out done false; exit 1; }
echo "$BUILD_KEY" > "$PK/DONE"; upload "$PK/DONE"
out done true; ev "status=DONE"
