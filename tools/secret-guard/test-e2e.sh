#!/bin/bash
# Token-सुरक्षा E2E परीक्षण। असली token केवल local repo में (कभी push नहीं); push-tests केवल नकली token से।
# Usage: test-e2e.sh <local-clone-path>
set -u
REPO=${1:?repo path}; SG=/home/user/tools/secret-guard; S=/home/user/.secrets
OWNER_REPO=$(git -C "$REPO" remote get-url origin | sed -E 's#https://github.com/##; s#\.git$##')
P=0; F=0; ok(){ echo "PASS  $1"; P=$((P+1)); }; bad(){ echo "FAIL  $1"; F=$((F+1)); }
FAKE="github_pat_$(python3 -c "import secrets,string;a=string.ascii_letters+string.digits;print('11'+''.join(secrets.choice(a) for _ in range(20))+'_'+''.join(secrets.choice(a) for _ in range(59)))")"
GC="git -c user.name=sg-test -c user.email=sg-test@users.noreply.github.com"
cd "$REPO"; START=$(git rev-parse --abbrev-ref HEAD); BASE=$(git rev-parse HEAD)
cleanup(){ git reset -q --hard "$BASE"; git checkout -q "$START" 2>/dev/null; git clean -qfd; git branch -D sg-t1 sg-t2 >/dev/null 2>&1; }

