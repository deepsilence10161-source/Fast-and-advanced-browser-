#!/bin/bash
# Build पूरा होने के बाद: (वैकल्पिक) release signing -> सत्यापन -> BUILD_INFO -> gates -> DONE।
#
# दो तरह से चलता है:
#   * signing नहीं (patches/signing_cert_sha256.txt नहीं): chromium_stage.sh इसे सीधे चलाता है।
#   * signing ज़रूरी: chromium_stage.sh केवल build करके "sign=true" देता है; workflow का अलग step
#     (केवल उसी step को secrets) इसे चलाता है। इसलिए Chromium के build scripts/hooks/ninja (हज़ारों
#     तीसरे-पक्ष processes) के env में keystore/password कभी नहीं होते।
# Secrets (env, केवल signing step में): SIGNING_KS_B64 (PKCS12 keystore, base64), SIGNING_KS_PASS।
# Keystore का password args.gn/BUILD_INFO/state tar/logs में कभी नहीं जाता; keystore एक 700 temp dir में
# decode होकर signing के तुरंत बाद मिटता है। अपेक्षित cert SHA-256 (public) से मिलान अनिवार्य।
# Input: $CR_PK/finalize.env (chromium_stage.sh ने लिखा: declare -p)।
set -euo pipefail
PK=${CR_PK:-/home/runner/pk}
[ -f "$PK/finalize.env" ] || { echo "finalize.env नहीं मिला ($PK)"; exit 1; }
# shellcheck disable=SC1091
source "$PK/finalize.env"     # TAG CPU STAGE STATE R ROOT OUTD OUTPUTS_DIR COMMIT PATCH_HASH BUILD_KEY EXP_PKG EXP_CERT EXP_NONDEBUG
log(){ echo "[$(date -u +%H:%M:%S)] $*"; }
out(){ echo "$1=$2" >> "${GITHUB_OUTPUT:-/dev/null}"; }
EVID="$OUTPUTS_DIR/stage-$STAGE.txt"; touch "$EVID"
ev(){ echo "$*" | tee -a "$EVID"; }
upload(){ local i; for i in 1 2 3 4; do gh release upload "$STATE" -R "$R" --clobber "$@" && return 0; log "upload retry $i"; sleep $((i*15)); done; return 1; }
fail(){ echo "$*"; out done false; exit 1; }
cd "$ROOT"

