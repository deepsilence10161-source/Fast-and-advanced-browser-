#!/usr/bin/env python3
"""Swiftra Ad & Tracker Blocker: bundled ruleset into the Chromium source tree (transform, see patches.py).

Runs after 0012-swiftra-adblock.patch:
  1. adblock/swiftra-ruleset.pb.gz (repo) -> src/chrome/browser/resources/swiftra/adblock_ruleset.pb
     (unindexed subresource_filter ruleset; grit includes it gzip-compressed as IDR_SWIFTRA_ADBLOCK_RULESET).
  2. The placeholder @SWIFTRA_ADBLOCK_VERSION@ in subresource_filter_features.cc becomes
     "swiftra.<sha256[:16] of the ruleset>", so a new ruleset always gets a new content version
     (RulesetService re-indexes only when the version changes).
The ruleset's SHA-256 is pinned below: patches.py hashes this script, not the ruleset, so changing the ruleset
must change this file (and therefore the patch hash) -- a mismatch is an error, never a silent build.
Regenerate: tools/adblock/convert.py (see adblock/README.md), then update EXPECTED_SHA256.
"""
import gzip
import hashlib
import os
import sys

EXPECTED_SHA256 = "bbc65e3afc380c8e3d6602ec4eb953990f7d8ff34943f99ade165ef4c7cf8f8e"
PLACEHOLDER = "@SWIFTRA_ADBLOCK_VERSION@"
FEATURES = "components/subresource_filter/core/browser/subresource_filter_features.cc"
DEST = "chrome/browser/resources/swiftra/adblock_ruleset.pb"
README = """Name: Swiftra Ad & Tracker Blocker lists (EasyList, EasyPrivacy, AdAway hosts)
Short Name: swiftra_adblock
URL: https://easylist.to/
Version: EasyList 202610181227, EasyPrivacy 202610181225, AdAway hosts 2026-10-18
License: CC-BY-SA-3.0, CC-BY-3.0
License File: LICENSE
Security Critical: no
Shipped: yes

Description:
Network filtering rules converted to the Chromium subresource_filter ruleset format and bundled in Swiftra.
The converted ruleset is published under CC BY-SA 3.0 in the Swiftra repository (adblock/).
"""
LICENSE = """Swiftra Ad & Tracker Blocker lists

EasyList and EasyPrivacy
  Copyright: The EasyList authors (https://easylist.to/)
  Licence: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)
           https://creativecommons.org/licenses/by-sa/3.0/ (dual licensed with GPLv3,
           https://easylist.to/pages/licence.html; used here under CC BY-SA 3.0)
  Changes: element-hiding rules removed; network rules converted to the Chromium
           subresource_filter format. The converted ruleset is distributed under CC BY-SA 3.0.

AdAway default hosts file
  Copyright: The AdAway authors (https://adaway.org/)
  Licence: Creative Commons Attribution 3.0 Unported (CC BY 3.0)
           https://creativecommons.org/licenses/by/3.0/
  Changes: host entries converted to third-party blocking rules.
"""


def main():
    src = sys.argv[1]
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data = gzip.open(os.path.join(repo, "adblock", "swiftra-ruleset.pb.gz"), "rb").read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        sys.exit(f"ruleset sha256 {digest} != pinned {EXPECTED_SHA256}")
    dest = os.path.join(src, DEST)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    print(f"TOUCHED {DEST}")

    # Attribution in the shipped "Open source licenses" page (chrome://credits, generated because args.gn sets
    # generate_about_credits = true): tools/licenses/licenses.py scans every third_party/* dir with a README.chromium.
    tp = os.path.join(src, "third_party", "swiftra_adblock")
    os.makedirs(tp, exist_ok=True)
    for name, text in (("README.chromium", README), ("LICENSE", LICENSE)):
        with open(os.path.join(tp, name), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"TOUCHED third_party/swiftra_adblock/{name}")

    path = os.path.join(src, FEATURES)
    text = open(path, encoding="utf-8").read()
    if text.count(PLACEHOLDER) != 1:
        sys.exit(f"{FEATURES}: expected exactly one {PLACEHOLDER} (is 0012 applied?)")
    open(path, "w", encoding="utf-8").write(text.replace(PLACEHOLDER, "swiftra." + digest[:16]))
    print(f"TOUCHED {FEATURES}")


if __name__ == "__main__":
    main()
