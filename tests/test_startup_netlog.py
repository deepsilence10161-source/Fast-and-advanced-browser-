"""Offline tests for scripts/ci/startup_netlog.py (NetLog parsing + classification). Device part runs in CI."""
import importlib.util
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "ci"))
spec = importlib.util.spec_from_file_location("startup_netlog", os.path.join(HERE, "..", "scripts", "ci", "startup_netlog.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

CONSTS = {"logEventTypes": {"URL_REQUEST_START_JOB": 1, "HOST_RESOLVER_MANAGER_REQUEST": 2,
                            "HTTP_STREAM_JOB_CONTROLLER": 3, "QUIC_SESSION": 4, "TCP_CONNECT": 5,
                            "SOCKET_POOL_CONNECT_JOB_CREATED": 6}}


def ev(t, params, sid=1):
    return {"type": t, "source": {"id": sid, "type": 1}, "time": "1", "phase": 0, "params": params}


EVENTS = [
    ev(1, {"url": "https://t0.gstatic.com/faviconV2?client=chrome&url=https://example.org", "method": "GET"}),
    ev(1, {"url": "https://example.com/", "method": "GET"}),
    ev(1, {"url": "http://127.0.0.1:8001/x.html", "method": "GET"}),
    ev(2, {"host": "https://www.google.com:443"}),
    ev(3, {"url": "https://www.google.com/", "is_preconnect": True}),
    ev(4, {"host": "accounts.google.com", "port": 443}),
    ev(5, {"address_list": ["142.250.1.1:443"]}),
    ev(6, {"group_id": "ssl/content-autofill.googleapis.com:443"}),
]


class Parse(unittest.TestCase):
    def test_ndjson_truncated(self):
        text = json.dumps({"constants": CONSTS}) + "\n" + "\n".join(json.dumps(e) for e in EVENTS) + '\n{"type": 1, "sou'
        consts, events = S.load_netlog(text)
        self.assertEqual(consts["logEventTypes"]["QUIC_SESSION"], 4)
        self.assertEqual(len(events), len(EVENTS))          # the cut-off last line is ignored

    def test_json_format(self):
        text = ('{"constants": ' + json.dumps(CONSTS) + ',\n"events": [\n'
                + ",\n".join(json.dumps(e) for e in EVENTS) + ",\n")   # truncated (no closing ]})
        consts, events = S.load_netlog(text)
        self.assertTrue(consts)
        self.assertEqual(len(events), len(EVENTS))

    def test_summary(self):
        s = S.summarize(CONSTS, EVENTS)
        self.assertEqual(s["google_requests"], {"GET https://t0.gstatic.com/faviconV2": 1})   # query stripped
        self.assertEqual(s["non_google_requests"], {"GET https://example.com/": 1})          # loopback excluded
        self.assertEqual(s["google_resolves"], ["www.google.com"])
        self.assertIn("www.google.com", s["preconnect_hosts"])
        self.assertIn("accounts.google.com", s["google_connect_hosts"])
        self.assertIn("content-autofill.googleapis.com", s["google_connect_hosts"])
        self.assertIn("142.250.1.1:443", s["remote_ips"])
        self.assertEqual(s["sb_hosts"], [])

    def test_sb_detected_in_any_channel(self):
        for e in (ev(1, {"url": "https://safebrowsing.googleapis.com/v4/threatListUpdates:fetch", "method": "POST"}),
                  ev(2, {"host": "sb-ssl.google.com:443"}),
                  ev(4, {"host": "safebrowsing.google.com"})):
            self.assertTrue(S.summarize(CONSTS, [e])["sb_hosts"], e)

    def test_norm_host(self):
        self.assertEqual(S.norm_host("https://www.google.com:443"), "www.google.com")
        self.assertEqual(S.norm_host("example.org"), "example.org")
        self.assertEqual(S.norm_host("WWW.Example.org.:80"), "www.example.org")


if __name__ == "__main__":
    unittest.main()
