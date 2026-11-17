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


def main(out):
    os.makedirs(out, exist_ok=True)
    for key, name in (("one", "one_face.jpg"), ("two", "two_faces.jpg"), ("none", "no_face.jpg")):
        src = Image.open(os.path.join(FIX, name)).convert("RGB")
        if key == "two":
            # android.media.FaceDetector found only ONE of the two real people in the group photo through the emulator camera
            # (camdiag runs, 17 Nov 2026), so the two-face fixture shows the same clearly detectable face TWICE side by side.
            # It tests the app's "two detected faces -> lock" path; it does NOT prove the detector finds a real second person.
            w, h = src.size
            face = src.crop((round(w * 0.24), round(h * 0.10), round(w * 0.52), round(h * 0.78)))
            half = fit(face, 240, 480)
            both = Image.new("RGB", (480, 480), BG)
            both.paste(half, (0, 0))
            both.paste(half, (240, 0))
            src = both
        upright = fit(src, 480, 640)                       # what the app should see (portrait 480x640)
        upright.rotate(-90, expand=True).save(os.path.join(out, f"cam_{key}_rot90.jpg"), quality=92)   # sensor frame 640x480
        # Measured (camdiag, 17 Nov 2026): the emulator turns the 640x480 file into a 480-wide portrait view and keeps only the
        # central 480 columns, so a full-width picture loses its edges (the second person was cut off). Keep the whole
        # picture inside the central 480x480 square.
        inner = fit(src, 480, 480)
        canvas = Image.new("RGB", (640, 480), BG)
        canvas.paste(inner, (80, 0))
        canvas.save(os.path.join(out, f"cam_{key}_rot0.jpg"), quality=92)
    print("wrote", sorted(os.listdir(out)))


if __name__ == "__main__":
    main(sys.argv[1])
