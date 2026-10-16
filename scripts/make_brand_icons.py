#!/usr/bin/env python3
"""Swiftra launcher icons — शुद्ध geometric (कोई font/तीसरे पक्ष की artwork नहीं), PIL से।
Output: patches/overlay/chrome/android/java/res_chromium_base/{mipmap-*,drawable}/... (Chromium के मौजूदा
icon resources की जगह — वही नाम, वही आकार)। Run: python3 scripts/make_brand_icons.py
"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(__file__), "..", "patches", "overlay", "chrome", "android", "java", "res_chromium_base")
C1, C2 = (20, 82, 245), (0, 191, 166)          # गहरा नीला -> teal
# glyph: दो chevrons (">>") इकाई-वर्ग में
CHEV_A = [(0.02, 0.10), (0.30, 0.10), (0.62, 0.50), (0.30, 0.90), (0.02, 0.90), (0.34, 0.50)]
CHEV_B = [(x + 0.36, y) for x, y in CHEV_A]
DENS = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
SS = 4  # supersampling


def gradient(n):
    im = Image.new("RGB", (n, n)); px = im.load()
    for y in range(n):
        for x in range(n):
            t = (x + y) / (2 * (n - 1))
            px[x, y] = tuple(int(C1[i] + (C2[i] - C1[i]) * t) for i in range(3))
    return im


def glyph(n, box, ox, oy, alpha_b=200):
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    sc = lambda pts: [(ox + x * box, oy + y * box) for x, y in pts]
    d.polygon(sc(CHEV_B), fill=(255, 255, 255, alpha_b))
    d.polygon(sc(CHEV_A), fill=(255, 255, 255, 255))
    return im


def layered(px):
    """108dp canvas, glyph 44dp केंद्र में (safe zone 66dp के भीतर)।
    Chromium का resource ढाँचा (res_chromium_base, drawable-v26):
      ic_launcher       = <background @android:color/white> + <foreground layered_app_icon>
      ic_launcher_round = <background layered_app_icon_background> + <foreground पारदर्शी shape>
    इसलिए दोनों PNG में *पूरा* icon (gradient + glyph) होना ज़रूरी है — सिर्फ़ foreground में glyph रखने से
    Pixel launcher (roundIcon) पर glyph गायब हो जाता है (x64 emulator launcher_drawer.png, run 38904972738)।
    """
    n = px * SS; box = 44 / 108 * n; o = (n - box) / 2
    full = gradient(n).convert("RGBA")
    full.alpha_composite(glyph(n, box, o, o))
    full = full.resize((px, px), Image.LANCZOS)
    return full.copy(), full.convert("RGB")


def legacy(px):             # 48dp: गोल gradient + glyph
    n = px * SS
    base = gradient(n).convert("RGBA")
    mask = Image.new("L", (n, n), 0); ImageDraw.Draw(mask).ellipse((n * 0.02, n * 0.02, n * 0.98, n * 0.98), fill=255)
    box = n * 0.52; o = (n - box) / 2
    base.alpha_composite(glyph(n, box, o, o))
    out = Image.new("RGBA", (n, n), (0, 0, 0, 0)); out.paste(base, (0, 0), mask)
    return out.resize((px, px), Image.LANCZOS)


def vector_xml():           # monochrome (themed) icon: 90x90 viewport, glyph 27..63 (Chromium जैसा क्षेत्र)
    def path(pts):
        p = [(27 + x * 36, 27 + y * 36) for x, y in pts]
        return "M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in p) + "Z"
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!-- Swiftra themed (monochrome) launcher icon. Original geometric artwork for this project. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="90dp"
    android:height="90dp"
    android:viewportWidth="90"
    android:viewportHeight="90">
    <path android:pathData="{path(CHEV_A)}" android:fillColor="#000000"/>
    <path android:pathData="{path(CHEV_B)}" android:fillColor="#000000"/>
</vector>
'''


def main():
    for d, f in DENS.items():
        out = os.path.join(ROOT, f"mipmap-{d}"); os.makedirs(out, exist_ok=True)
        fg, bg = layered(round(108 * f))
        fg.save(os.path.join(out, "layered_app_icon.png"), optimize=True)
        bg.save(os.path.join(out, "layered_app_icon_background.png"), optimize=True)
        legacy(round(48 * f)).save(os.path.join(out, "app_icon.png"), optimize=True)
    os.makedirs(os.path.join(ROOT, "drawable"), exist_ok=True)
    open(os.path.join(ROOT, "drawable", "themed_app_icon.xml"), "w").write(vector_xml())


if __name__ == "__main__":
    main()
