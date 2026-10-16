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

# cert_digests <apksigner-verify-output-file> → stdout: अलग-अलग signer cert SHA-256 (lowercase, comma से जुड़े)
# दोनों formats: पुराना "Signer #1 certificate SHA-256 digest: …" (build-tools ≤36) और
# नया "V2 Signer: certificate SHA-256 digest: …" / "V3 Signer: …" (build-tools 37, Chromium 155 का)।
# एक से ज़्यादा अलग digest = "a,b" (caller के अपेक्षित मान से कभी मेल नहीं खाएगा -> FAIL)।
cert_digests() {
  sed -nE 's/^(Signer #[0-9]+|V[0-9.]+ Signer( #[0-9]+)?):? certificate SHA-256 digest: *([0-9a-fA-F]{64}).*/\3/p' "$1" 2>/dev/null \
    | tr 'A-F' 'a-f' | sort -u | paste -sd, - || true
}
