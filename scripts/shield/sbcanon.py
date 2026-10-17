"""Swiftra Shield: Safe Browsing URL canonicalization + expressions (Python side).

Mirrors chromium SBProtocolManagerUtil (155.0.8059.80):
  CanonicalizeUrl, GenerateHostVariantsToCheckV4, GeneratePathVariantsToCheck, UrlToFullHashes.
The Java twin (SwiftraShield.java) implements the same steps; both are tested against the same
37 upstream vectors (tests/data/sb_canon_vectors.json) and shared expression vectors.

Step 0 ("gurl_lite") approximates GURL for raw feed URLs: trim, drop tab/CR/LF, lowercase scheme,
decode+lowercase host, IPv4 normalization (WHATWG), IDNA, default/explicit port dropped
(SB host never includes a port), dot-segment resolution, empty path -> "/".
In the browser the input is already a GURL spec, for which step 0 is idempotent.
"""
import hashlib
import re
import struct

STANDARD = ("http", "https", "ftp", "ws", "wss")


def unescape(s: bytes) -> bytes:
    """base::UnescapeBinaryURLComponent loop until stable (max 1024)."""
    for _ in range(1025):
        out = re.sub(rb"%([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), s)
        if len(out) == len(s):
            return out
        s = out
    return s


def escape(s: bytes) -> bytes:
    out = bytearray()
    for c in s:
        if c <= 0x20 or c > 0x7E or c in (0x23, 0x25):   # <= ' ', > '~', '#', '%'
            out += b"%%%02X" % c
        else:
            out.append(c)
    return bytes(out)


def _ipv4_part(p: str):
    if p == "":
        return None
    try:
        if p[:2].lower() == "0x":
            return int(p[2:] or "0", 16)
        if len(p) > 1 and p[0] == "0":
            return int(p[1:], 8)
        return int(p, 10)
    except ValueError:
        return None


def ipv4_normalize(host: str):
    """WHATWG IPv4 parser (GURL compatible). Returns dotted quad or None if not an IPv4 address."""
    parts = host.split(".")
    if parts and parts[-1] == "" and len(parts) > 1:
        parts = parts[:-1]
    if not 1 <= len(parts) <= 4:
        return None
    # last part must look numeric for host to be treated as IPv4
    if not re.fullmatch(r"(0[xX][0-9a-fA-F]*|[0-9]+)", parts[-1]):
        return None
    nums = [_ipv4_part(p) for p in parts]
    if any(n is None for n in nums):
        return None
    if any(n > 255 for n in nums[:-1]) or nums[-1] >= 256 ** (5 - len(nums)):
        return None
    v = nums[-1]
    for i, n in enumerate(nums[:-1]):
        v += n << (8 * (3 - i))
    return ".".join(str((v >> s) & 255) for s in (24, 16, 8, 0))


def resolve_dots(path: bytes) -> bytes:
    """RFC 3986 remove_dot_segments as GURL does (segments '.', '..', also %2e forms after unescape)."""
    if not path.startswith(b"/"):
        path = b"/" + path
    segs = path.split(b"/")[1:]
    out = []
    for i, s in enumerate(segs):
        last = i == len(segs) - 1
        if s in (b".",):
            if last:
                out.append(b"")
            continue
        if s == b"..":
            if out:
                out.pop()
            if last:
                out.append(b"")
            continue
        out.append(s)
    return b"/" + b"/".join(out)


def _split(spec: bytes):
    """url::ParseStandardUrl-like split: scheme, userinfo, host, port, path, query, ref (bytes or None)."""
    m = re.match(rb"^([A-Za-z][A-Za-z0-9+.\-]*):", spec)
    if not m:
        return None
    scheme = m.group(1).lower()
    rest = spec[m.end():]
    rest = rest.lstrip(b"/\\")
    i = 0
    while i < len(rest) and rest[i:i + 1] not in (b"/", b"?", b"#", b"\\"):
        i += 1
    auth, rest = rest[:i], rest[i:]
    userinfo = None
    if b"@" in auth:
        userinfo, auth = auth.rsplit(b"@", 1)
    port = None
    pm = re.match(rb"^(.*):([0-9]*)$", auth)
    if pm and not auth.startswith(b"["):
        auth, port = pm.group(1), pm.group(2)
    ref = None
    if b"#" in rest:
        rest, ref = rest.split(b"#", 1)
    query = None
    if b"?" in rest:
        rest, query = rest.split(b"?", 1)
    return scheme, userinfo, auth, port, rest, query, ref


def gurl_lite(url: str):
    """Approximate GURL canonical spec (bytes) for raw input; None if not a standard URL."""
    url = url.strip("".join(chr(i) for i in range(0x21)))   # GURL: trim C0 controls + space
    url = re.sub(r"[\t\r\n]", "", url)
    b = url.encode("utf-8")
    sp = _split(b)
    if not sp:
        return None
    scheme, _ui, host, _port, path, query, _ref = sp
    if scheme.decode() not in STANDARD:
        return None
    host = unescape(host).lower()                    # ASCII-only lowercase
    if any(c > 0x7F for c in host):                  # IDN -> punycode (GURL does this before us)
        try:
            host = host.decode("utf-8").encode("idna")
        except UnicodeError:
            pass
    ip = ipv4_normalize(host.decode("latin-1"))
    if ip:
        host = ip.encode("ascii")
    hb = escape(host)
    path = resolve_dots(path.replace(b"\\", b"/") or b"/")
    out = scheme + b"://" + hb + path
    if query is not None:
        out += b"?" + query
    return out


def canonicalize(url: str):
    """Returns (host, path, query) as str per SBProtocolManagerUtil::CanonicalizeUrl; ("", "", "") if N/A."""
    spec = gurl_lite(url)
    if spec is None:
        return "", "", ""
    # 1. fragment/userinfo already absent in spec. 2. unescape loop
    s = unescape(spec)
    sp = _split(s)
    if not sp:
        return "", "", ""
    scheme, _ui, host, port, path, query, ref = sp
    # 3./4. host dots
    host = re.sub(rb"\.{2,}", b".", host.strip(b"."))
    # 5. path slashes
    path = re.sub(rb"/{2,}", b"/", path)
    # ReplaceComponents re-canonicalization (structural effects only); ASCII-only lowercase (Java parity)
    host = host.lower()
    ip = ipv4_normalize(host.decode("latin-1")) if host else None
    if ip:
        host = ip.encode("ascii")
    path = resolve_dots(path.replace(b"\\", b"/") or b"/")
    out = scheme + b"://" + host + ((b":" + port) if port else b"") + path
    if query is not None:
        out += b"?" + query
    if ref is not None:
        out += b"#" + ref
    # 6. unescape again, 7. escape
    final = escape(unescape(out))
    sp = _split(final)
    if not sp:
        return "", "", ""
    _s, _u, fh, _p, fpath, fquery, _r = sp
    return fh.decode("ascii"), fpath.decode("ascii"), (fquery or b"").decode("ascii")


def host_variants(host: str, is_ip: bool):
    if not host:
        return []
    if is_ip:
        return [host]
    hosts, skipped = [], False
    for i in range(len(host) - 1, -1, -1):
        if len(hosts) >= 4:
            break
        if host[i] == ".":
            if skipped:
                hosts.append(host[i + 1:])
            else:
                skipped = True
    hosts.append(host)
    return hosts


def path_variants(path: str, query: str):
    if not path:
        return []
    paths = []
    for i, c in enumerate(path):
        if len(paths) >= 4:
            break
        if c == "/":
            paths.append(path[:i + 1])
    if paths and paths[-1] != path:
        paths.append(path)
    if query:
        paths.append(path + "?" + query)
    return paths


def expressions(url: str):
    host, path, query = canonicalize(url)
    is_ip = ipv4_normalize(host) == host if host else False
    return [h + p for h in host_variants(host, is_ip) for p in path_variants(path, query)]


def expr_hash64(expr: str) -> int:
    """First 8 bytes of SHA-256(expr) as signed big-endian int64 (Java long)."""
    return struct.unpack(">q", hashlib.sha256(expr.encode("ascii", "strict")).digest()[:8])[0]


def entry_expression(url: str, host_only: bool = False):
    """Blocklist entry: exact 'host/path[?query]' for a URL; 'host/' for a domain entry."""
    host, path, query = canonicalize(url if "://" in url else "http://" + url)
    if not host:
        return None
    if host_only:
        return host + "/"
    return host + path + ("?" + query if query else "")
