#!/usr/bin/env python3
"""Chromium source पर इस परियोजना के patches लगाना — staged build के साथ सुरक्षित।

समस्या: हर stage pristine src (patch-रहित pack) restore करता है और patches फिर से लगाता है।
अगर patched फ़ाइलों की mtime हर बार "अभी" हो, तो ninja हर stage में उनके dependents दोबारा बनाएगा।
अगर कोई patch हटाया जाए, तो restore हुई मूल फ़ाइल की पुरानी mtime के कारण ninja पुराना (patched) output रख लेगा।

हल:
  * series + patch फ़ाइलों + patches/args.gn का hash निकालें।
  * hash पिछले stage जैसा  -> वही epoch (पहली बार लगाने का समय) फिर से patched फ़ाइलों पर लगाएँ।
  * hash बदला             -> epoch = अभी; नई और पिछली (हटाई गई) दोनों सूचियों की फ़ाइलों पर लगाएँ।
  * patches न हों          -> hash "none" (पुरानी state के साथ संगत)।

Overlay (binary assets, जैसे launcher icon PNG — जो diff से नहीं बदल सकते):
  patches/overlay/<src-सापेक्ष path> की हर फ़ाइल src की उसी (पहले से मौजूद) फ़ाइल की जगह कॉपी होती है।
  * लक्ष्य फ़ाइल src में न हो -> त्रुटि (गलत path / upstream में नाम बदला — चुपचाप नई फ़ाइल नहीं)।
  * symlink / ".." -> त्रुटि। overlay पहले, फिर series patches (patch overlay वाली फ़ाइल पर भी लग सकता है)।
  * overlay की फ़ाइलें (path+content) hash में और touched-files सूची में शामिल।

Usage: patches.py apply <src-dir> <patch-dir> <prev-json|-> <out-json>
            prev-json = पिछले stage का progress.json (उसकी "patches" key) या "-"
       patches.py args  <patch-dir>          # patches/args.gn (न हो तो खाली)
       patches.py hash  <patch-dir>          # series+patches+args.gn+overlay का hash ("none" = कुछ नहीं)
Exit 0 = सफल; 1 = patch नहीं लगा / अमान्य।
"""
import hashlib, json, os, shutil, subprocess, sys, time


def read_series(pdir):
    s = os.path.join(pdir, "series")
    if not os.path.isfile(s):
        return []
    out = []
    for line in open(s, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def extra_args(pdir):
    p = os.path.join(pdir, "args.gn")
    return open(p, encoding="utf-8").read() if os.path.isfile(p) else ""


def overlay_files(pdir):
    """patches/overlay के अंदर की फ़ाइलें (src-सापेक्ष, क्रमबद्ध)। अमान्य प्रविष्टि -> ValueError।"""
    root = os.path.join(pdir, "overlay")
    if not os.path.isdir(root):
        return []
    out = []
    for dp, dns, fns in os.walk(root, followlinks=False):
        for d in dns:
            if os.path.islink(os.path.join(dp, d)):
                raise ValueError(f"overlay में symlink: {os.path.relpath(os.path.join(dp, d), root)}")
        for f in fns:
            fp = os.path.join(dp, f)
            rel = os.path.relpath(fp, root)
            if os.path.islink(fp) or not os.path.isfile(fp):
                raise ValueError(f"overlay में अमान्य फ़ाइल (symlink/विशेष): {rel}")
            out.append(rel.replace(os.sep, "/"))
    return sorted(out)


def series_hash(pdir, series):
    args = extra_args(pdir)
    ov = overlay_files(pdir)
    if not series and not args.strip() and not ov:
        return "none"
    h = hashlib.sha256()
    for name in series:
        h.update(name.encode() + b"\0" + open(os.path.join(pdir, name), "rb").read() + b"\0")
    h.update(b"args\0" + args.encode())
    if ov:  # overlay न हो तो hash पुराने (overlay-रहित) सूत्र जैसा ही — मौजूदा state संगत
        for rel in ov:
            h.update(b"overlay\0" + rel.encode() + b"\0" + open(os.path.join(pdir, "overlay", rel), "rb").read() + b"\0")
    return h.hexdigest()


def patched_files(path):
    files = []
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("+++ "):
            f = line[4:].split("\t")[0].strip()
            if f == "/dev/null":
                continue
            if f.startswith("b/"):
                f = f[2:]
            files.append(f)
    return files


def apply(src, pdir, prev_json, out_json, now=None):
    series = read_series(pdir)
    for name in series:
        if "/" in name or name.startswith(".") or not os.path.isfile(os.path.join(pdir, name)):
            print(f"[patches] अमान्य series प्रविष्टि: {name}", file=sys.stderr)
            return 1
    try:
        ov = overlay_files(pdir)
        h = series_hash(pdir, series)
    except ValueError as e:
        print(f"[patches] {e}", file=sys.stderr)
        return 1
    prev = {"hash": "none", "epoch": 0, "files": []}
    if prev_json != "-" and os.path.isfile(prev_json):
        try:
            d = json.load(open(prev_json))
            # progress.json (out state के साथ परमाणु रूप से) में "patches" key; पुरानी state में नहीं = "none"
            if "patches" in d or "out_prefix" in d:
                d = d.get("patches") or {}
            prev.update({k: d[k] for k in ("hash", "epoch", "files") if k in d})
        except ValueError:
            pass
    files = []
    for rel in ov:
        dst = os.path.join(src, rel)
        real_src = os.path.realpath(src)
        if not os.path.realpath(dst).startswith(real_src + os.sep) or not os.path.isfile(dst):
            print(f"[patches] overlay लक्ष्य src में मौजूद नहीं: {rel}", file=sys.stderr)
            return 1
        shutil.copyfile(os.path.join(pdir, "overlay", rel), dst)
        files.append(rel)
    for name in series:
        p = os.path.join(pdir, name)
        r = subprocess.run(["patch", "-d", src, "-p1", "--forward", "--batch", "--no-backup-if-mismatch", "-i", p],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[patches] {name} नहीं लगा:\n{r.stdout}{r.stderr}", file=sys.stderr)
            return 1
        files += patched_files(p)
    files = sorted(set(files))
    if h == prev["hash"] and (prev.get("epoch") or h == "none"):
        epoch, touch = prev["epoch"], files
        changed = False
    else:
        epoch = int(now if now is not None else time.time())
        touch = sorted(set(files) | set(prev.get("files", [])))
        changed = True
    for f in touch:
        fp = os.path.join(src, f)
        if os.path.exists(fp):
            os.utime(fp, (epoch, epoch))
    json.dump({"hash": h, "epoch": epoch, "files": files, "series": series, "overlay": ov, "changed": changed},
              open(out_json, "w"), indent=1)
    print(f"[patches] {len(series)} patches, {len(ov)} overlay, {len(files)} files, hash={h[:12]}, changed={changed}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "args":
        sys.stdout.write(extra_args(sys.argv[2]))
        sys.exit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "hash":
        print(series_hash(sys.argv[2], read_series(sys.argv[2])))
        sys.exit(0)
    if len(sys.argv) != 6 or sys.argv[1] != "apply":
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(apply(*sys.argv[2:6]))