APK="src/$OUTD/apks/ChromePublic.apk"; [ -f "$APK" ] || fail "APK नहीं मिला"
NAME="ChromePublic-$TAG-$CPU.apk"
mkdir -p "$OUTPUTS_DIR"
export PATH="$ROOT/src/third_party/jdk/current/bin:$PATH"   # /usr/lib/jvm हटाया गया था; Chromium का अपना JDK
BT=$(ls -d src/third_party/android_sdk/public/build-tools/* 2>/dev/null | sort -V | tail -1)
[ -n "$BT" ] || fail "build-tools नहीं मिले"

SIGNING=debug
if [ -n "$EXP_CERT" ]; then
  # ---------- release signing ----------
  [ -n "${SIGNING_KS_B64:-}" ] && [ -n "${SIGNING_KS_PASS:-}" ] || \
    fail "release signing ज़रूरी (patches/signing_cert_sha256.txt) पर secrets SIGNING_KS_B64/SIGNING_KS_PASS नहीं मिले"
  pkill -f fast_local_dev_server 2>/dev/null || true          # build का बचा daemon (same user) signing के समय न रहे
  KSD=$(mktemp -d); chmod 700 "$KSD"; trap 'rm -rf "$KSD"' EXIT
  ( umask 077
    printf '%s' "$SIGNING_KS_B64" | base64 -d > "$KSD/ks.p12"
    printf '%s' "$SIGNING_KS_PASS" > "$KSD/pass"
    cp "$KSD/pass" "$KSD/kpass" )   # अलग फ़ाइल: एक ही file: दोनों को देने पर apksigner क्रम से पंक्ति 1, 2 पढ़ता है
  unset SIGNING_KS_B64 SIGNING_KS_PASS
  # --alignment-preserved: Chromium ने libs को 16 KB page पर align किया है (apkbuilder.py) — वैसा ही रहे।
  # --v4-signing-enabled false: अलग .idsig फ़ाइल नहीं। minSdk 29 पर apksigner v3 लगाता है (Android 9+ verify)।
  # (स्थानीय सत्यापन: build-tools 36, असली x64 APK 397 MB, 3 s; cert मिलान; सभी .so offset %16384 = 0)
  set +e
  "$BT/apksigner" sign --ks "$KSD/ks.p12" --ks-type PKCS12 --ks-key-alias swiftra \
    --ks-pass "file:$KSD/pass" --key-pass "file:$KSD/kpass" \
    --alignment-preserved true --v4-signing-enabled false --out "$OUTPUTS_DIR/$NAME" "$APK" > "$PK/sign.log" 2>&1
  SRC_RC=$?
  set -e
  rm -rf "$KSD"; trap - EXIT
  [ "$SRC_RC" = 0 ] || { grep -vi pass "$PK/sign.log" | tail -20 || true; fail "apksigner sign विफल (rc=$SRC_RC)"; }
  # upload से पहले: गलत key से signed APK कभी अंतिम नाम से न जाए (unsigned presign पहले से सुरक्षित है)
  PRE=$("$BT/apksigner" verify --print-certs "$OUTPUTS_DIR/$NAME" 2>/dev/null | \
        sed -n 's/^Signer #1 certificate SHA-256 digest: *\([0-9a-fA-F]*\).*/\1/p' | head -1 | tr 'A-F' 'a-f') || true
  if [ "$PRE" != "$EXP_CERT" ]; then rm -f "$OUTPUTS_DIR/$NAME"; fail "signer cert (${PRE:-?}) अपेक्षित release cert ($EXP_CERT) से अलग — upload नहीं किया"; fi
  SIGNING=release
else
  cp "$APK" "$OUTPUTS_DIR/$NAME"
fi
FINAL="$OUTPUTS_DIR/$NAME"
upload "$FINAL"                           # सबसे पहले: महँगा परिणाम कभी न खोए

set +e                                    # रिपोर्ट के कदम script को नहीं रोकेंगे; निर्णायक जाँचें नीचे स्पष्ट हैं
"$BT/apksigner" verify --print-certs -v "$FINAL" > "$PK/apksigner.txt" 2>&1; SIGRC=$?
"$BT/aapt2" dump badging "$FINAL" > "$PK/badging.txt" 2>&1; AAPTRC=$?
CERT=$(sed -n 's/^Signer #1 certificate SHA-256 digest: *\([0-9a-fA-F]*\).*/\1/p' "$PK/apksigner.txt" | head -1 | tr 'A-F' 'a-f')
{
  echo "tag=$TAG"; echo "commit=$COMMIT"; echo "cpu=$CPU"; echo "built_on=github ubuntu-24.04 standard runner (staged, stage $STAGE)"
  echo "build_tools=$(basename "$BT")"
  echo "patch_hash=$PATCH_HASH build_key=$BUILD_KEY"
  echo "signing=$SIGNING signer_cert_sha256=${CERT:-?} expected_cert_sha256=${EXP_CERT:-none}"
  echo "--- patches"; python3 -c "import json;d=json.load(open('$PK/patches.json'));[print(x) for x in d['series']];[print('overlay:',x) for x in d.get('overlay',[])]"
  echo "--- args.gn"; cat "src/$OUTD/args.gn"
  echo "--- sha256"; sha256sum "$FINAL" | cut -d' ' -f1
  echo "--- bytes"; stat -c %s "$FINAL"
  echo "--- clang"; cat src/third_party/llvm-build/Release+Asserts/cr_build_revision 2>/dev/null
  # "public key" पंक्तियाँ बाहर (gitleaks इन्हें key समझता है; cert digest ही पर्याप्त)
  echo "--- apksigner verify (rc=$SIGRC)"; grep -vi -e warning -e "public key" "$PK/apksigner.txt" | sed -n 1,25p
  echo "--- aapt2 badging (rc=$AAPTRC)"
  grep -E "^(package|sdkVersion|minSdkVersion|targetSdkVersion|native-code|application-label|application-debuggable)(:|$)" "$PK/badging.txt"
} > "$OUTPUTS_DIR/BUILD_INFO.txt"
cat "$OUTPUTS_DIR/BUILD_INFO.txt"
set -e
upload "$OUTPUTS_DIR/BUILD_INFO.txt"
[ "$SIGRC" = 0 ] || fail "apksigner verify विफल (rc=$SIGRC)"
grep -q "^package: name='$EXP_PKG'" "$PK/badging.txt" || fail "badging में अपेक्षित package ($EXP_PKG) नहीं"
if [ -n "$EXP_CERT" ]; then
  [ "$CERT" = "$EXP_CERT" ] || fail "signer cert ($CERT) अपेक्षित release cert ($EXP_CERT) से अलग"
fi
if [ "$EXP_NONDEBUG" = 1 ] && grep -q "^application-debuggable" "$PK/badging.txt"; then
  fail "debuggable_apks = false होने पर भी APK debuggable है"
fi
ev "signing=$SIGNING signer_cert=${CERT:0:16}"
echo "$BUILD_KEY" > "$PK/DONE"; upload "$PK/DONE"
out done true; ev "status=DONE"
