import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ci"))
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("pc", ROOT / "scripts/ci/personal_clipboard_e2e.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


def test_parse_helper_get():
    assert pc.parse_helper_get("I/CLIPHELPER( 1): GET text=[ctl_ab]\n") == ("text", "ctl_ab")
    assert pc.parse_helper_get("11-17 I CLIPHELPER: GET none") == ("none", "")
    assert pc.parse_helper_get("I CLIPHELPER: ERR java.lang.SecurityException: x")[0] == "error"
    assert pc.parse_helper_get("nothing here") == ("missing", "")
    # the last line wins
    assert pc.parse_helper_get("I CLIPHELPER: GET text=[old]\nI CLIPHELPER: GET text=[new]") == ("text", "new")


def test_classify_copy_never_passes_without_evidence():
    assert pc.classify_copy("text", "web_t", "ctl", "web_t", True)[0] == "FAIL"
    assert pc.classify_copy("text", "ctl", "ctl", "web_t", True)[0] == "PASS"
    assert pc.classify_copy("text", "ctl", "ctl", "web_t", False)[0] == "NOT_RUN"
    assert pc.classify_copy("none", "", "ctl", "web_t", True)[0] == "NOT_RUN"
    assert pc.classify_copy("error", "x", "ctl", "web_t", True)[0] == "NOT_RUN"
    assert pc.classify_copy("text", "something_else", "ctl", "web_t", True)[0] == "FAIL"


def test_classify_paste():
    assert pc.classify_paste(["ctl_1"], "ctl_1", True)[0] == "FAIL"
    assert pc.classify_paste([""], "ctl_1", True)[0] == "PASS"
    assert pc.classify_paste([], "ctl_1", False)[0] == "NOT_RUN"
