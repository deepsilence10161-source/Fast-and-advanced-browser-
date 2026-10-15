#!/bin/bash
# नए session में एक बार चलाएँ: permissions, gitleaks, hooks, credential helper ठीक करता है।
# Workspace snapshot executable bits/permissions और excluded dirs (.cache, .git/config) नहीं रखता।
set -uo pipefail
H=/home/user; REPO=$H/fab; URL=https://github.com/deepsilence10161-source/Fast-and-advanced-browser-.git
if [ -d $H/.secrets ]; then chmod 700 $H/.secrets; chmod 600 $H/.secrets/gh_token 2>/dev/null; chmod 700 $H/.secrets/*.sh 2>/dev/null; fi
[ -d "$REPO/.git" ] || git clone -q "$URL" "$REPO"
git -C "$REPO" config credential.helper "$H/.secrets/git-cred.sh"
git -C "$REPO" config user.name "arena-agent"; git -C "$REPO" config user.email "agent@users.noreply.github.com"
git -C "$REPO" fetch -q origin && git -C "$REPO" status -sb | head -1
find "$REPO/tools" -type f \( -name '*.sh' -o -name '*.py' -o -name gitx -o -path '*/hooks/*' \) -exec chmod +x {} \;
[ -L $H/tools ] || { [ -e $H/tools ] && mv $H/tools $H/.cache/tools.old.$$; ln -s "$REPO/tools" $H/tools; }
bash "$REPO/tools/install-gitleaks.sh"
bash "$REPO/tools/secret-guard/install-hooks.sh" "$REPO"
echo "bootstrap OK"
