#!/bin/bash
# Diagnostic only: how can the SYSTEM clipboard be read from adb on this image? (no app involved)
set -u
mkdir -p out/clip; L=out/clip/diag.txt; : > "$L"
timeout 180 adb wait-for-device
{
echo "sdk=$(adb shell getprop ro.build.version.sdk | tr -d '\r') release=$(adb shell getprop ro.build.version.release | tr -d '\r')"
echo "--- cmd clipboard help"; adb shell cmd clipboard help 2>&1 | head -30
echo "--- cmd clipboard set-text canary_one"; adb shell cmd clipboard set-text canary_one 2>&1 | head -5
echo "--- cmd clipboard get-text"; adb shell cmd clipboard get-text 2>&1 | head -5
echo "--- dumpsys clipboard (head)"; adb shell dumpsys clipboard 2>&1 | head -40
echo "--- service call clipboard 2 (getPrimaryClip raw probe)"; adb shell service call clipboard 2 s16 com.android.shell i32 0 i32 0 2>&1 | head -8
} 2>&1 | tee -a "$L"
