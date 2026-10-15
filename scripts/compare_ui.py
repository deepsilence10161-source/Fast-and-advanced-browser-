#!/usr/bin/env python3
"""Compare two ui_capture.py outputs screen-by-screen.

For every screen key captured for the reference:
  * element parity: resource-id suffixes, visible texts, content-descriptions
    (Jaccard similarity + exact missing/extra lists; brand words normalised
    separately so 'Chrome' vs 'Chromium' is reported, not hidden)
  * pixel difference: grayscale mean-absolute-difference on a 270x600
    downscale, status bar (top 3.5%) excluded
  * side-by-side evidence image (reference | artifact)
Status values follow the project rules: verified / mismatch / blocked / not-tested.
Because the emulator reference is NOT the current Chrome Stable, parity against
Stable is always reported as `not-tested` here.

Usage: compare_ui.py --ref out/chrome_ref --art out/chromium_arm64 --out reports/ui-compare/arm64 [--stable 155.0.8059.80]
Requires Pillow.
"""
import argparse, glob, json, os, re
from PIL import Image, ImageChops, ImageDraw, ImageStat

BRAND = re.compile(r"\b(Google Chrome|Chromium|Chrome)\b")

def load(d):
    meta = json.load(open(os.path.join(d, "meta.json"))) if os.path.exists(os.path.join(d, "meta.json")) else {}
    screens = {}
    for j in sorted(glob.glob(os.path.join(d, "*.json"))):
        b = os.path.basename(j)
        if b in ("meta.json", "provenance.json"):
            continue
        s = json.load(open(j))
        if "key" not in s or "nodes" not in s: continue  # e.g. chat_fixture.json
        screens[s["key"]] = s
    return meta, screens

def sig(nodes, own_pkgs):
    ids, texts, descs = set(), set(), set()
    for n in nodes:
        if n.get("pkg") and n["pkg"] not in own_pkgs:
            continue                       # ignore system UI / keyboard / other apps
        if n["id"]:
            ids.add(n["id"].split(":id/")[-1])
        if n["text"]:
            texts.add(n["text"].strip())
        if n["desc"]:
            descs.add(n["desc"].strip())
    return ids, texts, descs

def norm(s):
    return {BRAND.sub("<BRAND>", x) for x in s}

def jac(a, b):
    return 1.0 if not a and not b else len(a & b) / max(1, len(a | b))

def pixdiff(pa, pb):
    A = Image.open(pa).convert("L"); B = Image.open(pb).convert("L")
    def crop(im):
        w, h = im.size; return im.crop((0, int(h * 0.035), w, h)).resize((270, 600))
    A, B = crop(A), crop(B)
    return ImageStat.Stat(ImageChops.difference(A, B)).mean[0] / 255.0

