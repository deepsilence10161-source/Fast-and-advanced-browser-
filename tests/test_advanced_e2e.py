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
    assert A.hfm_verdict(err, 0, "support a secure connection") == "warning_dialog"
    assert A.hfm_verdict({"title": A.HTTP_MARKER, "text": "", "ids": []}, 2, "x") == "http_loaded_silently"


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


def _fp(dev, mx, h, frame="f1", wh="w1", audio="1.0", flags=True):
    c = {"dev": dev, "max": mx, "hash": h, "url_hash": "u" + h, "reread_same": flags, "strip_same": flags,
         "subrect_same": flags, "url_same": flags}
    return {"me": {"canvas": c, "webgl": {"available": True, "dev": dev, "max": mx, "hash": wh, "reread_same": True},
                   "audio": {"sum": audio}}, "frame": frame}


def test_fp_verdict():
    assert A.fp_verdict(None, None)[0] == "no_result"
    assert A.fp_verdict(_fp(0, 0, "x"), _fp(0, 0, "x"))[0] == "no_shield"
    ok = A.fp_verdict(_fp(40, 1, "a", "fa", "wa", "1.1"), _fp(37, 1, "b", "fb", "wb", "1.2"))
    assert ok == ("shielded", [])
    v, why = A.fp_verdict(_fp(40, 1, "a", "same", "wa", "1.1"), _fp(37, 1, "b", "same", "wb", "1.2"))
    assert v == "partial" and any("linkable" in w for w in why)
    v, why = A.fp_verdict(_fp(40, 3, "a"), _fp(37, 1, "b", "fb", "wb", "2"))
    assert v == "partial" and any("max=3" in w for w in why)
    v, why = A.fp_verdict(_fp(40, 1, "a", flags=False), _fp(37, 1, "b", "fb", "wb", "2"))
    assert v == "partial" and any("strip_same" in w for w in why)
