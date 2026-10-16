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
[ -f /tmp/arena-workspace/hydrate.zip ] && note "/tmp/arena-workspace/hydrate.zip: platform का workspace-restore archive (vault की प्रति सहित); workspace के बाहर, snapshot में नहीं"
echo "AUDIT: $P पास, $F विफल"; [ $F = 0 ]