def side_by_side(pa, pb, out, ta, tb):
    A = Image.open(pa).convert("RGB"); B = Image.open(pb).convert("RGB")
    h = 900
    A = A.resize((int(A.width * h / A.height), h)); B = B.resize((int(B.width * h / B.height), h))
    W = Image.new("RGB", (A.width + B.width + 30, h + 40), "white")
    W.paste(A, (0, 40)); W.paste(B, (A.width + 30, 40))
    d = ImageDraw.Draw(W); d.text((5, 10), ta, fill="black"); d.text((A.width + 35, 10), tb, fill="black")
    W.save(out, optimize=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True); ap.add_argument("--art", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--stable", default="155.0.8059.80")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    rm, rs = load(a.ref); am, as_ = load(a.art)
    rp = {rm.get("package")}; apk = {am.get("package")}
    rows = []
    for key, r in rs.items():
        row = {"screen": key, "ref_note": r.get("note", "")}
        x = as_.get(key)
        if not x:
            row.update(status="blocked", reason="artifact journey did not reach this screen"); rows.append(row); continue
        ri, rt, rd = sig(r["nodes"], rp); ai, at, ad = sig(x["nodes"], apk)
        row.update(
            id_jaccard=round(jac(ri, ai), 3), text_jaccard_brand_normalised=round(jac(norm(rt), norm(at)), 3),
            desc_jaccard_brand_normalised=round(jac(norm(rd), norm(ad)), 3),
            ids_missing_in_artifact=sorted(ri - ai), ids_extra_in_artifact=sorted(ai - ri),
            texts_missing_in_artifact=sorted(norm(rt) - norm(at)), texts_extra_in_artifact=sorted(norm(at) - norm(rt)),
            descs_missing_in_artifact=sorted(norm(rd) - norm(ad)), descs_extra_in_artifact=sorted(norm(ad) - norm(rd)),
            brand_strings_ref=sorted({t for t in rt | rd if BRAND.search(t)}),
            brand_strings_artifact=sorted({t for t in at | ad if BRAND.search(t)}),
            foreground_ref=r.get("foreground"), foreground_artifact=x.get("foreground"),
        )
        try:
            row["pixel_mad"] = round(pixdiff(os.path.join(a.ref, r["png"]), os.path.join(a.art, x["png"])), 4)
            side_by_side(os.path.join(a.ref, r["png"]), os.path.join(a.art, x["png"]), os.path.join(a.out, f"{key}.png"),
                         f"REFERENCE {rm.get('package')} {rm.get('versionName')}", f"ARTIFACT {am.get('package')} {am.get('versionName')}")
            row["evidence"] = f"{key}.png"
        except Exception as e:
            row["pixel_mad"] = None; row["image_error"] = str(e)
        exact = (row["id_jaccard"] == 1 and row["text_jaccard_brand_normalised"] == 1 and row["desc_jaccard_brand_normalised"] == 1
                 and (row["pixel_mad"] or 1) < 0.01)
        row["status_vs_emulator_reference"] = "verified" if exact else "mismatch"
        row["status_vs_chrome_stable"] = f"not-tested (reference is {rm.get('versionName')}, Stable is {a.stable})"
        rows.append(row)
    for key in as_:
        if key not in rs:
            rows.append({"screen": key, "status_vs_emulator_reference": "not-tested", "reason": "only artifact reached this screen"})
    summary = {"reference": {k: rm.get(k) for k in ("package", "versionName", "primaryCpuAbi", "android_release", "sdk", "model", "wm_size", "wm_density", "font_scale", "navigation_mode", "reached_browser_ui", "pss_kb_after_example", "timings", "crash_buffer_lines")},
               "artifact": {k: am.get(k) for k in ("package", "versionName", "primaryCpuAbi", "android_release", "sdk", "model", "wm_size", "wm_density", "font_scale", "navigation_mode", "reached_browser_ui", "pss_kb_after_example", "timings", "crash_buffer_lines")},
               "chrome_stable_target": a.stable, "screens": rows}
    json.dump(summary, open(os.path.join(a.out, "comparison.json"), "w"), indent=2, ensure_ascii=False)
    # markdown
    L = [f"# UI comparison: {rm.get('package')} {rm.get('versionName')} (emulator reference) vs {am.get('package')} {am.get('versionName')} (artifact)", "",
         f"Chrome Stable target: **{a.stable}**. Emulator reference version differs, so every row is `not-tested` against Stable.", "",
         "| screen | status vs emulator ref | id J | text J | desc J | pixel MAD | evidence |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['screen']} | {r.get('status_vs_emulator_reference', r.get('status'))} | {r.get('id_jaccard','-')} | {r.get('text_jaccard_brand_normalised','-')} | {r.get('desc_jaccard_brand_normalised','-')} | {r.get('pixel_mad','-')} | {r.get('evidence', r.get('reason',''))} |")
    L += ["", "Details (missing/extra elements) are in `comparison.json`."]
    open(os.path.join(a.out, "COMPARISON.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))

if __name__ == "__main__":
    main()
