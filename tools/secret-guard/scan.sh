#!/bin/bash
# Usage:
#   scan.sh dir <path>                  — फ़ाइलें (git history नहीं)
#   scan.sh repo <repo-path>            — पूरी git history (सभी branches)
#   scan.sh staged <repo>               — केवल staged बदलाव (pre-commit)
#   scan.sh range <repo> <rev-range>    — push होने वाले commits (pre-push)
# Exit: 0 = साफ़, 1 = secret मिला, 2 = स्कैनर त्रुटि (fail-closed). Secret का मान कभी print नहीं होता।
set -u
SGD=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
GL=/home/user/.cache/gitleaks/gitleaks
TF=/home/user/.secrets/gh_token
LEAK=3
mode=${1:-}; tgt=${2:-}; found=0; err=0
[ -x "$GL" ] || { echo "[त्रुटि] gitleaks नहीं मिला: $GL (चलाएँ: bash $SGD/../install-gitleaks.sh)" >&2; exit 2; }
exact_in_stdin() { # stdin में असली token हो तो exit 1
  [ -r "$TF" ] || return 0
  python3 -c '
import sys
t=open(sys.argv[1]).read().strip()
sys.exit(1 if t and t.encode() in sys.stdin.buffer.read() else 0)' "$TF"
}
run_gl() { # gitleaks चलाओ; JSON रिपोर्ट से केवल rule/file/line दिखाओ (मान कभी नहीं)
  local o rc rep; rep=$(mktemp)
  o=$("$GL" "$@" --config $SGD/gitleaks.toml --redact --no-banner --log-level error \
        --report-format json --report-path "$rep" --exit-code $LEAK 2>&1); rc=$?
  if [ $rc = $LEAK ]; then echo "[gitleaks] संभावित secret मिला:"
    python3 -c 'import json,sys;[print("  rule=%s file=%s line=%s commit=%s"%(f["RuleID"],f["File"],f["StartLine"],(f.get("Commit") or "-")[:10])) for f in json.load(open(sys.argv[1]))]' "$rep"; found=1
  elif [ $rc != 0 ]; then echo "[त्रुटि] gitleaks विफल (exit $rc):"; printf '%s\n' "$o" | $SGD/redact.py | tail -3; err=1; fi
  rm -f "$rep"
}
case "$mode" in
  dir)
    if [ -r "$TF" ]; then
      hits=$(grep -rIlF --exclude-dir=.secrets --exclude-dir=node_modules --exclude-dir=.git -f "$TF" "$tgt" 2>/dev/null)
      [ -n "$hits" ] && { echo "[असली-TOKEN] इन फ़ाइलों में मिला:"; echo "$hits" | sed 's/^/  /'; found=1; }
    fi
    run_gl dir "$tgt" --max-target-megabytes 50 ;;
  repo)
    git -C "$tgt" log --all -p --no-color 2>/dev/null | exact_in_stdin || { echo "[असली-TOKEN] git history में मिला"; found=1; }
    run_gl git "$tgt" --log-opts="--all" ;;
  staged)
    git -C "$tgt" diff --cached --no-color | exact_in_stdin || { echo "[असली-TOKEN] staged बदलावों में मिला"; found=1; }
    run_gl git "$tgt" --staged --pre-commit ;;
  range)
    rng=${3:?rev-range चाहिए}
    { git -C "$tgt" log -p --no-color $rng; git -C "$tgt" log --format='%B' $rng; } | exact_in_stdin || { echo "[असली-TOKEN] push होने वाले commits में मिला"; found=1; }
    run_gl git "$tgt" --log-opts="$rng" ;;
  *) echo "अज्ञात mode: $mode" >&2; exit 2;;
esac
[ $found = 1 ] && exit 1
[ $err = 1 ] && exit 2
echo "SECRET-SCAN: साफ़ ($mode $tgt)"; exit 0
