#!/usr/bin/env python3
"""stdin -> stdout: असली token और GitHub token patterns को ***REDACTED*** से बदलता है।"""
import re, sys
PATTERNS = [
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"gh[pousr]_[A-Za-z0-9]{30,}",
    r"x-access-token:[^@\s]+",
    r"(?i)(authorization:\s*(?:bearer|basic|token)\s+)[A-Za-z0-9._~+/=-]+",
]
exact = []
try:
    t = open("/home/user/.secrets/gh_token").read().strip()
    if t:
        import base64
        exact = [t, base64.b64encode(f"x-access-token:{t}".encode()).decode()]
except OSError:
    pass
rx = [re.compile(p) for p in PATTERNS]
data = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
for e in exact:
    data = data.replace(e, "***REDACTED***")
for r in rx:
    data = r.sub(lambda m: (m.group(1) if m.groups() else "") + "***REDACTED***", data)
sys.stdout.buffer.write(data.encode("utf-8", "surrogateescape"))
