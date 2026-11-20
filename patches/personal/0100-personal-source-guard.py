#!/usr/bin/env python3
"""Refuse source drift before the opt-in personal native patch writes anything.

Runs AFTER the ordinary Swiftra series, on a pristine restored Chromium tree.
These six files are not modified by the current ordinary series. New outputs
must be absent; applying twice or using another revision is an error. This is
source integrity only, not privacy/device acceptance. No source file is written.
"""
from pathlib import Path
import hashlib
import os
import sys

EXPECTED = {
    "chrome/android/BUILD.gn": "f2721b2322b00da091676a5f08e9a0536a123bc7c80023f2b895a9d48478d578",
    "chrome/android/java/AndroidManifest.xml": "1f0738d12bbe01f6d131a352e6716899fde3aa7e76944a1c37d74ca5b6ba9c91",
    "chrome/browser/signin/services/android/java/src/org/chromium/chrome/browser/signin/services/SigninManagerImpl.java": "31ef03b781e20f8e1127a3cacf42f9f5a3450644244d9bf32893f7ac620e628c",
    "components/signin/public/android/BUILD.gn": "d842cd65f91a033a55432c32328c06e0446fbe8083269125bd7ed135eecc44cb",
    "components/signin/public/android/java/src/org/chromium/components/signin/AccountManagerFacadeProvider.java": "d55d8a8e7760c69f8a74e96d7cc501d8cbfc7cfc76e4ffb35b4e011030bd8690",
    "content/public/android/java/src/org/chromium/content/browser/input/ImeAdapterImpl.java": "87e6d87f5eb728e42596c744382bbe38ebcd39719a2d13705b372648265e80a5",
}
NEW_PATHS = (
    "components/signin/public/android/java/src/org/chromium/components/signin/BrowserContainedAccountManagerFacade.java",
    "chrome/android/java/res_base/xml/personal_no_data_transfer.xml",
)


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
        print("Usage: 0100-personal-source-guard.py <src>", file=sys.stderr)
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
