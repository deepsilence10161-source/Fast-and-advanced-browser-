#!/usr/bin/env python3
"""Build swiftra-update.json for the in-app update channel (patch 0020, UpdateStatusProvider.SwiftraUpdate).

  update_manifest.py --sums SHA256SUMS.txt --times '{"arm64": <ms>, "x64": <ms>}' [--old old.json] --out new.json

One entry per APK the rolling release holds now: url (fixed latest link), sha256, published_ms (asset upload time).
An entry whose sha256 did not change keeps its old published_ms, so the app never re-offers the APK it already has.
The workflow signs "swiftra-update-v1\\n" + the file bytes with the Shield list key (domain-separated from shield.swz).
"""
import argparse
import json
import re

REPO = "deepsilence10161-source/Fast-and-advanced-browser-"
URL = "https://github.com/" + REPO + "/releases/latest/download/Swiftra-{abi}.apk"


def build(sums_text, times, old=None):
    old_apks = (old or {}).get("apks", {}) if (old or {}).get("v") == 1 else {}
    apks = {}
    for line in sums_text.splitlines():
        m = re.match(r"^([0-9a-f]{64})\s+\*?Swiftra-(arm64|x64)\.apk$", line.strip())
        if not m:
            continue
        sha, abi = m.groups()
        prev = old_apks.get(abi) or {}
        if prev.get("sha256") == sha and int(prev.get("published_ms", 0)) > 0:
            apks[abi] = prev
        else:
            if int(times.get(abi, 0)) <= 0:
                raise SystemExit(f"no upload time for {abi}")
            apks[abi] = {"url": URL.format(abi=abi), "sha256": sha, "published_ms": int(times[abi])}
    return {"v": 1, "apks": dict(sorted(apks.items()))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sums", required=True)
    ap.add_argument("--times", required=True)
    ap.add_argument("--old")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    old = None
    if a.old:
        try:
            old = json.load(open(a.old))
        except (OSError, ValueError):
            old = None
    m = build(open(a.sums).read(), json.loads(a.times), old)
    with open(a.out, "w") as f:
        json.dump(m, f, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps(m, sort_keys=True))


if __name__ == "__main__":
    main()
