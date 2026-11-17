#!/bin/bash
# Usage: build_clip_helper.sh <out.apk>   Builds the CI-only clipboard helper APK (javac + d8 + aapt2 + apksigner).
set -euo pipefail
OUT=${1:?out apk}
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/usr/local/lib/android/sdk}}
BT=$(ls -d "$SDK"/build-tools/*/ | sort -V | tail -1); AJ=$(ls -d "$SDK"/platforms/android-*/android.jar | sort -V | tail -1)
W=$(mktemp -d); mkdir -p "$W/cls"
javac -nowarn -Xlint:none -source 8 -target 8 -cp "$AJ" -d "$W/cls" tools/clip_helper/src/com/swiftra/cliphelper/Main.java 2>&1 | grep -v "^Note:\|warning" || true
"$BT/d8" --min-api 29 --lib "$AJ" --output "$W" $(find "$W/cls" -name '*.class')
"$BT/aapt2" link -o "$W/base.apk" -I "$AJ" --manifest tools/clip_helper/AndroidManifest.xml --min-sdk-version 29 --target-sdk-version 34
(cd "$W" && zip -q -j base.apk classes.dex)
"$BT/zipalign" -f 4 "$W/base.apk" "$W/aligned.apk"
keytool -genkeypair -keystore "$W/k.jks" -storepass ciclip00 -keypass ciclip00 -alias k -keyalg RSA -keysize 2048 -validity 3 -dname "CN=ci-cliphelper" >/dev/null 2>&1
"$BT/apksigner" sign --ks "$W/k.jks" --ks-pass pass:ciclip00 --key-pass pass:ciclip00 --out "$OUT" "$W/aligned.apk"
"$BT/apksigner" verify "$OUT" && echo "built $OUT $(stat -c %s "$OUT") bytes"
