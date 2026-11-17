#!/usr/bin/env python3
"""Leak scan for every secret in the vault: GitHub token (plain + base64 forms), release keystore password,
private-key bodies (PEM chunks), binary keystore (sha256 + a 48-byte chunk).

Prints only counts, paths and secret *labels*; a secret value is never printed.

Usage:
  leakscan.py paths <dir-or-file>...      # walk files (zip files are opened and their members scanned)
  leakscan.py ci-logs <owner/repo> [N]    # download the logs of the latest N completed Actions runs and scan them
Exit 0 = nothing found, 1 = a leak was found, 2 = the scan itself could not run.
"""
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile

VAULT = os.path.expanduser("~/.secrets")
SKIP_DIRS = {".secrets", "node_modules", ".git", "ms-playwright", "__pycache__", ".cache"}
MAX_FILE = 300 * 1024 * 1024


def _read(name):
    p = os.path.join(VAULT, name)
    try:
        with open(p, "rb") as f:
            return f.read()
    except OSError:
        return None


def private_key_needles(name, pem):
    """Needles from the *private* part of a PEM key only. A private-key PEM also carries the public key (SEC1 EC:
    the second half is the public point; RSA: the modulus), and the public key is meant to ship (e.g. the Shield
    verification key in SwiftraShieldApiHandler.java), so every 24-char window whose bytes also occur in the public
    key DER is dropped. Also: the raw private scalar / exponent bytes and their hex."""
    body = b"".join(l.strip() for l in pem.splitlines() if l and not l.startswith(b"-----"))
    try:
        der = base64.b64decode(body)
    except ValueError:
        return []
    with tempfile.NamedTemporaryFile(dir=VAULT, suffix=".pem") as t:     # stays inside the 700 vault
        t.write(pem)
        t.flush()
        pub = subprocess.run(["openssl", "pkey", "-in", t.name, "-pubout", "-outform", "der"],
                             capture_output=True).stdout
        txt = subprocess.run(["openssl", "pkey", "-in", t.name, "-noout", "-text"], capture_output=True,
                             text=True).stdout
    out = []
    for off in range(0, len(body) - 24, 8):                # 24 chars = 18 bytes, 4-char aligned
        win = der[off // 4 * 3: off // 4 * 3 + 18]
        if pub and win and win not in pub and all(win[i:i + 8] not in pub for i in range(0, 11)):
            out.append((f"{name}-private-pem", body[off:off + 24]))
    # the private scalar (EC "priv:") or exponent (RSA "privateExponent:"), as raw bytes and hex
    m = re.search(r"(?:priv|privateExponent):\s*\n((?:\s+[0-9a-f:]+\n)+)", txt)
    if m:
        hx = re.sub(r"[^0-9a-f]", "", m.group(1)).lstrip("0")
        hx = hx if len(hx) % 2 == 0 else "0" + hx
        raw = bytes.fromhex(hx)
        if len(raw) >= 16:
            out += [(f"{name}-private-scalar", raw[:24]), (f"{name}-private-scalar-hex", hx[:40].encode())]
    return out


def needles():
    """[(label, bytes)] - substrings whose presence anywhere outside the vault means a leak."""
    out = []
    tok = (_read("gh_token") or b"").strip()
    if tok:
        out.append(("github-token", tok))
        out.append(("github-token-b64", base64.b64encode(tok)[:40]))
        out.append(("github-token-basic-auth-b64", base64.b64encode(b"x-access-token:" + tok)[:40]))
    ksp = (_read("swiftra-ks-pass") or b"").strip()
    if len(ksp) >= 12:
        out.append(("keystore-password", ksp))
    for name in sorted(os.listdir(VAULT)) if os.path.isdir(VAULT) else []:
        data = _read(name) or b""
        if b"PRIVATE KEY-----" in data:
            out += private_key_needles(name, data)
    p12 = _read("swiftra-release.p12")
    if p12 and len(p12) > 400:
        out.append(("release-keystore-bytes", p12[200:248]))
        out.append(("release-keystore-b64", base64.b64encode(p12)[300:348]))
    return [(l, n) for l, n in out if n]


def p12_hash():
    p12 = _read("swiftra-release.p12")
    return hashlib.sha256(p12).hexdigest() if p12 else None


def scan_bytes(data, ns):
    return sorted({label for label, n in ns if n in data})


notes = []


def scan_paths(roots, ns):
    hits, files = [], 0
    kh = p12_hash()
    for root in roots:
        walk = [(os.path.dirname(root), [], [os.path.basename(root)])] if os.path.isfile(root) else os.walk(root)
        for d, dirs, fs in walk:
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for fn in fs:
                p = os.path.join(d, fn)
                try:
                    if os.path.islink(p) or not os.path.isfile(p) or os.path.getsize(p) > MAX_FILE:
                        continue
                    with open(p, "rb") as f:
                        data = f.read()
                except OSError:
                    continue
                files += 1
                found = []
                is_zip = False
                if data[:4] == b"PK\x03\x04":
                    try:
                        with zipfile.ZipFile(io.BytesIO(data)) as z:
                            is_zip = True
                            for m in z.infolist():
                                if m.file_size > MAX_FILE:
                                    continue
                                f = scan_bytes(z.read(m), ns)
                                if f and m.filename.split("/")[0] == ".secrets":
                                    # a backup of the vault itself (platform workspace-restore archive)
                                    notes.append((p, m.filename))
                                else:
                                    found += [f"{x} (in {m.filename})" for x in f]
                    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError):
                        is_zip = False
                if not is_zip:
                    found = scan_bytes(data, ns)
                if kh and hashlib.sha256(data).hexdigest() == kh:
                    found.append("release-keystore-copy")
                if found:
                    hits.append((p, sorted(set(found))))
    return files, hits


