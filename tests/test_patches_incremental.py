"""Incremental builds: a changed patch set must re-stamp ONLY files whose final content changed (scripts/ci/patches.py)."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ci_patches", ROOT / "scripts/ci/patches.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

OLD = 1_000_000_000


def make_src(tmp):
    src = tmp / "src"
    src.mkdir()
    for n in ("a.txt", "b.txt", "c.txt"):
        (src / n).write_text(f"{n} line1\nline2\n")
        os.utime(src / n, (OLD, OLD))
    return src


def diff(src, name, new_second_line):
    return (f"--- a/{name}\n+++ b/{name}\n@@ -1,2 +1,2 @@\n {name} line1\n-line2\n+{new_second_line}\n")


def pdir_with(tmp, tag, patches):
    d = tmp / f"p{tag}"
    d.mkdir()
    (d / "series").write_text("\n".join(n for n, _ in patches) + "\n")
    for n, body in patches:
        (d / n).write_text(body)
    return d


def run(src, pdir, prev, out, now):
    assert P.apply(str(src), str(pdir), str(prev) if prev else "-", str(out), now=now) == 0
    return json.load(open(out))


def mtimes(src):
    return {n: int((src / n).stat().st_mtime) for n in ("a.txt", "b.txt", "c.txt")}


def fresh(tmp, tag):
    s = tmp / f"s{tag}"
    s.mkdir()
    return make_src(s)


def test_only_changed_files_are_restamped(tmp_path):
    pa, pb = diff(None, "a.txt", "A2"), diff(None, "b.txt", "B2")
    # build 1: patches on a and b
    src1 = fresh(tmp_path, 1)
    d1 = pdir_with(tmp_path, 1, [("0001.patch", pa), ("0002.patch", pb)])
    j1 = run(src1, d1, None, tmp_path / "o1.json", 2_000_000_000)
    assert mtimes(src1) == {"a.txt": 2_000_000_000, "b.txt": 2_000_000_000, "c.txt": OLD}
    assert set(j1["stamps"]) == {"a.txt", "b.txt"}
    # build 2: pristine src restored again, patch for b changes, a stays identical, c newly patched
    src2 = fresh(tmp_path, 2)
    d2 = pdir_with(tmp_path, 2, [("0001.patch", pa), ("0002.patch", diff(None, "b.txt", "B3")), ("0003.patch", diff(None, "c.txt", "C2"))])
    (tmp_path / "prev1.json").write_text(json.dumps({"patches": j1, "out_prefix": "x"}))
    j2 = run(src2, d2, tmp_path / "prev1.json", tmp_path / "o2.json", 2_100_000_000)
    m = mtimes(src2)
    assert m["a.txt"] == 2_000_000_000, "unchanged content keeps its old stamp (no rebuild of its dependents)"
    assert m["b.txt"] == 2_100_000_000 and m["c.txt"] == 2_100_000_000
    assert j2["changed"] is True


def test_file_no_longer_patched_is_restamped(tmp_path):
    pa, pb = diff(None, "a.txt", "A2"), diff(None, "b.txt", "B2")
    src1 = fresh(tmp_path, 1)
    d1 = pdir_with(tmp_path, 1, [("0001.patch", pa), ("0002.patch", pb)])
    j1 = run(src1, d1, None, tmp_path / "o1.json", 2_000_000_000)
    src2 = fresh(tmp_path, 2)       # pristine, b is no longer patched
    d2 = pdir_with(tmp_path, 2, [("0001.patch", pa)])
    (tmp_path / "prev1.json").write_text(json.dumps({"patches": j1, "out_prefix": "x"}))
    run(src2, d2, tmp_path / "prev1.json", tmp_path / "o2.json", 2_100_000_000)
    m = mtimes(src2)
    assert m["a.txt"] == 2_000_000_000
    assert m["b.txt"] == 2_100_000_000, "reverted file must look newer than the object built from the patched version"


def test_legacy_state_without_stamps_restamps_everything_once(tmp_path):
    pa = diff(None, "a.txt", "A2")
    src1 = fresh(tmp_path, 1)
    d1 = pdir_with(tmp_path, 1, [("0001.patch", pa)])
    legacy = {"hash": "oldhash", "epoch": 1_500_000_000, "files": ["a.txt"]}
    (tmp_path / "prev.json").write_text(json.dumps({"patches": legacy, "out_prefix": "x"}))
    j = run(src1, d1, tmp_path / "prev.json", tmp_path / "o.json", 2_000_000_000)
    assert mtimes(src1)["a.txt"] == 2_000_000_000
    assert j["stamps"]["a.txt"]["epoch"] == 2_000_000_000


def test_same_patch_set_is_stable(tmp_path):
    pa = diff(None, "a.txt", "A2")
    d = pdir_with(tmp_path, 1, [("0001.patch", pa)])
    src1 = fresh(tmp_path, 1)
    j1 = run(src1, d, None, tmp_path / "o1.json", 2_000_000_000)
    src2 = fresh(tmp_path, 2)
    (tmp_path / "prev1.json").write_text(json.dumps({"patches": j1, "out_prefix": "x"}))
    j2 = run(src2, d, tmp_path / "prev1.json", tmp_path / "o2.json", 2_300_000_000)
    assert j2["changed"] is False
    assert mtimes(src2)["a.txt"] == 2_000_000_000
