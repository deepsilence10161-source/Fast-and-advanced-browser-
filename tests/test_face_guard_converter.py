"""Host JVM tests for FaceGrayConverter (frame rotation / stride / RGB565). Host result only; NOT camera or Android PASS."""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools/face_guard/src/org/chromium/chrome/browser/swiftra/faceguard/FaceGrayConverter.java"
TEST = ROOT / "tools/face_guard/test/FaceGrayConverterTest.java"
pytestmark = pytest.mark.skipif(not (shutil.which("javac") and shutil.which("java")), reason="JDK required")

MUTANTS = {
    "stride_ignored": ("y[sy * rowStride + sx]", "y[sy * width + sx]"),
    "rot90_wrong_direction": ("                        sx = oy;\n                        sy = height - 1 - ox;",
                              "                        sx = width - 1 - oy;\n                        sy = ox;"),
    "rot180_not_flipped": ("sx = width - 1 - ox;\n                        sy = height - 1 - oy;",
                           "sx = ox;\n                        sy = height - 1 - oy;"),
    "odd_width_kept": ("int outW = fullW & ~1;", "int outW = fullW;"),
    "bad_rotation_accepted": ("if (rotation != 0 && rotation != 90 && rotation != 180 && rotation != 270) {",
                              "if (false) {"),
    "short_plane_accepted": ("if (y.length < (long) (height - 1) * rowStride + width) {", "if (false) {"),
    "grey_green_wrong": ("((g >> 2) << 5)", "((g >> 3) << 5)"),
}


def run(source_text):
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "org/chromium/chrome/browser/swiftra/faceguard/FaceGrayConverter.java"
        src.parent.mkdir(parents=True)
        src.write_text(source_text)
        out = Path(d) / "out"
        out.mkdir()
        c = subprocess.run(["javac", "-Xlint:all", "-Werror", "-d", str(out), str(src), str(TEST)],
                           capture_output=True, text=True, timeout=120)
        if c.returncode:
            return c.returncode, c.stdout + c.stderr
        r = subprocess.run(["java", "-cp", str(out), "FaceGrayConverterTest"], capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout + r.stderr


def test_converter_passes():
    rc, out = run(SRC.read_text())
    assert rc == 0 and "FACE_GRAY_CONVERTER_OK" in out, out


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_mutant_is_rejected(name):
    old, new = MUTANTS[name]
    text = SRC.read_text()
    assert text.count(old) == 1, "mutation anchor drifted: " + name
    rc, out = run(text.replace(old, new))
    assert rc != 0 and "FACE_GRAY_CONVERTER_OK" not in out, "mutant survived: " + name
