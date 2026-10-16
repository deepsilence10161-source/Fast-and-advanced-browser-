#!/bin/bash
# हर नए session की शुरुआत में (और कभी भी): secret-guard self-heal + audit।
# Snapshot permissions, .git/config, .git/hooks, ~/.cache, ~/tools नहीं रखता — यह सब यहाँ दोबारा बनता है।
set -uo pipefail
H=/home/user; REPO=$H/fab; URL=https://github.com/deepsilence10161-source/Fast-and-advanced-browser-.git
[ -d "$REPO/.git" ] || git clone -q "$URL" "$REPO"
source "$REPO/tools/secret-guard/lib.sh"
sg_heal || { echo "bootstrap: secret-guard heal विफल"; exit 1; }
"$REPO/tools/secret-guard/gitx" -C "$REPO" fetch -q origin && git -C "$REPO" status -sb | head -1
bash "$REPO/tools/secret-guard/audit.sh" && echo "bootstrap OK"
