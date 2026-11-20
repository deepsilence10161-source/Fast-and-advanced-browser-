#!/usr/bin/env python3
"""Refuse source drift before the opt-in egress/storage native patch writes anything.

Runs AFTER the ordinary Swiftra series, on a pristine restored Chromium tree.
These egress/storage source files are not modified by the current ordinary series. New outputs
must be absent; applying twice or using another revision is an error. This is
source integrity only, not privacy/device acceptance. No source file is written.
"""
from pathlib import Path
import hashlib
import os
import sys

EXPECTED = {
    "base/android/java/src/org/chromium/base/PathUtils.java": "740605db4b36870f596ff242af4cf442e7da3cb09a259ad3e8d83acb5c269b17",
    "chrome/android/java/src/org/chromium/chrome/browser/ChromeBaseAppCompatActivity.java": "2d12cf386bf2b6318784afd61e8b7c49aa353acc628117b2cfb6542bc21c840f",
    "chrome/android/java/src/org/chromium/chrome/browser/download/DownloadManagerService.java": "62a2e6dcd1e616a3f6a6b4dfd58bb9127243fb99fee4643d1f4ea5b52637b76a",
    "chrome/android/java/src/org/chromium/chrome/browser/download/DownloadUtils.java": "f0e0204c16af4a3d99c895e81b892873895c9404ccb76d1ecc1fc73af463ccf6",
    "chrome/android/java/src/org/chromium/chrome/browser/incognito/IncognitoSnapshotController.java": "da31a5a84fe4a967c3af1e21f287711faba4fcbb33e7e1a654143b2c11c8ec90",
    "chrome/browser/download/BUILD.gn": "579c5696c828d343685b555939cee8564f791858ac0d884078e968f972aab5e5",
    "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/DownloadDirectoryProvider.java": "cf16d9c71134b414107ca8d2e74da365a250e948f528bb4d03cc82c17e58137d",
    "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/DownloadManagerBridge.java": "fac93ed27637bc1f28f749bb45b0ac63e30f2cad9c030b99b35ba5472a74d252",
    "chrome/browser/download/download_prefs.cc": "2e7bb246fa9975ee464324a869c316805db0103d0c8fc654f7956e7dc42a16e9",
    "chrome/browser/download/download_target_determiner.cc": "64194f3095cef3303501c96afecf4f92a116559f1199c509d55f487841ebe814",
    "components/browser_ui/share/android/java/src/org/chromium/components/browser_ui/share/ShareHelper.java": "64547fde9c95db0980761c1af43c26d09002c9b92321b3a8ca696f4a08778924",
    "components/download/internal/common/android/java/src/org/chromium/components/download/DownloadCollectionBridge.java": "d507bf06e0b19f70661207e12353ff09f0d2046ba60e49ca181f1f0e65bdbe97",
    "components/external_intents/android/java/src/org/chromium/components/external_intents/ExternalNavigationHandler.java": "391083b03b6cadf4868a29d087cb1d5e0995458f0fbcbec96bbf8cf7bf75fe44",
    "ui/android/BUILD.gn": "85b7f2d86b4c8031b260a522e9b3591efeef2e3da16b61c4bef4356e97eface2",
    "ui/android/java/src/org/chromium/ui/base/Clipboard.java": "cb402a1c0460dddbf8818d3bc3c63c575d8868f08612d6c767b80c0d356e38dd"
}
NEW_PATHS = ('chrome/browser/download/browser_contained_download_path.h', 'ui/android/java/src/org/chromium/ui/base/BrowserContainedClipboard.java')


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
        print("Usage: 0102-personal-egress-source-guard.py <src>", file=sys.stderr)
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
