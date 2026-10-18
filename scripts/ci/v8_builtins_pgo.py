#!/usr/bin/env python3
"""Fetch V8's builtins PGO profiles for the checked-out V8 (arm64 PGO build).

Why: with chrome_pgo_phase = 2, V8's mksnapshot reads v8/tools/builtins-pgo/profiles/<cpu>.profile (official Chrome
does the same). Chromium's DEPS fetches them only when `checkout_pgo_profiles` is set (hook "Fetch PGO profiles for
V8 builtins" -> v8/tools/builtins-pgo/download_profiles.py, gsutil). Swiftra keeps that var off and takes Chrome's
profile/orderfile from CIPD, so run 39149165491 stopped in ninja: x64.profile "missing and no known rule to make it".

What: the same public bucket and layout as download_profiles.py (gs://chromium-v8-builtins-pgo/by-version/<V8
version>/*), read over the anonymous GCS JSON API (no gsutil, no credentials). Every object is checked against the
md5 that GCS lists, and meta.json's revision must equal the v8_revision in src/DEPS (the --check-v8-revision rule):
otherwise exit 1, never a silently mismatched profile. Files get a fixed mtime so a re-fetch in a later stage does not
make ninja rebuild the snapshot.

Usage: v8_builtins_pgo.py <chromium src dir>
"""
import base64
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request

BUCKET = "chromium-v8-builtins-pgo"
FIXED_MTIME = 1700000000
VERSION_RE = (r"#define V8_MAJOR_VERSION\s+(\d+).*#define V8_MINOR_VERSION\s+(\d+).*"
              r"#define V8_BUILD_NUMBER\s+(\d+).*#define V8_PATCH_LEVEL\s+(\d+)")


def v8_version(src):
    text = open(os.path.join(src, "v8", "include", "v8-version.h")).read()
    m = re.search(VERSION_RE, text, re.S)
    if not m:
        raise SystemExit("v8-version.h: version not found")
    return ".".join(m.groups())


def deps_v8_revision(src):
    m = re.search(r"'v8_revision':\s*'([0-9a-f]{40})'", open(os.path.join(src, "DEPS")).read())
    if not m:
        raise SystemExit("DEPS: v8_revision not found")
    return m.group(1)


def get(url, timeout=120):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            err = e
    raise SystemExit(f"fetch failed: {url}: {err}")


def listing(prefix):
    q = urllib.parse.urlencode({"prefix": prefix})
    items = json.loads(get(f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?{q}")).get("items", [])
    return [(i["name"], int(i["size"]), i.get("md5Hash", "")) for i in items]


def md5_b64(data):
    return base64.b64encode(hashlib.md5(data).digest()).decode()


def main(src):
    ver, rev = v8_version(src), deps_v8_revision(src)
    if ver.split(".")[2:] == ["0", "0"]:
        raise SystemExit(f"V8 {ver}: no profiles exist for x.y.0.0 versions")
    prefix = f"by-version/{ver}/"
    objs = listing(prefix)
    if not any(n.endswith("/meta.json") for n, _, _ in objs):
        raise SystemExit(f"no meta.json under gs://{BUCKET}/{prefix}")
    out = os.path.join(src, "v8", "tools", "builtins-pgo", "profiles")
    os.makedirs(out, exist_ok=True)
    for name, size, md5 in objs:
        dest = os.path.join(out, name[len(prefix):])
        if os.path.isfile(dest) and os.path.getsize(dest) == size and md5_b64(open(dest, "rb").read()) == md5:
            data = None                                      # already there, identical: keep it (and its mtime)
        else:
            data = get(f"https://storage.googleapis.com/{BUCKET}/{urllib.parse.quote(name)}")
            if len(data) != size or md5_b64(data) != md5:
                raise SystemExit(f"{name}: size/md5 mismatch")
            with open(dest, "wb") as f:
                f.write(data)
        os.utime(dest, (FIXED_MTIME, FIXED_MTIME))
        print(f"v8_builtins_pgo {name[len(prefix):]} bytes={size} md5={md5} {'fetched' if data else 'kept'}")
    meta = json.load(open(os.path.join(out, "meta.json")))
    if meta.get("revision") != rev or meta.get("version") != ver:
        raise SystemExit(f"meta.json is for {meta.get('version')} @ {meta.get('revision')}, checkout is {ver} @ {rev}")
    print(f"v8_builtins_pgo OK version={ver} revision={rev[:12]} profiles={meta.get('profile')}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
