#!/bin/bash
# Token-सुरक्षा audit: हर जाँच PASS/FAIL; token का मान कभी print नहीं होता। Exit 0 = सब PASS।
# Usage: audit.sh [--no-network]
set -u
SG=$(cd "$(dirname "$(readlink -f "$0")")" && pwd); source "$SG/lib.sh"
P=0; F=0; ok(){ echo "PASS  $1"; P=$((P+1)); }; bad(){ echo "FAIL  $1"; F=$((F+1)); }; note(){ echo "NOTE  $1"; }
[ "$(stat -c %a "$SG_VAULT" 2>/dev/null)" = 700 ] && ok "01 vault dir 700" || bad "01 vault dir perms $(stat -c %a "$SG_VAULT" 2>/dev/null)"
[ -f "$SG_TOKEN" ] && [ ! -L "$SG_TOKEN" ] && [ "$(stat -c %a "$SG_TOKEN")" = 600 ] && [ "$(stat -c %U "$SG_TOKEN")" = "$(id -un)" ] \
  && ok "02 token फ़ाइल: regular, 600, owner $(id -un)" || bad "02 token फ़ाइल perms/type"
[ -s "$SG_TOKEN" ] && [ "$(wc -l < "$SG_TOKEN")" -le 1 ] && ok "03 token फ़ाइल में एक ही मान" || bad "03 token फ़ाइल खाली/अनपेक्षित"
case "$(readlink -f "$SG_VAULT")" in "$SG_REPO"*) bad "04 vault repo के अंदर है";; *) ok "04 vault किसी git repo के बाहर";; esac
git -C "$SG_REPO" check-ignore -q .secrets/x && ok "05 .gitignore में .secrets/" || bad "05 .gitignore में .secrets/ नहीं"
hits=$(grep -rIlF --exclude-dir=.secrets -f "$SG_TOKEN" "$SG_HOME" 2>/dev/null)
[ -z "$hits" ] && ok "06 workspace में exact token कहीं नहीं (vault छोड़कर)" || { bad "06 token इन फ़ाइलों में:"; echo "$hits" | sed 's/^/      /'; }
B=$(python3 -c "import base64,sys;t=open(sys.argv[1]).read().strip();print(base64.b64encode(t.encode()).decode()[:40]);print(base64.b64encode(('x-access-token:'+t).encode()).decode()[:40])" "$SG_TOKEN")
hits=$(grep -rIlF --exclude-dir=.secrets -e "$(sed -n 1p <<<"$B")" -e "$(sed -n 2p <<<"$B")" "$SG_HOME" 2>/dev/null)
[ -z "$hits" ] && ok "07 workspace में base64 रूप कहीं नहीं" || bad "07 base64 रूप मिला: $hits"
if [ -e "$SG_HOME/.git-credentials" ] || [ -e "$SG_HOME/.netrc" ]; then bad "08 ~/.git-credentials या ~/.netrc मौजूद"; else ok "08 ~/.git-credentials और ~/.netrc नहीं"; fi
cfg=$( { git -C "$SG_REPO" config --list 2>/dev/null; git config --global --list 2>/dev/null; } )
if grep -qF -f "$SG_TOKEN" <<<"$cfg" || grep -qiE '://[^/ ]*@github|extraheader' <<<"$cfg"; then bad "09 git config में credential/URL-token"; else ok "09 git config (local+global) में कोई credential नहीं"; fi
[ "$(git -C "$SG_REPO" config --get remote.origin.url)" = "$SG_URL" ] && ok "10 origin URL साफ़ (बिना userinfo)" || bad "10 origin URL: अनुपस्थित/अलग"
[ "$(git -C "$SG_REPO" config --get core.hooksPath)" = "$SG_DIR/hooks" ] && [ -x "$SG_DIR/hooks/pre-commit" ] && [ -x "$SG_DIR/hooks/pre-push" ] && [ -x "$SG_DIR/hooks/commit-msg" ] \
  && ok "11 hooks सक्रिय (core.hooksPath, executable)" || bad "11 hooks सक्रिय नहीं"
