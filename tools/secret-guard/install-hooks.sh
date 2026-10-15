#!/bin/bash
# Usage: install-hooks.sh <repo-path>  — hooks को repo के .git/hooks में जोड़ता है
set -e; r=$1; d=$(git -C "$r" rev-parse --git-path hooks); case "$d" in /*) ;; *) d="$r/$d";; esac
git -C "$r" config --unset core.hooksPath 2>/dev/null || true
for h in pre-commit commit-msg pre-push; do ln -sf /home/user/tools/secret-guard/hooks/$h "$d/$h"; done
echo "hooks installed: $r"
