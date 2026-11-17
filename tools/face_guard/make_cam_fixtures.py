#!/usr/bin/env python3
"""Build the front-camera frames fed to the Android emulator (-camera-front imagefile:/videofile:).

NOTE (measured 17 Nov 2026): the emulator's imagefile front camera reports SENSOR_ORIENTATION 90 and FaceDetector finds
the face in the `rot0` files at the app's rotation, so `rot0` is the ACCEPTANCE variant. Old text follows. `rot90` files hold the
upright picture (the app will see it sideways) and exist only to learn how the emulator orients image files.
Usage: make_cam_fixtures.py <out-dir>   (needs Pillow)
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "../../tests/fixtures/face_guard")
BG = (128, 128, 128)


def fit(img, w, h):
    s = min(w / img.width, h / img.height)
    im = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), BG)
    canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return canvas


# Measured with the camdiag suite (17 Nov 2026, x64 emulator front camera via -camera-front imagefile:, sensor orientation 90):
# the emulator scales the 640x480 file by 640/480 and shows it in a 480x640 portrait view: only the LEFT columns 0..359 of
# the file (360 px wide, full height) are visible (upright x = 1.333 * file x). Everything the test needs must sit there.
WIN_X, WIN_W, FRAME_W, FRAME_H = 0, 360, 640, 480


def window_frame(content):
    """content: a WIN_W x FRAME_H picture -> 640x480 sensor-file with the picture inside the visible window."""
    canvas = Image.new("RGB", (FRAME_W, FRAME_H), BG)
    canvas.paste(content, (WIN_X, 0))
    return canvas


def main(out):
    os.makedirs(out, exist_ok=True)
    for key, name in (("one", "one_face.jpg"), ("two", "two_faces.jpg"), ("none", "no_face.jpg")):
        src = Image.open(os.path.join(FIX, name)).convert("RGB")
        if key == "two":
            # android.media.FaceDetector found only ONE of the two real people in the group photo through the emulator
            # camera, so the two-face fixture shows the same clearly detectable face TWICE side by side. It tests the
            # app's "two detected faces -> lock" path; it does NOT prove the detector finds a real second person.
            w, h = src.size
            face = src.crop((round(w * 0.24), round(h * 0.10), round(w * 0.52), round(h * 0.78)))
            half = fit(face, WIN_W // 2, FRAME_H)
            content = Image.new("RGB", (WIN_W, FRAME_H), BG)
            content.paste(half, (0, 0))
            content.paste(half, (WIN_W // 2, 0))
        else:
            content = fit(src, WIN_W, FRAME_H)
        upright = fit(src, 480, 640)
        upright.rotate(-90, expand=True).save(os.path.join(out, f"cam_{key}_rot90.jpg"), quality=92)   # information only
        window_frame(content).save(os.path.join(out, f"cam_{key}_rot0.jpg"), quality=92)               # acceptance
    print("wrote", sorted(os.listdir(out)))


if __name__ == "__main__":
    main(sys.argv[1])
