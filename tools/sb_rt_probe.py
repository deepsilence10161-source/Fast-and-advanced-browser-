#!/usr/bin/env python3
"""Research probe: what Google's Safe Browsing real-time URL endpoint (used by Chromium's
Enhanced protection, UrlRealTimeMechanism) answers for a URL, anonymously (no key, no OAuth).
Only for Google's own harmless test pages (testsafebrowsing.appspot.com) and IANA example domains.
Usage: sb_rt_probe.py URL [URL...]   -> threat_type / verdict_type / cache_duration_sec per URL
"""
import sys, urllib.request

EP = "https://safebrowsing.google.com/safebrowsing/clientreport/realtime"
THREAT = {0: "UNSPECIFIED", 1: "WEB_MALWARE", 3: "SOCIAL_ENGINEERING", 4: "UNWANTED_SOFTWARE", 5: "UNCLEAR_BILLING"}
VERDICT = {0: "UNSPECIFIED", 1: "SAFE", 50: "SUSPICIOUS", 75: "WARN", 100: "DANGEROUS"}


def varint(n):
    out = b""
    while True:
        b, n = n & 0x7F, n >> 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def field(no, wt, payload):
    return varint(no << 3 | wt) + payload


def request(url):
    u = url.encode()
    return (field(1, 2, varint(len(u)) + u) + field(2, 0, varint(1)) + field(6, 0, varint(3))
            + field(7, 0, varint(1)) + field(9, 0, varint(1)) + field(10, 0, varint(1)))


def parse(buf):
    i, out = 0, []
    while i < len(buf):
        key, i = rd(buf, i)
        no, wt = key >> 3, key & 7
        if wt == 0:
            v, i = rd(buf, i); out.append((no, v))
        elif wt == 2:
            ln, i = rd(buf, i); out.append((no, buf[i:i + ln])); i += ln
        elif wt == 5:
            i += 4
        elif wt == 1:
            i += 8
        else:
            raise ValueError("wire type %d" % wt)
    return out


def rd(b, i):
    n = s = 0
    while True:
        c = b[i]; i += 1; n |= (c & 0x7F) << s; s += 7
        if not c & 0x80:
            return n, i


def main():
    for url in sys.argv[1:]:
        req = urllib.request.Request(EP, data=request(url), method="POST",
                                     headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=20) as r:
            body, code = r.read(), r.status
        infos = [parse(v) for no, v in parse(body) if no == 1]
        if not infos:
            print(f"{url}: HTTP {code}, no threat_info (=SAFE by default)")
        for ti in infos:
            d = {k: v for k, v in ti if not isinstance(v, bytes)}
            print(f"{url}: HTTP {code} threat={THREAT.get(d.get(1, 0), d.get(1))} "
                  f"verdict={VERDICT.get(d.get(4, 0), d.get(4))} cache_s={d.get(2)}")


if __name__ == "__main__":
    main()
