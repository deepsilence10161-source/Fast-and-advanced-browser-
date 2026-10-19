"""Licence compliance of everything third-party that Swiftra redistributes (the "zero copyright problems" gate)."""
import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


FEEDS = _load("patches/0019-swiftra-shield-feeds-credits.py", "feeds_credits")
ADBLOCK = _load("patches/0013-swiftra-adblock-ruleset.py", "adblock_ruleset")
REQUIRED = ("Name:", "URL:", "Version:", "License:", "License File: LICENSE", "Shipped: yes")


def test_0019_in_series_after_0013():
    series = [l.strip() for l in open(os.path.join(ROOT, "patches", "series")) if l.strip() and not l.startswith("#")]
    assert series.index("0019-swiftra-shield-feeds-credits.py") > series.index("0013-swiftra-adblock-ruleset.py")


def test_readme_chromium_fields():
    for mod in (FEEDS, ADBLOCK):
        for field in REQUIRED:
            assert field in mod.README, (mod.__name__, field)


def test_mit_notice_complete_for_phishing_database():
    lic = FEEDS.LICENSE
    for holder in ("Mitchell Krog", "Nissar Chababy", "Phishing.Database Contributors"):
        assert f"Copyright (c) 2018-2025 {holder}" in lic
    assert "The above copyright notice and this permission notice shall be included in all" in lic
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in lic
    assert "CC0-1.0" in lic and "TweetFeed" in lic


def test_every_shield_source_is_licence_clean_and_attributed():
    sys.path.insert(0, os.path.join(ROOT, "scripts", "shield"))
    import build_shield_db as b
    for s in b.SOURCES:
        assert s["licence"] in ("MIT", "CC0-1.0"), s["id"]
        repo = "Phishing.Database" if "Phishing" in s["url"] else "TweetFeed" if "tweetfeed" in s["url"] else None
        assert repo and repo in FEEDS.LICENSE, s["id"]
    # the NOTICE uploaded next to the list is the same text as the in-app credits entry
    assert b.feed_notice() == FEEDS.LICENSE


def test_0019_transform_writes_credits_dir(tmp_path):
    out = subprocess.run([sys.executable, os.path.join(ROOT, "patches", "0019-swiftra-shield-feeds-credits.py"),
                          str(tmp_path)], capture_output=True, text=True, check=True).stdout
    d = tmp_path / "third_party" / "swiftra_shield_feeds"
    assert (d / "README.chromium").read_text() == FEEDS.README and (d / "LICENSE").read_text() == FEEDS.LICENSE
    assert out.count("TOUCHED") == 2


def test_adblock_lists_attributed_with_share_alike():
    lic = ADBLOCK.LICENSE
    assert "CC BY-SA 3.0" in lic and "The EasyList authors" in lic and "AdAway" in lic and "CC BY 3.0" in lic
    srcs = sorted(os.listdir(os.path.join(ROOT, "adblock", "sources")))
    assert srcs == ["adaway-hosts.txt.gz", "easylist.txt.gz", "easyprivacy.txt.gz"]   # nothing unlisted bundled


def test_swiftra_patch_lines_ascii_only():
    """Lines Swiftra adds to Chromium source via .patch files are ASCII (0000 = upstream code, may carry upstream
    non-ASCII; .py transforms keep their own Hindi comments, which never reach the Chromium tree)."""
    bad = []
    for n in sorted(os.listdir(os.path.join(ROOT, "patches"))):
        if n.endswith(".patch") and n[:4].isdigit() and not n.startswith("0000"):
            for i, line in enumerate(open(os.path.join(ROOT, "patches", n), encoding="utf-8"), 1):
                if line.startswith("+") and not line.isascii():
                    bad.append(f"{n}:{i}")
    assert not bad, bad
