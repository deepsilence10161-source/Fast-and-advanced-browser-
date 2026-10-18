#!/usr/bin/env python3
"""EasyList-syntax filter lists / hosts files -> Chromium subresource_filter *unindexed* ruleset.

Output format = components/subresource_filter/core/common/unindexed_ruleset.cc @155:
repeated { varint32 size; url_pattern_index.proto.FilteringRules chunk }.
Parsing follows components/subresource_filter/tools/rule_parser/{rule_parser,rule}.cc (BSD-3, Chromium) in behaviour:
element hiding rules and rules with options Chromium does not understand are skipped (never guessed).

Usage: convert.py --out ruleset.pb [--easylist FILE ...] [--hosts FILE ...] [--stats stats.json]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules_pb2 as P  # noqa: E402  (generated from rules.proto by grpc_tools.protoc, see adblock/README.md)

ELEMENT_TYPES = {
    "other": P.ELEMENT_TYPE_OTHER, "script": P.ELEMENT_TYPE_SCRIPT, "image": P.ELEMENT_TYPE_IMAGE,
    "stylesheet": P.ELEMENT_TYPE_STYLESHEET, "object": P.ELEMENT_TYPE_OBJECT,
    "xmlhttprequest": P.ELEMENT_TYPE_XMLHTTPREQUEST, "object-subrequest": P.ELEMENT_TYPE_OBJECT_SUBREQUEST,
    "subdocument": P.ELEMENT_TYPE_SUBDOCUMENT, "ping": P.ELEMENT_TYPE_PING, "media": P.ELEMENT_TYPE_MEDIA,
    "font": P.ELEMENT_TYPE_FONT, "popup": P.ELEMENT_TYPE_POPUP, "websocket": P.ELEMENT_TYPE_WEBSOCKET,
    "webtransport": P.ELEMENT_TYPE_WEBTRANSPORT, "webbundle": P.ELEMENT_TYPE_WEBBUNDLE,
}
ACTIVATION_TYPES = {"document": P.ACTIVATION_TYPE_DOCUMENT, "elemhide": P.ACTIVATION_TYPE_ELEMHIDE,
                    "generichide": P.ACTIVATION_TYPE_GENERICHIDE, "genericblock": P.ACTIVATION_TYPE_GENERICBLOCK}
ALL_ELEMENTS = P.ELEMENT_TYPE_ALL
DEFAULT_ELEMENTS = ALL_ELEMENTS & ~P.ELEMENT_TYPE_POPUP
HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


class Skip(Exception):
    pass


def pattern_type(pattern, anchor_left, anchor_right):
    if len(pattern) >= 2 and pattern[0] == "/" and pattern[-1] == "/":
        return P.URL_PATTERN_TYPE_REGEXP
    if "^" in pattern or anchor_left != P.ANCHOR_TYPE_NONE or anchor_right != P.ANCHOR_TYPE_NONE:
        return P.URL_PATTERN_TYPE_WILDCARDED
    pos = pattern.find("*")
    if pos == -1 or pos == len(pattern) - 1:
        return P.URL_PATTERN_TYPE_SUBSTRING
    if pos == 0:
        nxt = pattern.find("*", 1)
        if nxt == -1 or nxt == len(pattern) - 1:
            return P.URL_PATTERN_TYPE_SUBSTRING
    return P.URL_PATTERN_TYPE_WILDCARDED


def parse_line(line):
    """Returns a UrlRule or None (comment / style rule); raises Skip for unsupported rules."""
    part = line.strip()
    if not part or part[0] in "![":
        return None
    i = part.find("#")
    while i != -1:
        if i + 1 < len(part) and part[i + 1] in "#@$?%":
            return None   # element hiding / scriptlet / snippet: not network rules
        i = part.find("#", i + 1)
    allow = False
    if part.startswith("@@"):
        allow, part = True, part[2:]
    elif part.startswith("@"):
        raise Skip("bad allowlist syntax")
    third_party, match_case, domains = P.SOURCE_TYPE_ANY, False, []
    type_mask, act_mask, seen_type = DEFAULT_ELEMENTS, 0, False
    opt = part.rfind("$")
    if opt != -1 and not part.endswith("/"):
        for piece in [p.strip() for p in part[opt + 1:].split(",") if p.strip()]:
            neg = piece.startswith("~")
            name = piece[1:] if neg else piece
            key, _, value = name.partition("=")
            if key in ELEMENT_TYPES:
                if not neg:
                    if not seen_type:
                        type_mask = 0
                    type_mask |= ELEMENT_TYPES[key]
                else:
                    type_mask &= ~ELEMENT_TYPES[key]
                seen_type = True
            elif key in ACTIVATION_TYPES:
                if not allow or neg:
                    raise Skip("activation type on block rule")
                if not seen_type:
                    type_mask = 0
                act_mask |= ACTIVATION_TYPES[key]
                seen_type = True
            elif key == "third-party":
                third_party = P.SOURCE_TYPE_FIRST_PARTY if neg else P.SOURCE_TYPE_THIRD_PARTY
            elif key == "match-case" and not neg:
                match_case = True
            elif key == "domain" and value and not neg:
                domains = [d.strip().lower() for d in value.split("|") if d.strip()]
            else:
                raise Skip("unsupported option " + key)
        part = part[:opt]
    anchor_left = anchor_right = P.ANCHOR_TYPE_NONE
    if part.startswith("||"):
        anchor_left, part = P.ANCHOR_TYPE_SUBDOMAIN, part[2:]
    elif part.startswith("|"):
        anchor_left, part = P.ANCHOR_TYPE_BOUNDARY, part[1:]
    if part.endswith("|"):
        anchor_right, part = P.ANCHOR_TYPE_BOUNDARY, part[:-1]
    ptype = pattern_type(part, anchor_left, anchor_right)
    if ptype == P.URL_PATTERN_TYPE_REGEXP:
        raise Skip("regexp")   # not supported by the Chromium matcher
    if anchor_left != P.ANCHOR_TYPE_SUBDOMAIN and part.startswith("*"):
        part, anchor_left = part[1:], P.ANCHOR_TYPE_NONE
    if part.endswith("*"):
        part, anchor_right = part[:-1], P.ANCHOR_TYPE_NONE
    if not part and not domains and not allow:
        raise Skip("matches everything")
    if not part.isascii():
        raise Skip("non-ascii pattern")
    r = P.UrlRule()
    r.semantics = P.RULE_SEMANTICS_ALLOWLIST if allow else P.RULE_SEMANTICS_BLOCKLIST
    r.source_type = third_party
    if type_mask & ALL_ELEMENTS:
        r.element_types = type_mask & ALL_ELEMENTS
    if act_mask:
        r.activation_types = act_mask
    for d in sorted(domains, key=lambda x: (-len(x.lstrip("~")), x)):
        item = r.initiator_domains.add()
        if d.startswith("~"):
            item.domain, item.exclude = d[1:], True
        else:
            item.domain = d
    r.url_pattern_type = ptype
    r.anchor_left, r.anchor_right = anchor_left, anchor_right
    if match_case:
        r.match_case = True
    if part:
        r.url_pattern = part if match_case else part.lower()
    if not (r.element_types or r.activation_types):
        raise Skip("no element or activation type left")
    return r


def hosts_rules(lines):
    """hosts-file lines ('0.0.0.0 ads.example' / '127.0.0.1 x') -> third-party block rules ||host^."""
    for line in lines:
        line = line.split("#", 1)[0].strip()
        bits = line.split()
        if len(bits) < 2 or bits[0] not in ("0.0.0.0", "127.0.0.1", "::1", "::"):
            continue
        for host in bits[1:]:
            host = host.lower().rstrip(".")
            if host in ("localhost", "localhost.localdomain", "local", "broadcasthost", "0.0.0.0") or not HOST_RE.match(host):
                continue
            yield f"||{host}^$third-party"


def write_ruleset(rules, out, chunk=1000):
    def varint(n):
        b = bytearray()
        while True:
            x = n & 0x7F
            n >>= 7
            if n:
                b.append(x | 0x80)
            else:
                b.append(x)
                return bytes(b)
    with open(out, "wb") as f:
        for i in range(0, len(rules), chunk):
            msg = P.FilteringRules()
            msg.url_rules.extend(rules[i:i + chunk])
            data = msg.SerializeToString()
            f.write(varint(len(data)))
            f.write(data)


def read_ruleset(path):
    data, pos, out = open(path, "rb").read(), 0, []
    while pos < len(data):
        shift = size = 0
        while True:
            b = data[pos]
            pos += 1
            size |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                break
        msg = P.FilteringRules()
        msg.ParseFromString(data[pos:pos + size])
        pos += size
        out.extend(msg.url_rules)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--easylist", nargs="*", default=[])
    ap.add_argument("--hosts", nargs="*", default=[])
    ap.add_argument("--stats")
    a = ap.parse_args()
    rules, seen, stats = [], set(), {"files": {}, "skipped_reasons": {}}
    sources = [(p, open(p, encoding="utf-8", errors="replace").read().splitlines()) for p in a.easylist]
    sources += [(p, list(hosts_rules(open(p, encoding="utf-8", errors="replace").read().splitlines()))) for p in a.hosts]
    for path, lines in sources:
        n_ok = n_skip = 0
        for line in lines:
            try:
                r = parse_line(line)
            except Skip as e:
                n_skip += 1
                reason = str(e).split(" ")[0] if not str(e).startswith("unsupported") else str(e)
                stats["skipped_reasons"][reason] = stats["skipped_reasons"].get(reason, 0) + 1
                continue
            if r is None:
                continue
            key = r.SerializeToString()
            if key in seen:
                continue
            seen.add(key)
            rules.append(r)
            n_ok += 1
        stats["files"][os.path.basename(path)] = {"rules": n_ok, "skipped": n_skip}
    write_ruleset(rules, a.out)
    stats["total_rules"] = len(rules)
    stats["bytes"] = os.path.getsize(a.out)
    if a.stats:
        json.dump(stats, open(a.stats, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: stats[k] for k in ("total_rules", "bytes", "files")}))


if __name__ == "__main__":
    main()
