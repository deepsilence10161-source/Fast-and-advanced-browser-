import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "release"))
import release_gate as g

BI = "Package: com.swiftra.app\ncpu arm64\n--- patches\n%s\n--- end\n"

def _w(tmp_path, pats):
    p = tmp_path / "BI.txt"; p.write_text(BI % "\n".join(pats)); return str(p)

def test_full_set_passes(tmp_path):
    r, _ = g.gate("x", _w(tmp_path, g.required()), "arm64", run_audit=False)
    assert r == []

def test_old_build_blocked(tmp_path):
    r, _ = g.gate("x", _w(tmp_path, [p for p in g.required() if not p.startswith("0016")]), "arm64", run_audit=False)
    assert r and "0016-swiftra-speedpack.py" in r[0]
