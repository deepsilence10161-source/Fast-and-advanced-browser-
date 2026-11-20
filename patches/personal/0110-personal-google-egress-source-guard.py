#!/usr/bin/env python3
"""Refuse source drift before the opt-in Google-egress patch (AI Mode kill switch, network-time query off, no popular-sites/doodle/last_n archive/search-suggest defaults) writes anything.

Runs AFTER the ordinary series and personal 0100-0109 on a restored Chromium 155.0.8059.80 tree.
The pinned files are not modified by any earlier patch. New outputs must be absent.
Source integrity only; it says nothing about Face Guard behaviour on a device. No file is written.
"""
from pathlib import Path
import hashlib
import os
import sys

EXPECTED = {
    "components/omnibox/browser/aim_eligibility_service_features.cc": "9f4d3dc7848870c2665802d1f42023ac11a6696333d76a332b66a17c6b945278",
    "components/network_time/network_time_tracker.cc": "216a2fc23756e4a4010144720c5c9d2cc728cd5d43f3b2c4bfee246ed189cb33",
    "components/ntp_tiles/popular_sites_impl.cc": "240bc08a2871e0a73565679b3b1357ad06a13aa5322c9e8b54c0f0955a537f42",
    "components/ntp_tiles/features.cc": "4bbf8e076b721b568568eabfc686a6474c3d813bcb8b3db4d55b25c1bdf3d971",
    "components/search_provider_logos/logo_service_impl.cc": "3963796c759086b1a605d8171055816ce80e7b2cd644c121b0f8af8f0ef23cae",
    "chrome/browser/offline_pages/recent_tab_helper.cc": "419da292c4ff999281044dc1c523923eda9545bfd4e60c5206e402763da2e239",
    "chrome/browser/profiles/profile.cc": "f8999e49c117b11bbf720397f284434f87fd8f431f9dae6353c501d2a699ad31",
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
        print("Usage: 0110-personal-google-egress-source-guard.py <src>", file=sys.stderr)
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
