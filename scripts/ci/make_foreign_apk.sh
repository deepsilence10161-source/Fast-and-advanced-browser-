#!/bin/bash
# वही APK, पर एक throwaway (हर run में नई, फिर नष्ट) key से re-signed — device_checks.sh का negative test:
# Android को इसे update के रूप में मना करना चाहिए (INSTALL_FAILED_UPDATE_INCOMPATIBLE)।
# apksigner: Google का build-tools r37 zip, Google repository manifest के SHA-1 से सत्यापित (Java चाहिए)।
# Usage: make_foreign_apk.sh <in.apk> <out.apk>
set -euo pipefail
IN=$1; OUTAPK=$2
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
ZIP=build-tools_r37_linux.zip; SHA1=70954e99f4c3d9d46ee70fa32624672fe7cd6ebe   # repository2-3.xml, 16-10-2026
curl -sSfL -o "$W/$ZIP" "https://dl.google.com/android/repository/$ZIP"
echo "$SHA1  $W/$ZIP" | sha1sum -c --quiet
unzip -q -o "$W/$ZIP" '*/lib/apksigner.jar' -d "$W/bt"; JAR=$(find "$W/bt" -name apksigner.jar | head -1)
P=$(head -c 24 /dev/urandom | base64 | tr -dc A-Za-z0-9); printf '%s' "$P" > "$W/p"; cp "$W/p" "$W/kp"
keytool -genkeypair -keystore "$W/t.p12" -storetype PKCS12 -alias t -keyalg RSA -keysize 2048 -validity 2 \
  -dname "CN=Throwaway Test Key" -storepass:file "$W/p" -keypass:file "$W/p" >/dev/null 2>&1
java -jar "$JAR" sign --ks "$W/t.p12" --ks-type PKCS12 --ks-key-alias t --ks-pass "file:$W/p" --key-pass "file:$W/kp" \
  --alignment-preserved true --v4-signing-enabled false --out "$OUTAPK" "$IN"
java -jar "$JAR" verify --print-certs -v "$OUTAPK" | grep -E "certificate DN|certificate SHA-256" | head -2
