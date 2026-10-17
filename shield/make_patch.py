#!/usr/bin/env python3
"""Generates patches/0006-swiftra-shield.patch (deterministic).

Inputs: pristine upstream files @155.0.8059.80 (fetched from gitiles, or --pristine DIR) +
shield/java/** (new files, source of truth). Usage: python3 shield/make_patch.py [--check]
--check: exit 1 if the committed patch differs from what would be generated.
"""
import base64
import difflib
import os
import sys
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TAG = "155.0.8059.80"
OUT = os.path.join(ROOT, "patches", "0006-swiftra-shield.patch")
PKG = "components/safe_browsing/android/java/src/org/chromium/components/safe_browsing"
NEW = ["SwiftraShield.java", "SwiftraShieldApiHandler.java"]
BUILD = "components/safe_browsing/android/BUILD.gn"
BRIDGE = PKG + "/SafeBrowsingApiBridge.java"


def pristine(path):
    cache = os.path.join("/tmp", "pristine-" + TAG, path)
    if os.path.exists(cache):
        return open(cache, encoding="utf-8").read()
    url = f"https://chromium.googlesource.com/chromium/src/+/refs/tags/{TAG}/{path}?format=TEXT"
    txt = base64.b64decode(urllib.request.urlopen(url, timeout=60).read()).decode("utf-8")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    open(cache, "w", encoding="utf-8").write(txt)
    return txt


def sub(text, old, new):
    assert text.count(old) == 1, f"anchor not unique/missing: {old[:60]!r}"
    return text.replace(old, new)


def modified_build(t):
    return sub(t, '''    "java/src/org/chromium/components/safe_browsing/SafetyNetApiHandler.java",
  ]
  resources_package''', '''    "java/src/org/chromium/components/safe_browsing/SafetyNetApiHandler.java",
    "java/src/org/chromium/components/safe_browsing/SwiftraShield.java",
    "java/src/org/chromium/components/safe_browsing/SwiftraShieldApiHandler.java",
  ]
  resources_package''')


def modified_bridge(t):
    t = sub(t, "import org.chromium.base.TraceEvent;\n",
            "import org.chromium.base.TraceEvent;\nimport org.chromium.build.BuildConfig;\n")
    return sub(t, '''            long callbackId, String uri, int[] threatTypes, int protocol) {
        synchronized (sSafeBrowsingApiHandlerLock) {
            if (sSafeBrowsingApiHandler == null) {
                // sSafeBrowsingApiHandler can only be null in tests.''', '''            long callbackId, String uri, int[] threatTypes, int protocol) {
        synchronized (sSafeBrowsingApiHandlerLock) {
            if (sSafeBrowsingApiHandler == null && !BuildConfig.IS_CHROME_BRANDED) {
                // Swiftra: non-branded builds have no Google Play services Safe Browsing handler,
                // which upstream treats as "every URL is safe" (fail-open). Use the on-device
                // Swiftra Shield list instead so Standard protection actually protects.
                setSafeBrowsingApiHandler(new SwiftraShieldApiHandler());
            }
            if (sSafeBrowsingApiHandler == null) {
                // sSafeBrowsingApiHandler can only be null in tests.''')


def udiff(path, a, b):
    al = a.splitlines(keepends=True) if a else []
    bl = b.splitlines(keepends=True)
    lines = list(difflib.unified_diff(al, bl, "/dev/null" if not a else "a/" + path, "b/" + path, n=3))
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n\\ No newline at end of file\n"
    return "".join(lines)


def generate():
    parts = []
    b = pristine(BUILD)
    parts.append(udiff(BUILD, b, modified_build(b)))
    br = pristine(BRIDGE)
    parts.append(udiff(BRIDGE, br, modified_bridge(br)))
    for n in NEW:
        src = open(os.path.join(ROOT, "shield", "java", "org", "chromium", "components", "safe_browsing", n), encoding="utf-8").read()
        assert all(ord(c) < 128 for c in src), f"{n}: non-ASCII"
        parts.append(udiff(PKG + "/" + n, "", src))
    return "".join(parts)


def main():
    txt = generate()
    if "--check" in sys.argv:
        cur = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        print("up to date" if cur == txt else "STALE")
        return 0 if cur == txt else 1
    open(OUT, "w", encoding="utf-8").write(txt)
    print(f"wrote {OUT} ({len(txt)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
