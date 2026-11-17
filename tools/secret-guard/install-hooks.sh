#!/bin/bash
# Usage: install-hooks.sh — hooks को core.hooksPath से सक्रिय करता है (lib.sh::sg_repo_fix)। gitx यह हर बार अपने-आप करता है।
source "$(dirname "$(readlink -f "$0")")/lib.sh" && sg_repo_fix && echo "hooks installed (core.hooksPath=$SG_DIR/hooks)"