[ -x "$SG_HOME/.cache/gitleaks/gitleaks" ] && ok "12 gitleaks मौजूद (SHA-256 सत्यापित install)" || bad "12 gitleaks नहीं"
hb=0; for h in gh.sh git-cred.sh; do cmp -s "$SG_DIR/$h" "$SG_VAULT/$h" && [ "$(stat -c %a "$SG_VAULT/$h")" = 700 ] || hb=1; done
[ $hb = 0 ] && ok "13 helpers vault में, 700, repo version से मेल" || bad "13 helper पुराना/perms गलत"
grep -laF -f "$SG_TOKEN" /proc/[0-9]*/cmdline 2>/dev/null | grep -q . && bad "14 किसी process के argv में token" || ok "14 किसी चल रहे process के argv में token नहीं"
if [ "${1:-}" != --no-network ]; then
  repo=$(sed -E 's#https://github.com/##; s#\.git$##' <<<"$SG_URL")
  j=$("$SG_VAULT/gh.sh" "/repos/$repo")
  python3 -c "import json,sys;d=json.load(sys.stdin)['security_and_analysis'];sys.exit(0 if d['secret_scanning']['status']=='enabled' and d['secret_scanning_push_protection']['status']=='enabled' else 1)" <<<"$j" \
    && ok "15 GitHub secret scanning + push protection: enabled" || bad "15 GitHub secret scanning/push protection बंद"
  grep -qF -f "$SG_TOKEN" <<<"$j" && bad "16 API output में token" || ok "16 API output में token नहीं (redaction)"
  exp=$("$SG_VAULT/gh.sh" /rate_limit -D - -o /dev/null | grep -i '^github-authentication-token-expiration' | cut -d' ' -f2- | tr -d '\r')
  [ -n "$exp" ] && note "token expiry: $exp — काम पूरा होने पर revoke/rotate करें"
fi
# 17 release keystore (Swiftra signing): vault में 600; password vault के बाहर/किसी argv में नहीं
KSP="$SG_VAULT/swiftra-ks-pass"; KS="$SG_VAULT/swiftra-release.p12"
if [ -f "$KSP" ] || [ -f "$KS" ]; then
  kp_ok=1
  for f in "$KS" "$KSP"; do [ -f "$f" ] && [ ! -L "$f" ] && [ "$(stat -c %a "$f")" = 600 ] || kp_ok=0; done
  [ -s "$KSP" ] && hits=$(grep -rIlF --exclude-dir=.secrets -f "$KSP" "$SG_HOME" 2>/dev/null) || hits=""
  [ -n "$hits" ] && kp_ok=0
  grep -laF -f "$KSP" /proc/[0-9]*/cmdline 2>/dev/null | grep -q . && kp_ok=0
  [ $kp_ok = 1 ] && ok "17 release keystore: vault में 600; password vault के बाहर/argv में नहीं" \
    || { bad "17 release keystore perms/रिसाव"; [ -n "$hits" ] && echo "$hits" | sed 's/^/      /'; }
fi
# 18 हर vault secret (token, keystore password/bytes, private keys का केवल private हिस्सा) workspace + /tmp में कहीं नहीं
#    (/tmp में CI artifacts/logs आते हैं; platform का hydrate.zip केवल .secrets/ प्रति हो तो NOTE)
ls_out=$(python3 "$SG_DIR/leakscan.py" paths "$SG_HOME" /tmp 2>&1); ls_rc=$?
[ $ls_rc = 0 ] && ok "18 leakscan: $(tail -1 <<<"$ls_out" | sed 's/^LEAKSCAN paths: //')" \
  || { bad "18 leakscan (rc=$ls_rc)"; grep '^LEAK' <<<"$ls_out" | sed 's/^/      /'; }
# 19 CI hygiene: secrets केवल env: से (run: के अंदर ${{ secrets.* }} नहीं), pull_request_target नहीं, हर workflow में permissions:
WF="$SG_REPO/.github/workflows"; hy=""
for f in "$WF"/*.yml; do
  grep -q '^permissions:' "$f" || hy="$hy $(basename "$f"):no-permissions"
  grep -q 'pull_request_target' "$f" && hy="$hy $(basename "$f"):pull_request_target"
  awk '/^ *(- )?run: *\|/{r=1;next} /^ *(- )?(name|uses|with|env|if|id|shell|timeout-minutes|continue-on-error):/{r=0} r && /\$\{\{ *secrets\./{print FILENAME": "FNR}' "$f" | grep -q . \
    && hy="$hy $(basename "$f"):secret-in-run"
done
[ -z "$hy" ] && ok "19 CI workflows: secrets केवल env से, pull_request_target नहीं, permissions घोषित" || bad "19 CI hygiene:$hy"
if [ "${1:-}" != --no-network ]; then
  repo=$(sed -E 's#https://github.com/##; s#\.git$##' <<<"$SG_URL")
  cl=$(timeout 600 python3 "$SG_DIR/leakscan.py" ci-logs "$repo" "${SG_CI_RUNS:-8}" 2>&1); cl_rc=$?
  [ $cl_rc = 0 ] && ok "20 CI logs: $(tail -1 <<<"$cl" | sed 's/^LEAKSCAN ci-logs: //')" \
    || { bad "20 CI logs leakscan (rc=$cl_rc)"; grep '^LEAK' <<<"$cl" | sed 's/^/      /'; }
fi
[ -f /tmp/arena-workspace/hydrate.zip ] && note "/tmp/arena-workspace/hydrate.zip: platform का workspace-restore archive (vault की प्रति सहित); workspace के बाहर, snapshot में नहीं"
echo "AUDIT: $P पास, $F विफल"; [ $F = 0 ]
