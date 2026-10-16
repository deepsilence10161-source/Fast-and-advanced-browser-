#!/bin/bash
# Usage: gh.sh <api-path|url> [curl args...]
# Token curl को config के रूप में stdin (-K -) से जाता है, argv में नहीं; केवल GitHub API host; हर output redact।
umask 077; V=/home/user/.secrets; T=$V/gh_token
[ -f "$T" ] && [ ! -L "$T" ] || { echo "[gh.sh] token फ़ाइल नहीं/अमान्य" >&2; exit 1; }
chmod 700 "$V"; chmod 600 "$T"
P="$1"; shift
case "$P" in http*) U="$P";; *) U="https://api.github.com$P";; esac
case "$U" in https://api.github.com/*|https://uploads.github.com/*) ;; *) echo "[gh.sh] केवल GitHub API host को token भेजा जाता है" >&2; exit 1;; esac
printf 'header = "Authorization: Bearer %s"\nheader = "Accept: application/vnd.github+json"\nheader = "X-GitHub-Api-Version: 2022-11-28"\n' "$(cat "$T")" \
 | curl -K - -sS "$@" "$U" | python3 /home/user/fab/tools/secret-guard/redact.py
