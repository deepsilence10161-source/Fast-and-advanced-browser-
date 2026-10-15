#!/bin/bash
# gitleaks v8.30.1 (linux x64) को ~/.cache में install करता है; official SHA-256 से मिलान, mismatch पर इनकार
set -euo pipefail
V=8.30.1; SHA=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
D=/home/user/.cache/gitleaks; mkdir -p "$D"
[ -x "$D/gitleaks" ] && "$D/gitleaks" version 2>/dev/null | grep -q "$V" && { echo "gitleaks $V पहले से मौजूद"; exit 0; }
T=$(mktemp); trap 'rm -f "$T"' EXIT
curl -sSL -o "$T" "https://github.com/gitleaks/gitleaks/releases/download/v$V/gitleaks_${V}_linux_x64.tar.gz"
echo "$SHA  $T" | sha256sum -c --quiet - || { echo "SHA-256 mismatch: install रद्द" >&2; exit 1; }
tar xzf "$T" -C "$D" gitleaks && chmod 755 "$D/gitleaks" && "$D/gitleaks" version
