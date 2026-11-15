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
    "chrome/android/BUILD.gn": "5b4fe0217f8f67fce9190eb002cb90dbc85cc77465b1bc80f9d553e159c77b54",
    "chrome/android/java/AndroidManifest.xml": "06c7dac54cdc5fc67e7ee6ae542ddf5cad7e1b598263563a205eccf2e217d68a",
    "chrome/browser/signin/services/android/java/src/org/chromium/chrome/browser/signin/services/SigninManagerImpl.java": "ed9fe948e2be17b6f9a0d7dd6515503cd397520517c4e1227dc5714c7b75f73a",
    "components/signin/public/android/BUILD.gn": "318035a3ef18d6cc802433bd69cae45a22a5ca6056699dee274c2a9aeb2c3a5d",
    "components/signin/public/android/java/src/org/chromium/components/signin/AccountManagerFacadeProvider.java": "d55d8a8e7760c69f8a74e96d7cc501d8cbfc7cfc76e4ffb35b4e011030bd8690",
    "content/public/android/java/src/org/chromium/content/browser/input/ImeAdapterImpl.java": "7d81c27d19922b828a7dce07bde0abc0192b651fceeffb7f35f061308212cc39",
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
