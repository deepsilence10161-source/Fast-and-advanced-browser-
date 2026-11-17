#!/usr/bin/env python3
"""Refuse source drift before the opt-in Face Guard (presence mode) patch writes anything.

Runs AFTER the ordinary series and personal 0100-0103 on a restored Chromium 155.0.8059.80 tree.
The pinned files are not modified by any earlier patch. New outputs must be absent.
Source integrity only; it says nothing about Face Guard behaviour on a device. No file is written.
"""
from pathlib import Path
import hashlib
import os
import sys

EXPECTED = {
    "chrome/android/chrome_java_sources.gni": "0a377b23450f37279d289220a50d1cbfa5ccd6872e54743ca52ff0fa90ab5720",
    "chrome/android/java/res/xml/privacy_preferences.xml": "d926df40914535cd4dd2dc6de0e4f3be82211f5162c7f408825131988660ae3f",
    "chrome/android/java/src/org/chromium/chrome/browser/ChromeTabbedActivity.java": "90b33b6cdfc4d44f4d126d5fe97ca01646ddbe08243525045ad65b75672ba28a",
    "chrome/android/java/src/org/chromium/chrome/browser/privacy/settings/PrivacySettings.java": "0f830e87ad3ebfb2d927c15f40b47bcdcae34e50144b3ad7e62d36a5d0c83bff",
    "chrome/browser/tab_ui/android/BUILD.gn": "f955bd6860c08c8b5b9e9e61be680edc4c9885675b04a91d021776522ad90ba7",
    "chrome/browser/tab_ui/android/java/src/org/chromium/chrome/browser/tab_ui/TabContentManager.java": "db7cec3783bd94f633af3be7262d3fb69dc4c5fee3972e4d32f2c3401616d649"
}
NEW_PATHS = ('chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/FaceCameraSource.java', 'chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/FaceGrayConverter.java', 'chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/FaceGuardAuth.java', 'chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/FaceGuardChromeBridge.java', 'chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/FaceGuardController.java', 'chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/FaceGuardOverlay.java', 'chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/FaceGuardPolicy.java', 'chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/FaceGuardSettings.java', 'chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/PresenceFaceAnalyzer.java', 'chrome/browser/tab_ui/android/java/src/org/chromium/chrome/browser/tab_ui/FaceGuardLockState.java')


def safe_path(root: Path, relative: str) -> Path:
    path = root / relative
    if any(item.is_symlink() for item in (path, *path.parents) if item != root.parent):
        raise ValueError("source_symlink_refused")
    if not path.resolve().is_relative_to(root):
        raise ValueError("source_path_escape")
    return path


def check(src: Path) -> None:
    if src.is_symlink() or not src.is_dir():
        raise ValueError("source_root_invalid")
    root = src.resolve(strict=True)
    for relative, expected in EXPECTED.items():
        path = safe_path(root, relative)
        if not path.is_file():
            raise ValueError("source_input_missing:" + relative)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("source_hash_mismatch:" + relative)
    for relative in NEW_PATHS:
        if os.path.lexists(safe_path(root, relative)):
            raise ValueError("new_source_output_already_exists:" + relative)


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: 0104-face-guard-source-guard.py <src>", file=sys.stderr)
        return 2
    try:
        check(Path(args[0]))
    except (OSError, ValueError) as exc:
        print("[personal-source-guard] REFUSED: " + (
            str(exc) if isinstance(exc, ValueError) else "source_io_error"), file=sys.stderr)
        return 1
    print("[personal-source-guard] pinned source hashes match; runtime containment NOT CERTIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
