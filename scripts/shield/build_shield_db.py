#!/usr/bin/env python3
"""Swiftra Shield DB builder.

Builds an on-device threat list from redistributable open feeds (licences verified 2026-10-17,
see docs/swiftra-shield.md). Output (all deterministic for the same inputs):
  shield.bin       : binary DB (format below) -> signed by the workflow (openssl ECDSA P-256)
  manifest.json    : per-source counts, guard removals, sha256, created
Format v1 (big-endian):
  magic  b"SWSHLD01"
  u64    created (unix seconds)
  u32    n_lists
  n_lists x { u32 threat (2=SOCIAL_ENGINEERING, 4=POTENTIALLY_HARMFUL_APPLICATION, 3=UNWANTED_SOFTWARE), u32 count }
  then per list: count x i64 sorted ascending (signed) = first 8 bytes of SHA-256(expression)
Lookup in the browser: expressions(url) -> hash64 -> binary search per list (no network, no URL leaves device).
"""
import argparse
import hashlib
import io
import json
import os
import re
import struct
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sbcanon  # noqa: E402

MAGIC = b"SWSHLD01"
PHISH, MALWARE, UNWANTED = 2, 4, 3

# kind: "urls" = one URL per line (exact expression), "domains" = one host per line ("host/" expression)
SOURCES = [
    {"id": "phishing_database_links", "kind": "urls", "threat": PHISH, "licence": "MIT",
     "url": "https://raw.githubusercontent.com/Phishing-Database/Phishing.Database/master/phishing-links-ACTIVE.txt"},
    {"id": "phishing_database_domains", "kind": "domains", "threat": PHISH, "licence": "MIT",
     "url": "https://raw.githubusercontent.com/Phishing-Database/Phishing.Database/master/phishing-domains-ACTIVE.txt"},
    {"id": "tweetfeed_urls", "kind": "urls", "threat": MALWARE, "licence": "CC0-1.0",
     "url": "https://api.tweetfeed.live/v1/blocklist/urls.txt"},
    {"id": "tweetfeed_domains", "kind": "domains", "threat": MALWARE, "licence": "CC0-1.0",
     "url": "https://api.tweetfeed.live/v1/blocklist/domains.txt"},
]

# Canary entries: deterministic E2E targets. Google's public test pages + a loopback path.
CANARIES = [
    ("testsafebrowsing.appspot.com/s/phishing.html", PHISH),
    ("testsafebrowsing.appspot.com/s/malware.html", MALWARE),
    ("127.0.0.1/__swiftra_shield_canary__/phishing.html", PHISH),
    ("127.0.0.1/__swiftra_shield_canary__/malware.html", MALWARE),
    # c2b: a public-host canary Google's real-time service rates SAFE (tools/sb_rt_probe.py,
    # 2026-10-17) and that is not a private IP, so Enhanced protection really performs the URL
    # real-time lookup for it -> proves Shield still blocks when Google says SAFE (patches/0007).
    # The path does not exist on the host (404), nothing harmful is served.
    ("testsafebrowsing.appspot.com/s/swiftra_shield_canary.html", PHISH),
    # patches/0015 Download Shield: a download that bypasses navigation (<a download>, also reached through a
    # redirect) must be checked against the list. Loopback only; the file served there is harmless bytes.
    ("127.0.0.1/__swiftra_shield_canary__/download/swiftra-canary.zip", MALWARE),
]

# FIRST_PARTY: every subdomain is operated by the owner -> never block a whole host under it
# (issue tracker shows mail.google.com/docs.google.com listed by feeds); specific URLs still allowed.
FIRST_PARTY = {
    "google.com", "google.co.in", "gstatic.com", "youtube.com", "gmail.com", "android.com", "github.com",
    "microsoft.com", "live.com", "office.com", "outlook.com", "microsoftonline.com", "windows.net",
    "apple.com", "icloud.com", "amazon.com", "amazon.in", "facebook.com", "instagram.com", "whatsapp.com",
    "twitter.com", "x.com", "linkedin.com", "wikipedia.org", "cloudflare.com", "mozilla.org",
    "schemas.microsoft.com", "w3.org", "proofpoint.com", "mailchimp.com", "sendgrid.net",
    "example.com", "example.org", "example.net", "gov.in", "nic.in", "npci.org.in", "sbi.co.in",
    "paytm.com", "phonepe.com", "chromium.org", "swiftra.app",
}
# SHARED: user-content/tracking platforms -> only the apex itself is protected; tenant hosts may be listed.
SHARED = {
    "github.io", "githubusercontent.com", "googleusercontent.com", "appspot.com", "blogspot.com",
    "firebaseapp.com", "web.app", "workers.dev", "pages.dev", "r2.dev", "amazonaws.com", "cloudfront.net",
    "wordpress.com", "weebly.com", "wixsite.com", "netlify.app", "vercel.app", "herokuapp.com",
    "dropbox.com", "box.com", "sharepoint.com", "bit.ly", "tinyurl.com", "t.co", "mjt.lu", "onelink.me",
    "list-manage.com", "hubspotlinks.com", "sendibm1.com", "sendibm3.com", "localhost",
}

