#!/usr/bin/env python3
"""Refuse source drift before the opt-in omnibox clipboard patch writes anything.

Runs AFTER the ordinary series and personal 0100-0107 on a restored Chromium 158.0.8127.42 tree.
The pinned files are not modified by any earlier patch. New outputs must be absent.
Source integrity only; it says nothing about Face Guard behaviour on a device. No file is written.
"""
from pathlib import Path
import hashlib
import os
import sys

EXPECTED = {
    "chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/UrlBar.java": "a3c720cd21ccce6735675176a59dd17573ad29e0cc7337c1d3843666c2081766",
    "chrome/android/java/src/org/chromium/chrome/browser/findinpage/FindToolbar.java": "ca61610baae354ac63bb64670f7a9dc9562703cb2ae78020fce3690db152fd57",
    "components/browser_ui/widget/android/java/src/org/chromium/components/browser_ui/widget/text/AlertDialogEditText.java": "a473469c8ffd3531ca7902b85f2d45a2831853e33488160c69c07fce62710688",
    "components/browser_ui/widget/android/java/res/layout/radio_button_with_edit_text.xml": "dff5a093c484fef4fdd40fba7716e7409951477b999b9a0ccbceedfde84b8667",
}
NEW_PATHS = ()


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
        print("Usage: 0108-personal-omnibox-source-guard.py <src>", file=sys.stderr)
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
