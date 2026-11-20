#!/bin/bash
# Real javac compile of all Face Guard Java against Android API 33 + the real androidx classes (not the tiny test stubs).
# Downloads the jars once into ~/aa (robolectric android-all 13 = Java 11 class files; the sandbox JDK is 11).
# Usage: tools/face_guard/compile_check.sh      -> prints OK or the javac errors
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
AA=${AA_DIR:-$HOME/aa}; mkdir -p "$AA"; cd "$AA"
get(){ [ -s "$2" ] || curl -fsSL -o "$2" "$1"; }
M=https://dl.google.com/android/maven2
get https://repo1.maven.org/maven2/org/robolectric/android-all/13-robolectric-9030017/android-all-13-robolectric-9030017.jar aa13.jar
aar(){ n=$(basename "$1" .aar); [ -s "x_$n/classes.jar" ] || { get "$M/$1" "$n.aar"; mkdir -p "x_$n"; unzip -oq "$n.aar" classes.jar -d "x_$n"; }; }
for a in androidx/preference/preference/1.2.1/preference-1.2.1.aar androidx/fragment/fragment/1.6.2/fragment-1.6.2.aar \
         androidx/appcompat/appcompat/1.6.1/appcompat-1.6.1.aar androidx/core/core/1.12.0/core-1.12.0.aar \
         androidx/recyclerview/recyclerview/1.3.2/recyclerview-1.3.2.aar androidx/lifecycle/lifecycle-viewmodel/2.6.2/lifecycle-viewmodel-2.6.2.aar \
         androidx/lifecycle/lifecycle-runtime/2.6.2/lifecycle-runtime-2.6.2.aar androidx/savedstate/savedstate/1.2.1/savedstate-1.2.1.aar \
         androidx/activity/activity/1.8.0/activity-1.8.0.aar; do aar "$a"; done
get $M/androidx/lifecycle/lifecycle-common/2.6.2/lifecycle-common-2.6.2.jar lifecycle-common.jar
get $M/androidx/annotation/annotation/1.7.1/annotation-1.7.1.jar annotation.jar
CP="$AA/aa13.jar:$AA/lifecycle-common.jar:$AA/annotation.jar:$(ls "$AA"/x_*/classes.jar | tr '\n' ':')"
STUBS=$(mktemp -d); cp -r "$HERE/test_stubs/org" "$STUBS/"      # only the Chromium-internal stubs; androidx is the real thing
OUT=$(mktemp -d)
cd "$HERE" && javac -nowarn -proc:none -cp "$CP" -sourcepath "$STUBS" -d "$OUT" $(find src src_tab_ui -name '*.java') && echo "face guard compile check OK"
