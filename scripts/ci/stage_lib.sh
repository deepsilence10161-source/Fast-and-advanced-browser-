#!/bin/bash
# chromium_stage.sh के छोटे, testable helpers। set -euo pipefail वाले caller में भी कभी non-zero नहीं लौटाते।

# count_remaining <ninja-binary> <out-dir> <target>  → stdout पर बचे edges की संख्या (कुछ नहीं बचा = 0)
# (सत्र 2 का bug: "ninja: no work to do." पर grep exit 1 → pipefail → set -e ने script रोक दी, APK upload नहीं हुआ)
count_remaining() {
  local n
  n=$("$1" -C "$2" -n "$3" 2>/dev/null | python3 -c '
import re,sys
last=None
for line in sys.stdin:
    m=re.match(r"\[(\d+)/(\d+)\]",line)
    if m: last=m.group(2)
print(last or 0)') || n=0
  echo "${n:-0}"
}
