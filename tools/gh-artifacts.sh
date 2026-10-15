#!/bin/bash
# Usage: gh-artifacts.sh <run-id> <dest-dir>   — run के सभी artifacts डाउनलोड करके unzip करता है
set -e; RUN=$1; DEST=$2; G=/home/user/.secrets/gh.sh; R=/repos/deepsilence10161-source/Fast-and-advanced-browser-
mkdir -p "$DEST"
$G "$R/actions/runs/$RUN/artifacts?per_page=100" | python3 -c "import sys,json;[print(a['id'],a['name']) for a in json.load(sys.stdin)['artifacts'] if not a['expired']]" |
while read id name; do
  rm -rf "$DEST/$name"; mkdir -p "$DEST/$name"
  T=$(cat /home/user/.secrets/gh_token)
  # artifact zip: GitHub redirect देता है; token केवल curl config (stdin) में
  printf 'header = "Authorization: Bearer %s"\n' "$T" | curl -K - -sSL -o "$DEST/$name.zip" "https://api.github.com$R/actions/artifacts/$id/zip"
  unzip -oq "$DEST/$name.zip" -d "$DEST/$name" && rm "$DEST/$name.zip"; echo "got $name"
done
