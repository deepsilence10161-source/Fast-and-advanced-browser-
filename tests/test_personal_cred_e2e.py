import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ci"))
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("pcr", ROOT / "scripts/ci/personal_cred_e2e.py")
pcr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pcr)


def test_cred_requests_parse():
    log = "I CLIPHELPER: CRED_GET pkg=com.swiftra.cliphelper\nI CLIPHELPER: CRED_CREATE pkg=a.b\nI CLIPHELPER: CRED_CLEAR pkg=z"
    assert pcr.cred_requests(log) == ["com.swiftra.cliphelper", "a.b"]


def test_classify_browser():
    pkg = "com.swiftra.personaldev"
    assert pcr.classify_browser([pkg], pkg, True, True)[0] == "FAIL"
    assert pcr.classify_browser([], pkg, True, True)[0] == "PASS"
    assert pcr.classify_browser([], pkg, True, False)[0] == "NOT_RUN"
    assert pcr.classify_browser([], pkg, False, True)[0] == "NOT_RUN"
