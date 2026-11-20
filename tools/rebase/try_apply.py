#!/usr/bin/env python3
"""Dry-run feasibility check for moving the patch series to another Chromium tag.
Fetches only the files our patches touch (raw.githubusercontent.com/chromium/chromium/<tag>/<path>), applies each
patch in series order with `patch --fuzz=2` and reports failed hunks. Source integrity/feasibility only: no build."""
import sys, os, json, subprocess, urllib.request, urllib.error, concurrent.futures as cf, shutil, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import patches as P

def fetch(tag, f):
    u = f"https://raw.githubusercontent.com/chromium/chromium/{tag}/{f}"
    for _ in range(4):
        try:
            return urllib.request.urlopen(u, timeout=40).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
    return b"ERR"

def main(tag, work):
    order, files = [], set()
    for d in ("patches", "patches/personal"):
        for name in P.read_series(str(ROOT / d)):
            if name.startswith("0000"):
                continue
            if not name.endswith(".patch"):
                print("TRANSFORM-SCRIPT (needs a separate check):", name); continue
            order.append(ROOT / d / name); files.update(P.patched_files(str(order[-1])))
    files = sorted(f for f in files if not f.startswith("/dev"))
    root = pathlib.Path(work); shutil.rmtree(root, ignore_errors=True)
    missing, err = [], []
    with cf.ThreadPoolExecutor(8) as ex:
        for f, b in zip(files, ex.map(lambda f: fetch(tag, f), files)):
            if b == b"ERR": err.append(f)
            elif b is None: missing.append(f)
            else:
                p = root / f; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
    print(f"tag={tag} files={len(files)} absent_at_tag(new files or removed)={len(missing)} fetch_errors={len(err)}")
    rep = {}
    for pf in order:
        r = subprocess.run(["patch", "-p1", "--batch", "--forward", "--no-backup-if-mismatch", "-i", str(pf)], cwd=root, capture_output=True, text=True)
        bad = [l for l in r.stdout.splitlines() if "FAILED" in l or "No file to patch" in l]
        rep[pf.name] = {"rc": r.returncode, "failed": bad}
        print(f"{pf.name[:58]:58} rc={r.returncode} failed={len(bad)}")
        for l in bad[:8]: print("     ", l[:150])
    json.dump({"tag": tag, "missing": missing, "errors": err, "patches": rep}, open(root / "REPORT.json", "w"), indent=1)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
