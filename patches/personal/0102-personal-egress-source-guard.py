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
    "chrome/android/java/src/org/chromium/chrome/browser/ChromeBaseAppCompatActivity.java": "115b949478561bfecc2230d8f26a5bfd4d184b3f18742954055c046d32f0d778",
    "chrome/android/java/src/org/chromium/chrome/browser/download/DownloadManagerService.java": "62a2e6dcd1e616a3f6a6b4dfd58bb9127243fb99fee4643d1f4ea5b52637b76a",
    "chrome/android/java/src/org/chromium/chrome/browser/download/DownloadUtils.java": "00b59e565307a1f653c1a5d523599c05d145969250b74063ab734bae93b566a5",
    "chrome/android/java/src/org/chromium/chrome/browser/incognito/IncognitoSnapshotController.java": "da31a5a84fe4a967c3af1e21f287711faba4fcbb33e7e1a654143b2c11c8ec90",
    "chrome/browser/download/BUILD.gn": "736c12bd19b95148de3e5d69e1d1820e363229956a5ad1f27b5021acd584d4d8",
    "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/DownloadDirectoryProvider.java": "cf16d9c71134b414107ca8d2e74da365a250e948f528bb4d03cc82c17e58137d",
    "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/DownloadManagerBridge.java": "fac93ed27637bc1f28f749bb45b0ac63e30f2cad9c030b99b35ba5472a74d252",
    "chrome/browser/download/download_prefs.cc": "b7edd58cb7df3342302fe4eb2a72be0dc9dd636e074fb65e97e8926de8cd5e9e",
    "chrome/browser/download/download_target_determiner.cc": "20c460af6833a7c0a2e3ed1f09ae8999681840542ab915dbe75b395de1fdd71c",
    "components/browser_ui/share/android/java/src/org/chromium/components/browser_ui/share/ShareHelper.java": "2bb156b1d191e14c158a1c56858c821d10ef4ea41a71a93cddacc204b72b3483",
    "components/download/internal/common/android/java/src/org/chromium/components/download/DownloadCollectionBridge.java": "d507bf06e0b19f70661207e12353ff09f0d2046ba60e49ca181f1f0e65bdbe97",
    "components/external_intents/android/java/src/org/chromium/components/external_intents/ExternalNavigationHandler.java": "508639af0abf800f1fd3ffb26c307b44413df9461eeba75b61cb6b68087502b9",
    "ui/android/BUILD.gn": "daf798e009d30de101d57400346b3a723e8172c5aea56a952f7136bf0d5969da",
    "ui/android/java/src/org/chromium/ui/base/Clipboard.java": "37a6dd4f1a3470be9a671f99566e74881759ab1d920baecda3680417c2b464c0"
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
