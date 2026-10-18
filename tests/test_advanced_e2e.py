import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "ci"))
import advanced_e2e as A  # noqa: E402


def test_hfm_verdict():
    assert A.hfm_verdict(None) == "no_page"
    assert A.hfm_verdict({"title": A.HTTP_MARKER, "text": A.HTTP_MARKER, "ids": []}) == "http_loaded_silently"
    assert A.hfm_verdict({"title": "Privacy error", "text": "Connection is not secure", "ids": []}) == "interstitial"
    assert A.hfm_verdict({"title": "", "text": "", "ids": ["primary-button"]}) == "interstitial"
    assert A.hfm_verdict({"title": "x", "text": "y", "ids": []}) == "unknown"
    err = {"title": "", "text": "", "ids": [], "href": "chrome-error://chromewebdata/"}
    assert A.hfm_verdict(err, 0) == "blocked_no_http"
    assert A.hfm_verdict(err, 1) == "http_loaded_silently"
    assert A.hfm_verdict(err, None) == "unknown"


def test_tpc_verdict():
    done = lambda fp, frames: {"title": "3PC:done", "r": json.dumps({"fp": fp, "frame": frames})}  # noqa: E731
    assert A.tpc_verdict(None) == "no_result"
    assert A.tpc_verdict({"title": "3PC:pending"}) == "no_result"
    assert A.tpc_verdict(done("fp=1", ["", ""])) == "third_party_blocked"
    assert A.tpc_verdict(done("fp=1", ["s3p=1", "s3p=1"])) == "third_party_allowed"
    assert A.tpc_verdict(done("", ["", ""])) == "first_party_cookie_broken"


def test_rules_cover_all_hosts():
    for h in (A.HTTP_HOST, A.TOP_HOST, A.THIRD_HOST):
        assert f"MAP {h} 127.0.0.1:" in A.RULES
    assert A.THIRD_HOST.split(".")[-2:] != A.TOP_HOST.split(".")[-2:]   # really cross-site
