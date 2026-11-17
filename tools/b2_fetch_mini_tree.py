#!/usr/bin/env python3
"""b2 strings transform को offline जाँचने के लिए Chromium 155 का छोटा "mini tree" (gitiles से) — /tmp/b2src।

patches/0002-swiftra-strings.py की GRDS सूची की हर grd + उसके (nested) <part> + xtb directories + tools/grit।
Usage: b2_fetch_mini_tree.py [dest=/tmp/b2src] [tag=155.0.8059.80]
"""
import base64
import concurrent.futures as cf
import importlib.util
import io
import os
import re
import sys
import tarfile
import urllib.request

DEST = sys.argv[1] if len(sys.argv) > 1 else "/tmp/b2src"
TAG = sys.argv[2] if len(sys.argv) > 2 else "155.0.8059.80"
G = f"https://chromium.googlesource.com/chromium/src/+/refs/tags/{TAG}/"
A = f"https://chromium.googlesource.com/chromium/src/+archive/refs/tags/{TAG}/"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def http(url, tries=5):
    for t in range(tries):
        try:
            return urllib.request.urlopen(url, timeout=120).read()
        except Exception:
            if t == tries - 1:
                raise
            import time; time.sleep(5 * (t + 1))


def get_file(rel):
    p = os.path.join(DEST, rel)
    if os.path.exists(p):
        return open(p, encoding="utf-8").read()
    txt = base64.b64decode(http(G + rel + "?format=TEXT")).decode("utf-8")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(txt)
    return txt


def get_dir(rel):
    d = os.path.join(DEST, rel)
    if os.path.isdir(d) and os.listdir(d):
        return
    os.makedirs(d, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(http(A + rel + ".tar.gz")), mode="r:gz") as t:
        t.extractall(d, filter="data")


def main():
    spec = importlib.util.spec_from_file_location("rb", os.path.join(ROOT, "patches", "0002-swiftra-strings.py"))
    rb = importlib.util.module_from_spec(spec); spec.loader.exec_module(rb)
    grds = [g if isinstance(g, str) else g[0] for g in rb.GRDS]
    get_dir("tools/grit")
    todo, seen, xdirs = list(grds), set(), set()
    while todo:
        batch = [t for t in todo if t not in seen]; todo = []
        seen.update(batch)
        with cf.ThreadPoolExecutor(8) as ex:
            for rel, txt in zip(batch, ex.map(get_file, batch)):
                base = os.path.dirname(rel)
                todo += [os.path.normpath(os.path.join(base, p)) for p in re.findall(r'<part\s+file="([^"]+)"', txt)]
                if rel in grds:
                    xdirs |= {os.path.dirname(os.path.normpath(os.path.join(base, x)))
                              for x in re.findall(r'<file\s+path="([^"]+\.xtb)"', txt)}
    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(get_dir, sorted(xdirs)))
    print(f"mini tree: {DEST} — {len(seen)} grd/grdp, xtb dirs: {sorted(xdirs)}")


if __name__ == "__main__":
    main()
