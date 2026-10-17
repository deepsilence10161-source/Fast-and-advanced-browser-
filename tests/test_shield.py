"""Swiftra Shield: canonicalization parity (upstream vectors), builder guards, transport, Java twin."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "shield"))
import build_shield_db as B  # noqa: E402
import sbcanon  # noqa: E402

VEC = json.load(open(os.path.join(ROOT, "tests", "data", "sb_canon_vectors.json"), encoding="utf-8"))
EXTRA_URLS = [
    "http://a.b.c/1/2.html?param=1", "http://a.b.c.d.e.f.g/1.html", "http://1.2.3.4/1/", "http://a.b/saw-cgi/eBayISAPI.dll/",
    "https://WWW.Example.COM:443/A/./b/../c//d?x=1#frag", "http://0x7f.1/path", "http://017700000001/", "http://user:pw@evil.test/p",
    "http://xn--80ak6aa92e.com/login", "http://пример.рф/вход", "http://host.com/a%2fb%2Fc", "http://host.com/%3Fq%3D1?real=2",
    "http://127.0.0.1:8000/__swiftra_shield_canary__/phishing.html", "https://testsafebrowsing.appspot.com/s/phishing.html",
]


def spec_expressions(url):
    return sorted(sbcanon.expressions(url))


class Canon(unittest.TestCase):
    def test_upstream_vectors(self):
        self.assertEqual(len(VEC["cases"]), 37)
        for c in VEC["cases"]:
            self.assertEqual(sbcanon.canonicalize(c["url"]), (c["host"], c["path"], c["query"]), c["url"])

    def test_google_spec_expressions(self):
        # developers.google.com/safe-browsing/v4/urls-hashing#suffixprefix-expressions
        self.assertEqual(spec_expressions("http://a.b.c/1/2.html?param=1"), sorted([
            "a.b.c/1/2.html?param=1", "a.b.c/1/2.html", "a.b.c/", "a.b.c/1/",
            "b.c/1/2.html?param=1", "b.c/1/2.html", "b.c/", "b.c/1/"]))
        self.assertEqual(spec_expressions("http://a.b.c.d.e.f.g/1.html"), sorted([
            "a.b.c.d.e.f.g/1.html", "a.b.c.d.e.f.g/", "c.d.e.f.g/1.html", "c.d.e.f.g/", "d.e.f.g/1.html",
            "d.e.f.g/", "e.f.g/1.html", "e.f.g/", "f.g/1.html", "f.g/"]))
        self.assertEqual(spec_expressions("http://1.2.3.4/1/"), sorted(["1.2.3.4/1/", "1.2.3.4/"]))

    def test_hash64_known(self):
        import hashlib
        import struct
        self.assertEqual(sbcanon.expr_hash64("abc"), struct.unpack(">q", hashlib.sha256(b"abc").digest()[:8])[0])


FEEDS = {
    "phishing_database_links": b"http://evil.test/login.php?a=1\nhttps://docs.google.com/forms/d/e/BAD/viewform\n"
                               b"http://covered.test/deep/page\nhttp://www.google.com/\n# comment\n",
    "phishing_database_domains": b"covered.test\nmail.google.com\ngithub.io\nevil-tenant.github.io\npopular.test\n",
    "tweetfeed_urls": b"http://203.0.113.9/bin.exe\n",
    "tweetfeed_domains": b"malware.test\n",
}


class Builder(unittest.TestCase):
    def setUp(self):
        self.blob, self.m = B.build(B.SOURCES, {"popular.test"}, 1760000000, local=FEEDS)
        _, self.lists = B.parse_db(self.blob)

    def has(self, expr, t):
        return sbcanon.expr_hash64(expr) in set(self.lists[t])

    def test_entries_and_guards(self):
        self.assertTrue(self.has("evil.test/login.php?a=1", B.PHISH))
        self.assertTrue(self.has("docs.google.com/forms/d/e/BAD/viewform", B.PHISH))   # URL on first party: allowed
        self.assertFalse(self.has("www.google.com/", B.PHISH))                          # whole first-party host: dropped
        self.assertFalse(self.has("mail.google.com/", B.PHISH))
        self.assertFalse(self.has("github.io/", B.PHISH))                               # shared apex: dropped
        self.assertTrue(self.has("evil-tenant.github.io/", B.PHISH))                    # tenant: kept
        self.assertFalse(self.has("popular.test/", B.PHISH))                            # top-sites guard
        self.assertTrue(self.has("covered.test/", B.PHISH))
        self.assertFalse(self.has("covered.test/deep/page", B.PHISH))                   # redundant URL entry
        self.assertTrue(self.has("203.0.113.9/bin.exe", B.MALWARE))
        self.assertTrue(self.has("malware.test/", B.MALWARE))
        for e, t in B.CANARIES:
            self.assertTrue(self.has(e, t), e)
        g = self.m["guard_removed"]
        self.assertEqual((g.get("first_party"), g.get("shared_apex"), g.get("top_sites")), (2, 1, 1))
        self.assertEqual(self.m["redundant_url_entries"], 1)

    def test_lookup_semantics(self):
        """Browser-side matching = expressions(url) ∩ list (domain entry covers subdomains and paths)."""
        def check(url):
            hs = {sbcanon.expr_hash64(e) for e in sbcanon.expressions(url)}
            for t in (B.MALWARE, B.PHISH):
                if hs & set(self.lists[t]):
                    return t
            return 0
        self.assertEqual(check("https://a.b.covered.test/x/y?z"), B.PHISH)
        self.assertEqual(check("http://evil.test/login.php?a=1"), B.PHISH)
        self.assertEqual(check("http://evil.test/login.php"), 0)          # exact URL entry with query
        self.assertEqual(check("https://www.google.com/"), 0)
        self.assertEqual(check("http://malware.test/anything"), B.MALWARE)
        self.assertEqual(check("https://testsafebrowsing.appspot.com/s/phishing.html"), B.PHISH)
        self.assertEqual(check("https://example.com/"), 0)

    def test_transport_roundtrip_and_rejects(self):
        swz = B.encode_transport(self.blob)
        self.assertEqual(B.decode_transport(swz), self.blob)
        with self.assertRaises(Exception):
            B.decode_transport(b"XXXXXXXX" + swz[8:])
        with self.assertRaises(Exception):
            B.parse_db(self.blob + b"\0")

    def test_feed_failure_is_isolated(self):
        feeds = dict(FEEDS)
        del feeds["tweetfeed_urls"]
        srcs = [dict(s) for s in B.SOURCES]
        for s in srcs:
            if s["id"] == "tweetfeed_urls":
                s["url"] = "http://127.0.0.1:9/unreachable"
        blob, m = B.build(srcs, set(), 1760000000, local=feeds)
        errs = [s for s in m["sources"] if "error" in s]
        self.assertEqual([s["id"] for s in errs], ["tweetfeed_urls"])
        B.parse_db(blob)


@unittest.skipUnless(shutil.which("javac") and shutil.which("openssl"), "javac/openssl not available")
class JavaTwin(unittest.TestCase):
    def test_parity_signature_and_lookup(self):
        d = tempfile.mkdtemp()
        try:
            rows = []
            for url in [c["url"] for c in VEC["cases"]] + EXTRA_URLS:
                h, p, q = sbcanon.canonicalize(url)
                ex = sbcanon.expressions(url)
                rows.append("\t".join([url, h, p, q, "|".join(ex), ",".join(str(sbcanon.expr_hash64(e)) for e in ex)]))
            open(os.path.join(d, "v.tsv"), "w", encoding="utf-8").write("\n".join(rows) + "\n")
            blob, _ = B.build(B.SOURCES, {"popular.test"}, 1760000000, local=FEEDS)
            swz = B.encode_transport(blob)
            open(os.path.join(d, "db.swz"), "wb").write(swz)
            key = os.path.join(d, "k.pem")
            subprocess.run(["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", key], check=True, capture_output=True)
            subprocess.run(["openssl", "dgst", "-sha256", "-sign", key, "-out", os.path.join(d, "db.sig"), os.path.join(d, "db.swz")], check=True)
            pub = subprocess.run(["openssl", "ec", "-in", key, "-pubout", "-outform", "DER"], check=True, capture_output=True).stdout
            import base64
            checks = [("https://a.b.covered.test/x/y?z", 2), ("http://evil.test/login.php?a=1", 2), ("http://evil.test/login.php", 0),
                      ("https://www.google.com/", 0), ("http://malware.test/anything", 4), ("http://203.0.113.9/bin.exe", 4),
                      ("https://testsafebrowsing.appspot.com/s/phishing.html", 2), ("https://testsafebrowsing.appspot.com/s/malware.html", 4),
                      ("http://127.0.0.1:8000/__swiftra_shield_canary__/phishing.html", 2), ("https://example.com/", 0),
                      ("https://evil-tenant.github.io/a", 2), ("https://github.io/", 0)]
            open(os.path.join(d, "c.tsv"), "w").write("\n".join(f"{u}\t{t}" for u, t in checks) + "\n")
            src = [os.path.join(ROOT, "shield", "java", "org", "chromium", "components", "safe_browsing", "SwiftraShield.java"),
                   os.path.join(ROOT, "shield", "javatest", "ShieldParity.java"),
                   os.path.join(ROOT, "shield", "javatest", "org", "chromium", "build", "annotations", "NullMarked.java"),
                   os.path.join(ROOT, "shield", "javatest", "org", "chromium", "build", "annotations", "Nullable.java")]
            r = subprocess.run(["javac", "-Xlint:all", "-Werror", "-d", os.path.join(d, "cls")] + src, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = subprocess.run(["java", "-cp", os.path.join(d, "cls"), "ShieldParity", os.path.join(d, "v.tsv"), os.path.join(d, "db.swz"),
                                os.path.join(d, "db.sig"), base64.b64encode(pub).decode(), os.path.join(d, "c.tsv")],
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("ALL PASS", r.stdout)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()


class PatchSync(unittest.TestCase):
    """patches/0006 must carry exactly shield/java/** (regenerate: python3 shield/make_patch.py)."""

    PATCH = os.path.join(ROOT, "patches", "0006-swiftra-shield.patch")

    def test_in_series(self):
        series = [l.strip() for l in open(os.path.join(ROOT, "patches", "series")) if l.strip() and not l.startswith("#")]
        self.assertIn("0006-swiftra-shield.patch", series)

    def test_new_files_match_sources(self):
        txt = open(self.PATCH, encoding="utf-8").read()
        sections = txt.split("--- /dev/null\n")[1:]
        self.assertEqual(len(sections), 2)
        for sec in sections:
            head, body = sec.split("\n", 1)
            path = head[len("+++ b/"):]
            body = body.split("\n--- ", 1)[0]
            lines = body.split("\n")[1:]  # drop @@ line
            got = "\n".join(l[1:] for l in lines if l.startswith("+")) + "\n"
            name = os.path.basename(path)
            src = open(os.path.join(ROOT, "shield", "java", "org", "chromium", "components", "safe_browsing", name), encoding="utf-8").read()
            self.assertEqual(got, src, f"{name}: stale patch, run shield/make_patch.py")

    def test_bridge_hunk_is_non_branded_only(self):
        txt = open(self.PATCH, encoding="utf-8").read()
        self.assertIn("+            if (sSafeBrowsingApiHandler == null && !BuildConfig.IS_CHROME_BRANDED) {", txt)
        self.assertIn("+                setSafeBrowsingApiHandler(new SwiftraShieldApiHandler());", txt)
        self.assertIn("+import org.chromium.build.BuildConfig;", txt)
        self.assertTrue(all(ord(c) < 128 for c in txt))
        for n in ("SwiftraShield.java", "SwiftraShieldApiHandler.java"):
            self.assertIn(f'+    "java/src/org/chromium/components/safe_browsing/{n}",', txt)
