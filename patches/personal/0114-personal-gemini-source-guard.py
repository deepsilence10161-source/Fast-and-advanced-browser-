#!/usr/bin/env python3
"""Refuse source drift before the opt-in Gemini chat patch (0114) writes anything.

Runs AFTER the ordinary series and personal 0100-0113 on a restored Chromium 158.0.8127.42 tree.
Pinned hashes are the file state AFTER the earlier personal patches (chrome_java_sources.gni after 0105 and 0112). New outputs must be absent.
Source integrity only; it says nothing about Gemini chat behaviour on a device. No file is written.
"""
from pathlib import Path
import hashlib
import os
import sys

EXPECTED = {
    "chrome/android/chrome_java_sources.gni": "7ec23ed82428d67be5f4e638de1c834c43b9db715296ece534acfc63c261f027",
    "chrome/android/java/res/xml/main_preferences.xml": "c3e702fca7c33631d95a8e95fbb9c7ef5df5470099bbc49cc8b93e87bef12989",
    "chrome/android/java/src/org/chromium/chrome/browser/settings/MainSettings.java": "2f5579a222eced9a8323116aa9c7eb8be7911f4fdb54f93901ea14f2264f7595",
    "chrome/browser/browsing_data/android/BUILD.gn": "beca93ecfbe568ecb7d361e7550b3bb1b95c1c548ab6fedc8a1f250593608b66",
    "chrome/browser/browsing_data/android/java/src/org/chromium/chrome/browser/browsing_data/BrowsingDataBridge.java": "b49a1cbb2096d8ef7b01d24e8ad308ef26670d0f59553170c429204d0439b025"
}
NEW_PATHS = ('chrome/android/java/src/org/chromium/chrome/browser/swiftra/gemini/SwiftraGemini.java', 'chrome/browser/browsing_data/android/java/src/org/chromium/chrome/browser/browsing_data/SwiftraKeepSignin.java')


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
        print("Usage: 0114-personal-gemini-source-guard.py <src>", file=sys.stderr)
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