DOMAIN_RX = re.compile(r"^[a-z0-9_]([a-z0-9_\-]{0,62}\.)+[a-z0-9\-]{2,63}$")


def fetch(url, cap=200 * 1024 * 1024, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "SwiftraShieldBuilder/1 (+github.com/deepsilence10161-source/Fast-and-advanced-browser-)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(cap + 1)
    if len(data) > cap:
        raise ValueError("feed too large")
    return data


def parse_lines(data: bytes):
    for line in data.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!", ";")):
            continue
        # hosts-file style "0.0.0.0 domain"
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            line = parts[1]
        yield line


def guard_reason(expr: str, host_only: bool, top: set):
    """None = keep. Otherwise the reason the entry is dropped (false-positive guard)."""
    host, _, rest = expr.partition("/")
    if not host or "." not in host:
        return "no_dot"
    labels = host.split(".")
    suffixes = {".".join(labels[i:]) for i in range(len(labels) - 1)}
    whole_site = host_only or rest == ""
    if whole_site:
        if suffixes & FIRST_PARTY:
            return "first_party"
        bare = host[4:] if host.startswith("www.") else host
        if bare in SHARED:
            return "shared_apex"
        if bare in top:
            return "top_sites"
    return None


def load_top(path_or_url, n):
    if not path_or_url:
        return set()
    data = open(path_or_url, "rb").read() if os.path.exists(path_or_url) else fetch(path_or_url)
    if data[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(data))
        data = z.read(z.namelist()[0])
    top = set()
    for line in data.decode("utf-8", "replace").splitlines():
        if "," in line:
            line = line.split(",", 1)[1]
        line = line.strip().lower()
        if line:
            top.add(line)
            if len(top) >= n:
                break
    return top


def build(sources, top, created, local=None):
    lists = {PHISH: set(), MALWARE: set(), UNWANTED: set()}
    manifest = {"format": "SWSHLD01", "created": created, "sources": [], "guard_removed": {}, "canaries": len(CANARIES)}
    for s in sources:
        rec = {k: s[k] for k in ("id", "kind", "threat", "licence", "url")}
        try:
            data = local[s["id"]] if local and s["id"] in local else fetch(s["url"])
        except Exception as e:  # one feed failing must not stop the others
            rec["error"] = repr(e)[:200]
            manifest["sources"].append(rec)
            continue
        n_in = n_ok = 0
        for line in parse_lines(data):
            n_in += 1
            host_only = s["kind"] == "domains"
            if host_only:
                d = line.lower().strip(".")
                if d.startswith("*."):
                    d = d[2:]
                if not DOMAIN_RX.match(d) and not sbcanon.ipv4_normalize(d):
                    continue
                expr = sbcanon.entry_expression(d, host_only=True)
            else:
                if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", line):
                    line = "http://" + line
                try:
                    expr = sbcanon.entry_expression(line)
                except Exception:
                    expr = None
            if not expr:
                continue
            why = guard_reason(expr, host_only, top)
            if why:
                manifest["guard_removed"][why] = manifest["guard_removed"].get(why, 0) + 1
                continue
            lists[s["threat"]].add(expr)
            n_ok += 1
        rec.update({"lines": n_in, "accepted": n_ok, "sha256": hashlib.sha256(data).hexdigest()})
        manifest["sources"].append(rec)
    # URL entries already covered by a whole-host entry (host or any parent, any list) are redundant
    hosts = {e[:-1] for t in lists for e in lists[t] if e.endswith("/") and e.count("/") == 1}
    redundant = 0
    for t in lists:
        keep = set()
        for e in lists[t]:
            h, _, rest = e.partition("/")
            lab = h.split(".")
            if rest and any(".".join(lab[i:]) in hosts for i in range(len(lab) - 1)):
                redundant += 1
                continue
            keep.add(e)
        lists[t] = keep
    manifest["redundant_url_entries"] = redundant
    for expr, t in CANARIES:
        lists[t].add(expr)
    # an expression listed as both: keep the stronger (malware) only once per list is fine; keep both
    out = io.BytesIO()
    order = [PHISH, MALWARE, UNWANTED]
    hashed = {t: sorted({sbcanon.expr_hash64(e) for e in lists[t]}) for t in order}
    out.write(MAGIC + struct.pack(">QI", created, len(order)))
    for t in order:
        out.write(struct.pack(">II", t, len(hashed[t])))
    for t in order:
        out.write(struct.pack(">%dq" % len(hashed[t]), *hashed[t]))
    blob = out.getvalue()
    manifest["counts"] = {str(t): len(hashed[t]) for t in order}
    manifest["sha256"] = hashlib.sha256(blob).hexdigest()
    manifest["bytes"] = len(blob)
    return blob, manifest


TMAGIC = b"SWSHZ001"


def _varint(n: int, out: bytearray):
    while True:
        x = n & 0x7F
        n >>= 7
        if n:
            out.append(x | 0x80)
        else:
            out.append(x)
            return


def encode_transport(blob: bytes) -> bytes:
    """SWSHZ001 = magic + gzip(u64 created, u32 n, n*(u32 threat,u32 count), per list varint deltas of
    unsigned(v + 2^63)). The workflow signs this file; the browser verifies before decoding."""
    import gzip
    created, lists = parse_db(blob)
    order = list(lists)
    body = bytearray(struct.pack(">QI", created, len(order)))
    for t in order:
        body += struct.pack(">II", t, len(lists[t]))
    for t in order:
        prev = 0
        for v in lists[t]:
            u = v + (1 << 63)
            _varint(u - prev, body)
            prev = u
    return TMAGIC + gzip.compress(bytes(body), 9, mtime=0)


def decode_transport(swz: bytes) -> bytes:
    import gzip
    if swz[:8] != TMAGIC:
        raise ValueError("bad transport magic")
    body = gzip.decompress(swz[8:])
    created, n = struct.unpack(">QI", body[:12])
    if not 1 <= n <= 16:
        raise ValueError("bad list count")
    off, hdr = 12, []
    for _ in range(n):
        hdr.append(struct.unpack(">II", body[off:off + 8])); off += 8
    out = bytearray(MAGIC + struct.pack(">QI", created, n))
    for t, c in hdr:
        out += struct.pack(">II", t, c)
    for t, c in hdr:
        prev = 0
        for _ in range(c):
            shift = val = 0
            while True:
                b = body[off]; off += 1
                val |= (b & 0x7F) << shift
                shift += 7
                if not b & 0x80:
                    break
                if shift > 63:
                    raise ValueError("varint overflow")
            prev += val
            if prev >= 1 << 64:
                raise ValueError("value overflow")
            out += struct.pack(">q", prev - (1 << 63))
    if off != len(body):
        raise ValueError("trailing bytes")
    parse_db(bytes(out))
    return bytes(out)


def parse_db(blob: bytes):
    if blob[:8] != MAGIC:
        raise ValueError("bad magic")
    created, n = struct.unpack(">QI", blob[8:20])
    if not 1 <= n <= 16:
        raise ValueError("bad list count")
    hdr, off, lists = [], 20, {}
    for _ in range(n):
        hdr.append(struct.unpack(">II", blob[off:off + 8])); off += 8
    for t, c in hdr:
        arr = struct.unpack(">%dq" % c, blob[off:off + 8 * c]); off += 8 * c
        if list(arr) != sorted(arr):
            raise ValueError("unsorted")
        lists[t] = arr
    if off != len(blob):
        raise ValueError("trailing bytes")
    return created, lists


def feed_notice():
    """Licence notice for the redistributed feed data (MIT requires it in every copy): the LICENSE text of
    patches/0019-swiftra-shield-feeds-credits.py, which also puts it in the app's chrome://credits."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "patches", "0019-swiftra-shield-feeds-credits.py")
    spec = importlib.util.spec_from_file_location("shield_feeds_credits", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LICENSE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", default="https://tranco-list.eu/top-1m.csv.zip", help="Tranco list (guard only, not redistributed)")
    ap.add_argument("--top-n", type=int, default=100000)
    ap.add_argument("--min-entries", type=int, default=20000, help="refuse to publish a suspiciously small DB")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    try:
        top = load_top(a.top, a.top_n)
    except Exception as e:
        print(f"top list unavailable: {e!r}", file=sys.stderr)
        top = set()
    created = int(time.time())
    blob, manifest = build(SOURCES, top, created)
    manifest["top_sites_guard"] = len(top)
    total = sum(manifest["counts"].values())
    open(os.path.join(a.out, "shield.bin"), "wb").write(blob)
    swz = encode_transport(blob)
    if decode_transport(swz) != blob:
        print("transport round-trip mismatch", file=sys.stderr)
        return 3
    open(os.path.join(a.out, "shield.swz"), "wb").write(swz)
    manifest["transport_bytes"] = len(swz)
    manifest["transport_sha256"] = hashlib.sha256(swz).hexdigest()

    for s in manifest["sources"]:
        print(s["id"], s.get("accepted"), s.get("error", ""))
    with open(os.path.join(a.out, "NOTICE.txt"), "w", encoding="utf-8") as f:
        f.write(feed_notice())
    manifest["notice"] = "NOTICE.txt"
    json.dump(manifest, open(os.path.join(a.out, "manifest.json"), "w"), indent=1)
    print(json.dumps({k: manifest.get(k) for k in ("counts", "bytes", "transport_bytes", "guard_removed", "redundant_url_entries")}))
    if total < a.min_entries:
        print(f"DB too small ({total} < {a.min_entries}); not publishing", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
