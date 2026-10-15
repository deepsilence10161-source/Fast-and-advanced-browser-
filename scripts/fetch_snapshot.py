#!/usr/bin/env python3
"""Download an official Chromium Android snapshot from the public
`chromium-browser-snapshots` GCS bucket, verify it against the bucket's own
MD5 + CRC32C metadata, extract the APK(s) and write a provenance JSON.

Usage:
  fetch_snapshot.py --prefix Android_Arm64 --revision 1697603 --out dl/
  fetch_snapshot.py --prefix Android_Arm64 --near 1697595 --out dl/   # nearest snapshot >= position
  fetch_snapshot.py --prefix Android_Arm64 --latest --out dl/
Only stdlib is used.
"""
import argparse, base64, hashlib, json, os, sys, urllib.request, zipfile, datetime

BUCKET = "chromium-browser-snapshots"
API = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
DL = f"https://storage.googleapis.com/{BUCKET}/"

def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)

def list_revisions(prefix, start):
    """Snapshot revisions under prefix whose number starts with the given digits."""
    out, token = [], None
    while True:
        u = f"{API}?prefix={prefix}/{start}&delimiter=/&fields=prefixes,nextPageToken"
        if token: u += f"&pageToken={token}"
        d = get_json(u)
        out += [int(p.split("/")[1]) for p in d.get("prefixes", []) if p.split("/")[1].isdigit()]
        token = d.get("nextPageToken")
        if not token: return sorted(out)

def nearest_at_or_after(prefix, pos):
    s = str(pos)
    for digits in range(len(s) - 1, 2, -1):          # widen the search window gradually
        revs = [r for r in list_revisions(prefix, s[:digits]) if r >= pos]
        if revs: return revs[0]
    raise SystemExit(f"no snapshot >= {pos} under {prefix}")

def crc32c(data_iter):
    try:                                   # fast path if the optional C module is installed
        import crc32c as _c
        v = 0
        for chunk in data_iter: v = _c.crc32c(chunk, v)
        return v
    except ImportError:
        pass
    # table-driven CRC32C (Castagnoli), stdlib only
    poly, table = 0x82F63B78, []
    for i in range(256):
        c = i
        for _ in range(8): c = (c >> 1) ^ poly if c & 1 else c >> 1
        table.append(c)
    crc = 0xFFFFFFFF
    for chunk in data_iter:
        for b in chunk: crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--revision", type=int); g.add_argument("--near", type=int); g.add_argument("--latest", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-crc32c", action="store_true", help="MD5 only (CRC32C in pure python is slow)")
    a = ap.parse_args()
    if a.latest:
        with urllib.request.urlopen(DL + f"{a.prefix}/LAST_CHANGE", timeout=60) as r: rev = int(r.read().decode().strip())
    elif a.near: rev = nearest_at_or_after(a.prefix, a.near)
    else: rev = a.revision
    items = get_json(f"{API}?prefix={a.prefix}/{rev}/&fields=items(name,size,md5Hash,crc32c,generation,timeCreated)")["items"]
    zips = [i for i in items if i["name"].endswith(".zip")]
    if len(zips) != 1: raise SystemExit(f"expected one zip, got {[i['name'] for i in items]}")
    z = zips[0]; os.makedirs(a.out, exist_ok=True)
    zpath = os.path.join(a.out, os.path.basename(z["name"]))
    md5 = hashlib.md5(); sha = hashlib.sha256(); n = 0
    with urllib.request.urlopen(DL + z["name"], timeout=600) as r, open(zpath, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b); md5.update(b); sha.update(b); n += len(b)
    if n != int(z["size"]): raise SystemExit(f"size mismatch {n} != {z['size']}")
    if base64.b64encode(md5.digest()).decode() != z["md5Hash"]: raise SystemExit("MD5 mismatch")
    crc_ok = None
    if not a.skip_crc32c:
        with open(zpath, "rb") as f:
            c = crc32c(iter(lambda: f.read(1 << 20), b""))
        crc_ok = base64.b64encode(c.to_bytes(4, "big")).decode() == z["crc32c"]
        if not crc_ok: raise SystemExit("CRC32C mismatch")
    with zipfile.ZipFile(zpath) as zf:
        bad = zf.testzip()
        if bad: raise SystemExit(f"corrupt member {bad}")
        apks = [m for m in zf.namelist() if m.endswith(".apk")]
        zf.extractall(a.out, members=apks + [m for m in zf.namelist() if m.endswith(("REVISIONS", ".json"))])
    revisions = None
    try:
        with urllib.request.urlopen(DL + f"{a.prefix}/{rev}/REVISIONS", timeout=60) as r: revisions = json.loads(r.read())
    except Exception: pass
    prov = {
        "source": f"gs://{BUCKET}/{z['name']}", "download_url": DL + z["name"],
        "prefix": a.prefix, "snapshot_revision": rev, "REVISIONS": revisions,
        "zip_size": n, "zip_md5_b64_verified": z["md5Hash"], "zip_crc32c_verified": crc_ok,
        "zip_sha256": sha.hexdigest(), "gcs_generation": z.get("generation"), "gcs_time_created": z.get("timeCreated"),
        "apks": {m: hashlib.sha256(open(os.path.join(a.out, m), "rb").read()).hexdigest() for m in apks},
        "fetched_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "note": "Chromium development snapshot. NOT Google Chrome Stable.",
    }
    json.dump(prov, open(os.path.join(a.out, "provenance.json"), "w"), indent=2)
    print(json.dumps(prov, indent=2))

if __name__ == "__main__":
    main()