def gh(path, binary=False):
    cmd = [os.path.join(VAULT, "gh.sh"), path, "-L"]
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    return r.stdout if binary else json.loads(r.stdout or b"{}")


def scan_ci_logs(repo, n, ns):
    runs = gh(f"/repos/{repo}/actions/runs?status=completed&per_page={n}").get("workflow_runs", [])
    hits, scanned = [], 0
    for run in runs:
        # job logs as plain text (the run-level zip endpoint needs a binary Accept header that gh.sh overrides)
        jobs = gh(f"/repos/{repo}/actions/runs/{run['id']}/jobs?per_page=50").get("jobs", [])
        for j in jobs:
            data = gh(f"/repos/{repo}/actions/jobs/{j['id']}/logs", binary=True)
            if not data:
                continue
            scanned += 1
            found = scan_bytes(data, ns)
            if found:
                hits.append((f"run {run['id']} job {j['id']} ({run['name'][:40]})", found))
    return len(runs), scanned, hits


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    ns = needles()
    if not ns:
        print("LEAKSCAN: vault empty or unreadable - nothing to look for")
        return 2
    labels = sorted({l for l, _ in ns})
    if sys.argv[1] == "paths":
        files, hits = scan_paths(sys.argv[2:], ns)
        for p, f in hits:
            print(f"LEAK  {p}: {', '.join(f)}")
        for z in sorted({z for z, _ in notes}):
            print(f"NOTE  {z}: vault copy only (members under .secrets/), no secret elsewhere in it")
        print(f"LEAKSCAN paths: {files} files, {len(ns)} needles ({', '.join(labels)}), {len(hits)} leaks")
    elif sys.argv[1] == "ci-logs":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        runs, jobs, hits = scan_ci_logs(sys.argv[2], n, ns)
        for p, f in hits:
            print(f"LEAK  {p}: {', '.join(f)}")
        if not jobs:
            print("LEAKSCAN ci-logs: no job log could be read")
            return 2
        print(f"LEAKSCAN ci-logs: {runs} runs, {jobs} job logs, {len(ns)} needles, {len(hits)} leaks")
    else:
        print(__doc__)
        return 2
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
