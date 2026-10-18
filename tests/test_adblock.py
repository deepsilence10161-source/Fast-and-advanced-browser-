import gzip
import hashlib
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools", "adblock"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
import convert as C  # noqa: E402
import advanced_e2e as A  # noqa: E402
import rules_pb2 as P  # noqa: E402


def test_parse_semantics_match_chromium_rule_parser():
    r = C.parse_line("||adnxs.com^")
    assert r.semantics == P.RULE_SEMANTICS_BLOCKLIST and r.anchor_left == P.ANCHOR_TYPE_SUBDOMAIN
    assert r.url_pattern == "adnxs.com^" and r.url_pattern_type == P.URL_PATTERN_TYPE_WILDCARDED
    assert r.element_types == C.DEFAULT_ELEMENTS and r.source_type == P.SOURCE_TYPE_ANY
    r = C.parse_line("||google-analytics.com^$script,third-party,xmlhttprequest")
    assert r.element_types == P.ELEMENT_TYPE_SCRIPT | P.ELEMENT_TYPE_XMLHTTPREQUEST
    assert r.source_type == P.SOURCE_TYPE_THIRD_PARTY
    r = C.parse_line("@@||example.com^$document")
    assert r.semantics == P.RULE_SEMANTICS_ALLOWLIST and r.activation_types == P.ACTIVATION_TYPE_DOCUMENT
    assert not r.element_types
    r = C.parse_line("/Ads/Banner.$image,domain=a.com|~b.a.com,~third-party")
    assert r.url_pattern == "/ads/banner." and r.url_pattern_type == P.URL_PATTERN_TYPE_SUBSTRING
    assert [(d.domain, d.exclude) for d in r.initiator_domains] == [("b.a.com", True), ("a.com", False)]
    assert r.source_type == P.SOURCE_TYPE_FIRST_PARTY
    r = C.parse_line("/X/y$match-case")
    assert r.url_pattern == "/X/y" and r.match_case
    assert C.parse_line("|https://ads.$~image").element_types == C.DEFAULT_ELEMENTS & ~P.ELEMENT_TYPE_IMAGE
    assert C.parse_line("*/pagead/*").url_pattern == "/pagead/"
    for comment in ("! comment", "[Adblock Plus 2.0]", "example.com##.ad", "##.banner", "a.com#@#.ad", "x.com#?#div"):
        assert C.parse_line(comment) is None


def test_unsupported_rules_are_skipped_never_guessed():
    for line in ("/ads[0-9]+/", "||a.com^$redirect=noop.js", "||a.com^$csp=script-src", "||a.com^$document",
                 "@ads", "$third-party", "||a.com^$important"):
        try:
            C.parse_line(line)
        except C.Skip:
            continue
        raise AssertionError(line)


def test_hosts_and_roundtrip(tmp_path):
    hosts = list(C.hosts_rules(["# c", "127.0.0.1 localhost", "0.0.0.0 ads.example.net # x", "127.0.0.1 bad_host",
                                "1.2.3.4 not.blocked"]))
    assert hosts == ["||ads.example.net^$third-party"]
    rules = [C.parse_line(x) for x in ("||a.com^", "@@||b.com^$document")] * 1500
    out = tmp_path / "r.pb"
    C.write_ruleset(rules, str(out), chunk=1000)
    back = C.read_ruleset(str(out))
    assert len(back) == 3000 and back[1].semantics == P.RULE_SEMANTICS_ALLOWLIST


def test_bundled_ruleset_is_pinned_and_contains_e2e_hosts():
    data = gzip.open(os.path.join(ROOT, "adblock", "swiftra-ruleset.pb.gz"), "rb").read()
    script = open(os.path.join(ROOT, "patches", "0013-swiftra-adblock-ruleset.py")).read()
    assert hashlib.sha256(data).hexdigest() in script
    series = [x.strip() for x in open(os.path.join(ROOT, "patches", "series")) if x.strip() and x[0] != "#"]
    assert series.index("0013-swiftra-adblock-ruleset.py") == series.index("0012-swiftra-adblock.patch") + 1
    patch = open(os.path.join(ROOT, "patches", "0012-swiftra-adblock.patch")).read()
    assert patch.count("@SWIFTRA_ADBLOCK_VERSION@") == 1 and "IDR_SWIFTRA_ADBLOCK_RULESET" in patch
    tmp = os.path.join(os.path.dirname(__file__), "_rs.pb")
    open(tmp, "wb").write(data)
    try:
        rules = C.read_ruleset(tmp)
    finally:
        os.remove(tmp)
    blocks = {(r.url_pattern, r.anchor_left) for r in rules if r.semantics == P.RULE_SEMANTICS_BLOCKLIST}
    for host in ("adnxs.com", "google-analytics.com", "scorecardresearch.com"):
        assert (host + "^", P.ANCHOR_TYPE_SUBDOMAIN) in blocks, host
    for h in A.AD_HOSTS:
        assert any(h.endswith(p[0][:-1]) for p in blocks if p[1] == P.ANCHOR_TYPE_SUBDOMAIN and p[0].endswith("^"))
    # controls must not be blocked by a host rule
    assert not any(re.fullmatch(r"(news\.)?example\.(com|org)\^", p[0]) for p in blocks)


def test_ad_verdict():
    done = {"title": "AD:done", "r": "{}"}
    ok = {h: 0 for h in A.AD_HOSTS}
    ok.update({A.AD_TOP + "/first.js": 1, A.AD_CONTROL: 1})
    assert A.ad_verdict(ok, done) == "blocked"
    assert A.ad_verdict(ok, None) == "no_result"
    assert A.ad_verdict(dict(ok, **{A.AD_CONTROL: 0}), done) == "controls_broken"
    assert A.ad_verdict(dict(ok, **{h: 1 for h in A.AD_HOSTS}), done) == "no_blocker"
    assert A.ad_verdict(dict(ok, **{A.AD_HOSTS[0]: 2}), done) == "partial"
    A.HITS[:] = [(A.HTTPS_PORT, A.AD_HOSTS[0], "/ast.js?t=1"), (A.HTTPS_PORT, A.AD_TOP, "/first.js?t=1"),
                 (A.HTTPS_PORT, A.AD_TOP, "/ads.html?a=0"), (A.HTTPS_PORT, A.AD_CONTROL, "/lib.js")]
    h = A.ad_hits(0)
    assert h[A.AD_HOSTS[0]] == 1 and h[A.AD_TOP + "/first.js"] == 1 and h[A.AD_CONTROL] == 1
    assert A.ad_hits(1)[A.AD_HOSTS[0]] == 0
    A.HITS[:] = []