# 1 API helper
$S/gh.sh /user | grep -q '"login"' && ok "01 gh.sh: API auth काम करता है" || bad "01 gh.sh auth"
# 2 argv
( for i in $(seq 1 60); do grep -laF -f $S/gh_token /proc/[0-9]*/cmdline 2>/dev/null; sleep 0.03; done ) > /tmp/sg_argv & W=$!
for i in 1 2 3; do $S/gh.sh /rate_limit >/dev/null; done; $SG/gitx ls-remote origin >/dev/null; wait $W
[ -s /tmp/sg_argv ] && bad "02 token process argv में दिखा" || ok "02 token किसी process के argv में नहीं (curl+git)"
# 3 redact
out=$( { cat $S/gh_token; echo; echo "$FAKE"; echo "Authorization: Bearer abc.def"; printf 'x-access-token:%s' "$(cat $S/gh_token)" | base64 -w0; echo; } | $SG/redact.py )
if printf '%s' "$out" | grep -qF -f $S/gh_token || printf '%s' "$out" | grep -qF "$FAKE" || printf '%s' "$out" | grep -qF "abc.def"; then bad "03 redact"; 
else [ "$(printf '%s\n' "$out" | grep -c REDACTED)" = 4 ] && ok "03 redact: असली+नकली+Bearer+base64 चारों masked" || bad "03 redact count"; fi
# 4 config
$SG/gitx fetch -q origin >/dev/null; grep -qiE "extraheader|pat_|x-access-token" .git/config && bad "04 .git/config" || ok "04 gitx fetch सफल, .git/config में token नहीं"
# 5 negative: साफ़ commit होना चाहिए
echo "clean $(date +%s)" > sg_clean.txt; git add sg_clean.txt
$GC commit -qm "clean test" >/tmp/sg5 2>&1 && ok "05 साफ़ commit नहीं रुका (false-positive नहीं)" || { bad "05 साफ़ commit रुका"; cat /tmp/sg5; }
git reset -q --hard "$BASE"
# 6 असली token commit (local)
cp $S/gh_token sg_real.txt; git add sg_real.txt
if $GC commit -qm t >/tmp/sg6 2>&1; then bad "06 असली token commit हो गया"; git reset -q --hard "$BASE"; else grep -q "असली-TOKEN" /tmp/sg6 && ok "06 pre-commit ने असली token रोका (exact match)" || bad "06 रुका पर कारण गलत"; fi
grep -qF -f $S/gh_token /tmp/sg6 && bad "06b hook output में token छपा" || ok "06b hook output में token नहीं छपा"
git reset -q sg_real.txt; shred -u sg_real.txt
# 7 नकली pattern token
echo "token=$FAKE" > sg_fake.txt; git add sg_fake.txt
if $GC commit -qm t >/tmp/sg7 2>&1; then bad "07 नकली token commit हो गया"; git reset -q --hard "$BASE"; else grep -q "gitleaks\] संभावित secret" /tmp/sg7 && ok "07 pre-commit (gitleaks) ने token-pattern पहचाना" || { bad "07 कारण गलत"; cat /tmp/sg7; }; fi
grep -qF "$FAKE" /tmp/sg7 && bad "07b output में नकली token छपा" || ok "07b output redacted"
git reset -q sg_fake.txt; rm -f sg_fake.txt
# 8 commit message
echo ok > sg_ok.txt; git add sg_ok.txt
$GC commit -qm "msg $FAKE" >/tmp/sg8 2>&1 && { bad "08 commit-msg"; git reset -q --hard "$BASE"; } || ok "08 commit-msg hook ने message में token रोका"
git reset -q sg_ok.txt; rm -f sg_ok.txt
# 9 pre-push: --no-verify commit, push रुकना चाहिए (केवल नकली)
git checkout -q -b sg-t1; echo "k=$FAKE" > sg_p.txt; git add sg_p.txt; $GC commit -q --no-verify -m t
$SG/gitx push -q origin sg-t1 >/tmp/sg9 2>&1
if $S/gh.sh "/repos/$OWNER_REPO/branches/sg-t1" | grep -q '"name": "sg-t1"'; then bad "09 नकली token वाली branch push हो गई"; $SG/gitx push -q origin --delete sg-t1; else grep -q "gitleaks\] संभावित" /tmp/sg9 && ok "09 pre-push ने push रोका (remote पर branch नहीं बनी)" || { bad "09 कारण गलत"; cat /tmp/sg9; }; fi
git checkout -q "$START"; git branch -qD sg-t1
# 10 negative push: साफ़ branch push होनी चाहिए, फिर हटाओ
git checkout -q -b sg-t2; echo "clean" > sg_c.txt; git add sg_c.txt; $GC commit -qm "clean push test"
$SG/gitx push -q origin sg-t2 >/tmp/sg10 2>&1
if $S/gh.sh "/repos/$OWNER_REPO/branches/sg-t2" | grep -q '"name": "sg-t2"'; then ok "10 साफ़ push सफल (false-positive नहीं)"; $SG/gitx push -q origin --delete sg-t2 >/dev/null; else bad "10 साफ़ push रुका"; cat /tmp/sg10; fi
git checkout -q "$START"; git branch -qD sg-t2
# 11 scanner failure पर fail-closed
mv /home/user/.cache/gitleaks/gitleaks /home/user/.cache/gitleaks/gitleaks.off; echo x > sg_f.txt; git add sg_f.txt
$GC commit -qm t >/tmp/sg11 2>&1 && { bad "11 स्कैनर गायब होने पर भी commit हुआ"; git reset -q --hard "$BASE"; } || ok "11 स्कैनर न होने पर commit रुका (fail-closed)"
mv /home/user/.cache/gitleaks/gitleaks.off /home/user/.cache/gitleaks/gitleaks; git reset -q sg_f.txt; rm -f sg_f.txt
cleanup
# 12 workspace और history साफ़
$SG/scan.sh dir /home/user >/tmp/sg12 2>&1 && ok "12 पूरा workspace साफ़ (.secrets छोड़कर)" || { bad "12 workspace"; cat /tmp/sg12; }
$SG/scan.sh repo "$REPO" >/tmp/sg13 2>&1 && ok "13 repo की पूरी git history साफ़" || { bad "13 history"; cat /tmp/sg13; }
rm -f /tmp/sg[0-9]* /tmp/sg_argv
echo "परिणाम: $P पास, $F विफल"; [ $F = 0 ]
