#!/usr/bin/env python3
"""Swiftra product-logo assets — Chromium के branded logo assets की जगह (b2)।

एक ही ज्यामिति (launcher icon / themed_app_icon.xml वाली दो chevrons + diagonal gradient गोला) से:
  components/browser_ui/styles/android/java/res_chromium/drawable-<d>/fre_product_logo.png   (FRE, payments,
      custom-tabs, HaTS, touch-to-fill, omnibox default action — सब इसी drawable से)
  components/browser_ui/styles/android/java/res_chromium/drawable-<d>/product_logo_name.png  (logo + wordmark)
  components/browser_ui/styles/android/java/res_chromium/raw/signin_spin.json                (sign-in Lottie)
Chromium 155.0.8059.80 मूल से माप: fre_product_logo = पूरा canvas गोला (mdpi 130px … xxxhdpi 520px);
product_logo_name = ऊँचाई 21/32/42/63/84px, logo-गोला = पूरी ऊँचाई, wordmark #5F6368;
signin_spin = 180x180, 30fps, 30 frames; logo (त्रिज्या 48, केंद्र 48,48 comp में, frame scale 187.329% = पूरा canvas)
पहले अंदर के हिस्से (frame 8.8–17) फिर पूरा logo (frame 15–21) सिकुड़कर शून्य — वही timing/easing यहाँ।

Gradient (launcher icon से sample, 3 बिंदुओं पर जाँचा): icon-canvas 192px पर t=(x+y)/384,
रंग (19,82,245) -> (0,191,166); गोला icon में 4..188 पर। दूसरी chevron = सफ़ेद, opacity 0.79।
Wordmark font: DejaVu Sans (Bitstream Vera / public-domain derived, permissive)।

Usage: swiftra_logo.py <overlay-root>   (जैसे patches/overlay) — deterministic; उसी input पर वही bytes।
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

C0, C1 = (19, 82, 245), (0, 191, 166)
SECOND_ALPHA = 0.79
WORD_COLOR = (95, 99, 104)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
# themed_app_icon.xml (viewport 90, केंद्र 45) की chevrons; logo-त्रिज्या R पर scale = R*1.111/38
CHEVRONS = [
    [(27.72, 30.60), (37.80, 30.60), (49.32, 45.00), (37.80, 59.40), (27.72, 59.40), (39.24, 45.00)],
    [(40.68, 30.60), (50.76, 30.60), (62.28, 45.00), (50.76, 59.40), (40.68, 59.40), (52.20, 45.00)],
]
K38 = 1.111  # R=38 पर themed-unit -> comp-unit (chevron चौड़ाई = व्यास का 0.505, launcher icon से मापा)
DENS = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
FRE = {"mdpi": 130, "hdpi": 194, "xhdpi": 260, "xxhdpi": 390, "xxxhdpi": 520}
NAME_H = {"mdpi": 21, "hdpi": 32, "xhdpi": 42, "xxhdpi": 63, "xxxhdpi": 84}
SS = 4  # supersampling


def grad_t(s):
    """गोले के bbox में सापेक्ष योग s=u+v (0..2) -> launcher-icon gradient का t।"""
    return (8 + 184 * s) / 384


def color(t):
    return tuple(round(a + (b - a) * t) for a, b in zip(C0, C1))


def chevron_pts(i, cx, cy, R):
    k = R * K38 / 38
    return [(cx + (x - 45) * k, cy + (y - 45) * k) for x, y in CHEVRONS[i]]


def draw_logo(size):
    """size x size RGBA, पूरा canvas गोला।"""
    S = size * SS
    g = Image.new("RGBA", (S, S))
    px = g.load()
    for y in range(S):
        for x in range(S):
            px[x, y] = color(grad_t((x + y + 1) / S)) + (255,)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, S - 1, S - 1), fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(g, (0, 0), mask)
    R = S / 2
    over = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    d.polygon(chevron_pts(0, R, R, R), fill=(255, 255, 255, 255))
    sec = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sec).polygon(chevron_pts(1, R, R, R), fill=(255, 255, 255, round(255 * SECOND_ALPHA)))
    out.alpha_composite(sec)
    out.alpha_composite(over)
    return out.resize((size, size), Image.LANCZOS)


def draw_name(h):
    logo = draw_logo(h)
    # मूल अनुपात (xxxhdpi 84px): text x=101 से (gap 17/84 h), x-height पंक्तियाँ ~19..64
    font = ImageFont.truetype(FONT, round(h * 0.70))
    word = "swiftra"
    l, t, r, b = font.getbbox(word)
    gap = round(h * 17 / 84)
    W = h + gap + (r - l) + max(1, round(h * 0.03))
    img = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    img.alpha_composite(logo, (0, 0))
    base = round(h * 64 / 84)  # baseline
    asc = font.getmetrics()[0]
    ImageDraw.Draw(img).text((h + gap - l, base - asc), word, font=font, fill=WORD_COLOR + (255,))
    return img


def save_png(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, format="PNG", optimize=True)  # PIL PNG में timestamp नहीं -> deterministic


# ---------------- Lottie ----------------
def _kf(t, s, ease_in=(0.8, 0.15), ease_out=(0.3, 0.0)):
    return {"i": {"x": [ease_in[0]] * 3, "y": [ease_in[1]] * 3}, "o": {"x": [ease_out[0]] * 3, "y": [ease_out[1]] * 3},
            "t": t, "s": s}


def _scale_anim(t0, t1, to):
    return {"a": 1, "k": [_kf(t0, [100, 100, 100]), {"t": t1, "s": [to, to, 100]}]}


def _tr(o=100):
    return {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]},
            "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": o}, "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}, "nm": "Transform"}


def _shape_layer(ind, nm, items, scale, op):
    return {"ddd": 0, "ind": ind, "ty": 4, "nm": nm, "parent": 1, "sr": 1,
            "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": [48, 48, 0]},
                   "a": {"a": 0, "k": [0, 0, 0]}, "s": scale},
            "ao": 0, "shapes": items, "ip": 0, "op": op, "st": 0, "bm": 0}


def lottie():
    R = 48.0  # 2R x 187.329% = 180px = पूरा canvas (static fre_product_logo जैसा; मूल frame 0 से render करके मिलाया)

    def chev(i, alpha):
        pts = [[round(x - 48, 3), round(y - 48, 3)] for x, y in chevron_pts(i, 48, 48, R)]
        return {"ty": "gr", "nm": f"chevron{i + 1}", "it": [
            {"ty": "sh", "nm": "Path", "ks": {"a": 0, "k": {"c": True, "v": pts, "i": [[0, 0]] * 6, "o": [[0, 0]] * 6}}},
            {"ty": "fl", "nm": "Fill", "c": {"a": 0, "k": [1, 1, 1, 1]}, "o": {"a": 0, "k": round(alpha * 100)}, "r": 1},
            _tr()]}

    ca, cb = color(grad_t(0)), color(grad_t(2))
    circle = {"ty": "gr", "nm": "circle", "it": [
        {"ty": "el", "nm": "Ellipse", "d": 1, "p": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [2 * R, 2 * R]}},
        {"ty": "gf", "nm": "Gradient", "o": {"a": 0, "k": 100}, "r": 1, "t": 1,
         "s": {"a": 0, "k": [-R, -R]}, "e": {"a": 0, "k": [R, R]},
         "g": {"p": 2, "k": {"a": 0, "k": [0] + [c / 255 for c in ca] + [1] + [c / 255 for c in cb]}}},
        _tr()]}
    null = {"ddd": 0, "ind": 1, "ty": 3, "nm": "frame", "sr": 1,
            "ks": {"o": {"a": 0, "k": 0}, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": [89.539, 90, 0]},
                   "a": {"a": 0, "k": [48, 48, 0]}, "s": {"a": 0, "k": [187.329, 187.329, 100]}},
            "ao": 0, "ip": 0, "op": 30, "st": 0, "bm": 0}
    return {"v": "5.12.2", "fr": 30, "ip": 0, "op": 30, "w": 180, "h": 180, "nm": "swiftra_signin_spin", "ddd": 0,
            "assets": [], "markers": [],
            "layers": [null,
                       _shape_layer(2, "chevrons", [chev(0, 1.0), chev(1, SECOND_ALPHA)], _scale_anim(8.808, 15.051, 0), 23),
                       _shape_layer(3, "circle", [circle], _scale_anim(15.051, 21.051, 0), 23)]}


def main(root):
    base = os.path.join(root, "components/browser_ui/styles/android/java/res_chromium")
    for d in DENS:
        save_png(draw_logo(FRE[d]), os.path.join(base, f"drawable-{d}", "fre_product_logo.png"))
        save_png(draw_name(NAME_H[d]), os.path.join(base, f"drawable-{d}", "product_logo_name.png"))
    os.makedirs(os.path.join(base, "raw"), exist_ok=True)
    with open(os.path.join(base, "raw", "signin_spin.json"), "w", encoding="utf-8") as f:
        json.dump(lottie(), f, separators=(",", ":"), sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
