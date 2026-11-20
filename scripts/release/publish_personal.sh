#!/bin/bash
# Usage: publish_personal.sh <cpu> [<cpu>...]   (x64 | arm64)
# Copies the personal DEVELOPMENT APK from the draft crstate release to a public PRE-release after verifying
# (a) APK sha256 == BUILD_INFO sha256, (b) BUILD_INFO says personal_source_only=1 and signer==expected.
# Never touches the ordinary Swiftra release/update feed.
set -euo pipefail
R=deepsilence10161-source/Fast-and-advanced-browser-
TAG=swiftra-personal-dev
H="Authorization: Bearer $(cat /tmp/.gh_tok)"
api(){ curl -fsS -H "$H" -H "Accept: application/vnd.github+json" "$@"; }
mkdir -p /tmp/pub && cd /tmp/pub
rel=$(api "https://api.github.com/repos/$R/releases/tags/$TAG" 2>/dev/null || true)
if [ -z "$rel" ]; then
  rel=$(api -X POST "https://api.github.com/repos/$R/releases" -d "$(python3 - <<'P'
import json
print(json.dumps({"tag_name":"swiftra-personal-dev","target_commitish":"main","name":"Swiftra Personal (private-mode) - DEVELOPMENT build, NOT certified","prerelease":True,"draft":False,
"body":"DEVELOPMENT ONLY. Separate app (com.swiftra.personaldev); does not touch com.swiftra.app data. Not privacy-certified; not offered through the ordinary Swiftra update feed. See docs/plans/personal-browser-containment.md and TESTING.md for exactly what was and was not tested. Face Guard is NOT in this build."}))
P
)")
fi
rid=$(python3 -c "import sys,json;print(json.loads(sys.argv[1])['id'])" "$rel")
for cpu in "$@"; do
  st=crstate-158.0.8127.42-$cpu-personal-dev
  src=$(api "https://api.github.com/repos/$R/releases?per_page=50" | python3 -c "
import sys,json
for r in json.load(sys.stdin):
  if r['tag_name']=='$st': print(json.dumps({a['name']:a['id'] for a in r['assets']}))")
  aid=$(python3 -c "import sys,json;print(json.loads(sys.argv[1]).get('ChromePublic-158.0.8127.42-$cpu.apk',''))" "$src")
  bid=$(python3 -c "import sys,json;print(json.loads(sys.argv[1]).get('BUILD_INFO.txt',''))" "$src")
  [ -n "$aid" ] && [ -n "$bid" ] || { echo "NO APK for $cpu yet"; exit 3; }
  curl -fsSL -H "$H" -H "Accept: application/octet-stream" "https://api.github.com/repos/$R/releases/assets/$bid" -o BUILD_INFO-$cpu.txt
  curl -fsSL -H "$H" -H "Accept: application/octet-stream" "https://api.github.com/repos/$R/releases/assets/$aid" -o Swiftra-Personal-$cpu.apk
  want=$(grep -A1 -- '--- sha256' BUILD_INFO-$cpu.txt | tail -1); got=$(sha256sum Swiftra-Personal-$cpu.apk | cut -d' ' -f1)
  [ "$want" = "$got" ] || { echo "SHA MISMATCH $cpu"; exit 4; }
  grep -q '^personal_source_only=1' BUILD_INFO-$cpu.txt || { echo "not personal build"; exit 5; }
  s=$(grep -o 'signer_cert_sha256=[0-9a-f]*' BUILD_INFO-$cpu.txt | cut -d= -f2); e=$(grep -o 'expected_cert_sha256=[0-9a-f]*' BUILD_INFO-$cpu.txt | cut -d= -f2)
  [ -n "$s" ] && [ "$s" = "$e" ] || { echo "signer mismatch"; exit 6; }
  python3 /home/user/swiftra-repo/scripts/release/personal_gate.py --cpu $cpu --build-info BUILD_INFO-$cpu.txt --apk-sha $got --evidence $(ls /home/user/swiftra-repo/evidence/personal-e2e-*.json /home/user/swiftra-repo/evidence/face-guard-apk-*.json /home/user/swiftra-repo/evidence/clipboard-apk-*.json 2>/dev/null) 2>/dev/null || python3 /home/user/swiftra-repo/scripts/release/personal_gate.py --cpu $cpu --build-info BUILD_INFO-$cpu.txt --apk-sha $got --evidence $(ls /home/user/swiftra-repo/evidence/personal-e2e-*.json /home/user/swiftra-repo/evidence/face-guard-apk-*.json /home/user/swiftra-repo/evidence/clipboard-apk-*.json 2>/dev/null) || { echo "personal gate refused $cpu"; exit 7; }
  echo "$cpu verified sha256=$got size=$(stat -c %s Swiftra-Personal-$cpu.apk)"
  for f in Swiftra-Personal-$cpu.apk BUILD_INFO-$cpu.txt; do
    old=$(api "https://api.github.com/repos/$R/releases/$rid/assets" | python3 -c "
import sys,json
for a in json.load(sys.stdin):
  if a['name']=='$f': print(a['id'])")
    [ -n "$old" ] && api -X DELETE "https://api.github.com/repos/$R/releases/assets/$old" >/dev/null
    ct=application/octet-stream; [ "${f##*.}" = apk ] && ct=application/vnd.android.package-archive
    curl -fsS -H "$H" -H "Content-Type: $ct" --data-binary @"$f" "https://uploads.github.com/repos/$R/releases/$rid/assets?name=$f" >/dev/null
    echo "uploaded $f"
  done
done
# Update the release body so it states exactly which layers the uploaded builds contain.
fg=no; sg=no; cb=no; ge=no
for cpu in "$@"; do
  grep -q '^0105-face-guard-presence-mode.patch' /tmp/pub/BUILD_INFO-$cpu.txt && fg=yes
  grep -q '^0107-personal-signin-message.patch' /tmp/pub/BUILD_INFO-$cpu.txt && sg=yes
  grep -q '^0109-personal-omnibox-clipboard.patch' /tmp/pub/BUILD_INFO-$cpu.txt && cb=yes
  grep -q '^0111-personal-google-egress.patch' /tmp/pub/BUILD_INFO-$cpu.txt && ge=yes
done
body=$(FG=$fg SG=$sg CB=$cb GE=$ge python3 - <<'P'
import json,os
t="DEVELOPMENT ONLY. Separate app (com.swiftra.personaldev); does not touch com.swiftra.app data. Not privacy-certified; not offered through the ordinary Swiftra update feed. See docs/plans/personal-browser-containment.md and TESTING.md for exactly what was and was not tested."
if os.environ["FG"]=="yes":
    t+=" Face Guard (experimental, OFF by default) is in the most recently uploaded build: it only checks that A face is visible to the front camera. It does NOT recognise whose face it is, has no liveness check (a photo may fool it) and is a convenience lock, not security. Measured only on the x64 Android emulator with a still-image camera: one visible face unlocks, a second face keeps it locked (the second-face test used one detectable face shown twice); not tested with a real phone camera, and ARM64 has no camera test. Owner-only mode (Settings > Privacy, needs a device PIN, pattern or password) skips the camera and unlocks only through the phone own fingerprint, face or PIN prompt; it was measured on the emulator with the device PIN, NOT with a real fingerprint or face. Earlier builds could crash while locked (tab-switcher Hub, 3 of 4 two-face runs); this build passed its two-face runs on x64 (2 of 2), which is a small sample; the cause of the crash was never proven."
else:
    t+=" Face Guard is NOT in this build."
if os.environ["SG"]=="yes":
    t+=" Browser sign-in/Sync is intentionally off; the build says so instead of a generic 'Can't sign in'. Sign in on websites instead."
if os.environ["CB"]=="yes":
    t+=" Clipboard: copy/cut in the address bar and Find-in-page stay inside the browser (measured on Android emulator/Redroid, synthetic text; see TESTING.md). Settings > Homepage address box: copy/cut stays inside the browser too (measured on the same runs; earlier builds leaked it). Other dialogs and keyboard/IME clipboard history are NOT audited. Do not assume the system clipboard is never used. Whole-profile encryption is NOT implemented; stored data relies on Android file-based encryption plus the Keystore-backed cookie/card key."
else:
    t+=" KNOWN LEAK: text copied from the address bar or Find-in-page reaches the Android system clipboard in this build."
if os.environ["GE"]=="yes":
    t+=" Network (x64 emulator, Chromium NetLog only): with no tabs open and while browsing a test page this build made 0 requests to Google (earlier build: doodle, search-suggestion and default-tile requests at every New Tab). Built-in tiles, the doodle, the AI Mode check, the network-time query and search suggestions are off. Not measured: what a submitted search sends to the default search engine (Google), Android/Play services, the keyboard, your IP address. Local traces (synthetic URL scan of the app files): Delete browsing data (All time) removed History, usage DB, cache and Top Sites entries, and the page archive copy is no longer created; the tab/session-restore files still held the URL afterwards, so this is NOT a guarantee that history is unrecoverable (flash-level recovery was not assessed)."
t+=" Autofill: on the emulator/Redroid runs no autofill request was sent for web login fields. Passkeys/Credential Manager: no request is sent and passkeys are effectively unsupported in this build."
print(json.dumps({"body":t}))
P
)
api -X PATCH "https://api.github.com/repos/$R/releases/$rid" -d "$body" >/dev/null && echo "release body updated (face_guard=$fg signin_msg=$sg clipboard_fix=$cb)"
echo "https://github.com/$R/releases/tag/$TAG"
