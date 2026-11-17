import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ci"))
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("paf", ROOT / "scripts/ci/personal_autofill_e2e.py")
paf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paf)


def test_autofill_requests_parse():
    log = "I CLIPHELPER: AUTOFILL_CONNECTED\nI CLIPHELPER: AUTOFILL_REQUEST pkg=com.swiftra.cliphelper\nI CLIPHELPER: AUTOFILL_REQUEST pkg=com.x.y"
    assert paf.autofill_requests(log) == ["com.swiftra.cliphelper", "com.x.y"]
    assert paf.autofill_requests("nothing") == []


def test_classify_browser():
    pkg = "com.swiftra.personaldev"
    assert paf.classify_browser([pkg], pkg, True, True)[0] == "FAIL"
    assert paf.classify_browser([], pkg, True, True)[0] == "PASS"
    assert paf.classify_browser([], pkg, True, False)[0] == "NOT_RUN"
    assert paf.classify_browser([], pkg, False, True)[0] == "NOT_RUN"
    assert paf.classify_browser(["com.swiftra.cliphelper"], pkg, True, True)[0] == "PASS"
