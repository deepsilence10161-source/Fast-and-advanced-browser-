#!/bin/bash
# git credential helper: token केवल https://github.com के लिए; store/erase पर कुछ नहीं लिखता।
umask 077; V=/home/user/.secrets; T=$V/gh_token
[ "$1" = get ] || exit 0
proto=""; host=""
while IFS= read -r l; do [ -z "$l" ] && break; case "$l" in protocol=*) proto=${l#protocol=};; host=*) host=${l#host=};; esac; done
[ "$proto" = https ] && [ "$host" = github.com ] || exit 0
[ -f "$T" ] && [ ! -L "$T" ] || exit 0
chmod 700 "$V"; chmod 600 "$T"
echo "username=x-access-token"; echo "password=$(cat "$T")"
