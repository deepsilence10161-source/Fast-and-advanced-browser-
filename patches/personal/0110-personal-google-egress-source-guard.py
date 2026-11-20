#!/usr/bin/env python3
"""Refuse source drift before the opt-in Google-egress patch (AI Mode kill switch, network-time query off, no popular-sites/doodle/last_n archive/search-suggest defaults) writes anything.

Runs AFTER the ordinary series and personal 0100-0109 on a restored Chromium 158.0.8127.42 tree.
The pinned files are not modified by any earlier patch. New outputs must be absent.
Source integrity only; it says nothing about Face Guard behaviour on a device. No file is written.
"""
from pathlib import Path
import hashlib
import os
import sys

EXPECTED = {
    "components/omnibox/browser/aim_eligibility_service_features.cc": "9f4d3dc7848870c2665802d1f42023ac11a6696333d76a332b66a17c6b945278",
    "components/network_time/network_time_tracker.cc": "1ca25c3c74bceb730bce1958dfb5079997a51ac06017d85b5a806903a0f1eb10",
    "components/ntp_tiles/popular_sites_impl.cc": "41f987b94de5b1ffafaec0849ba983604dc75618fd74fd38fa5d79a539f3c965",
    "components/ntp_tiles/features.cc": "2e33fd5cd1b672f069bcb742be87e85a271da114b73f4a20e1df3a5d4b4e3821",
    "components/search_provider_logos/logo_service_impl.cc": "3963796c759086b1a605d8171055816ce80e7b2cd644c121b0f8af8f0ef23cae",
    "chrome/browser/offline_pages/recent_tab_helper.cc": "ba87a275aec9d9030c3d62cbbab73d3642c902abde2c8e97b3041846be0ed6cb",
    "chrome/browser/profiles/profile.cc": "441939664eb65da76f3bb257d56420dc422337cc66b25829a95ac22b4c592685",
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
