"""Host tests of the pure parsing helpers in scripts/ci/face_guard_e2e.py. NOT an Android result."""
import importlib.util
import io
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fg_e2e", ROOT / "scripts/ci/face_guard_e2e.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

ROW = ('<hierarchy><node text="Incognito lock" class="android.widget.TextView" bounds="[42,900][700,960]"/>'
       '<node text="Face Guard (experimental)" class="android.widget.TextView" bounds="[42,1000][800,1060]"/>'
       '<node text="Locks the browser" class="android.widget.TextView" bounds="[42,1060][800,1200]"/>'
       '<node class="android.widget.Switch" checked="%s" checkable="true" resource-id="x:id/switch_widget" bounds="[900,1010][1040,1090]"/>'
       '<node class="android.widget.Switch" checked="true" resource-id="x:id/switch_widget" bounds="[900,400][1040,480]"/>'
       '</hierarchy>')


def test_switch_state_reads_the_row_next_to_the_title_only():
    assert M.switch_state(ROW % "false") == (True, False)
    assert M.switch_state(ROW % "true") == (True, True)
    assert M.switch_state("<hierarchy/>") == (False, False)


def test_overlay_and_hub_detection():
    assert M.overlay_visible('<node text="Looking for your face\u2026 The tab"/>')
    assert M.overlay_visible('<node text="Camera permission is needed. x"/>')
    assert not M.overlay_visible('<node text="New tab"/>')
    assert M.hub_open('<node resource-id="org.x:id/hub_pane_host"/>')
    assert not M.hub_open('<node resource-id="org.x:id/toolbar"/>')
    assert M.overlay_text('<node text="Camera permission is needed. Face"/>').startswith("Camera permission")


def test_find_node_exact_text_and_bounds():
    n = M.find_node(ROW % "false", text="Face Guard (experimental)")
    assert n["bounds"] == [42, 1000, 800, 1060]
    assert M.find_node(ROW % "false", text="Face Guard") is None


def test_locked_screenshot_detection():
    PIL = pytest.importorskip("PIL.Image")
    dark = PIL.new("RGB", (200, 400), (16, 21, 26))
    buf = io.BytesIO(); dark.save(buf, "PNG")
    assert M.locked_screenshot_ok(buf.getvalue()) is True
    page = PIL.new("RGB", (200, 400), (250, 250, 250))
    buf = io.BytesIO(); page.save(buf, "PNG")
    assert M.locked_screenshot_ok(buf.getvalue()) is False
    assert M.locked_screenshot_ok(b"not a png") is None


def test_summarize_never_counts_not_run_as_pass():
    c = M.summarize([{"status": "PASS"}, {"status": "NOT_RUN"}, {"status": "FAIL"}])
    assert c == {"PASS": 1, "FAIL": 1, "NOT_RUN": 1}


def _probe_module():
    s = importlib.util.spec_from_file_location("fg_probe_check", ROOT / "scripts/ci/face_guard_probe_check.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _probe_text(one=1, two=2, none=0, done=True):
    lines = []
    for name, v in (("no_face.jpg", none), ("one_face.jpg", one), ("two_faces.jpg", two)):
        for r in (0, 90, 180, 270):
            lines.append(f"FACE_PROBE {name} rot={r} faces={v}")
    return "\n".join(lines) + ("\nFACE_PROBE_DONE\n" if done else "\n")


def test_probe_check_accepts_expected_counts_and_rejects_any_deviation():
    P = _probe_module()
    assert all(ok for _, ok, _ in P.evaluate(_probe_text()))
    assert [ok for _, ok, _ in P.evaluate(_probe_text(two=1))] == [True, True, False]
    assert [ok for _, ok, _ in P.evaluate(_probe_text(none=1))] == [False, True, True]
    assert P.evaluate(_probe_text(done=False)) is None
    partial = _probe_text().replace("FACE_PROBE one_face.jpg rot=90 faces=1\n", "")
    assert [ok for _, ok, _ in P.evaluate(partial)] == [True, False, True]


def test_regenerated_patch_is_current():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(ROOT / "tools/face_guard/regen_patch.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_face_scenario_script_and_fixture_builder_are_valid():
    import py_compile
    py_compile.compile(str(ROOT / "scripts/ci/face_guard_face_e2e.py"), doraise=True)
    PIL = pytest.importorskip("PIL.Image")
    import subprocess
    import sys
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([sys.executable, str(ROOT / "tools/face_guard/make_cam_fixtures.py"), d], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        for key in ("one", "two", "none"):
            for v in ("rot0", "rot90"):
                assert PIL.open(f"{d}/cam_{key}_{v}.jpg").size == (640, 480)
