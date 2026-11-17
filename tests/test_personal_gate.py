import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pg", ROOT / "scripts/release/personal_gate.py")
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)

SHA = "a" * 64
INFO = "personal_source_only=1\nsigner_cert_sha256=ab12\nexpected_cert_sha256=ab12\n"
FG = INFO + "--- patches\n0105-face-guard-presence-mode.patch\n"
E2E = {"x64": {"apk_sha256": SHA, "summary": {"PASS": 10, "FAIL": 0, "NOT_RUN": 0}}}
FGE = {"face_guard_apk": {"x64": {"apk_sha256": SHA, "summary": {"PASS": 5, "FAIL": 0, "NOT_RUN": 1},
                                   "scenarios": {"nofaces": "PASS", "one": "PASS", "two": "PASS"}}}}


def test_plain_personal_build_with_matching_evidence_passes():
    assert pg.gate("x64", INFO, SHA, [E2E]) == []


def test_wrong_sha_or_failures_or_missing_evidence_refused():
    assert "no_e2e_evidence_for_this_apk_sha256" in pg.gate("x64", INFO, "b" * 64, [E2E])
    bad = {"x64": {"apk_sha256": SHA, "summary": {"PASS": 9, "FAIL": 1}}}
    assert "no_e2e_evidence_for_this_apk_sha256" in pg.gate("x64", INFO, SHA, [bad])
    assert "no_e2e_evidence_for_this_apk_sha256" in pg.gate("x64", INFO, SHA, [])


def test_not_personal_or_signer_mismatch_refused():
    assert "not_a_personal_build" in pg.gate("x64", "personal_source_only=0\n", SHA, [E2E])
    assert "signer_mismatch_or_missing" in pg.gate("x64", "personal_source_only=1\nsigner_cert_sha256=1\nexpected_cert_sha256=2\n", SHA, [E2E])


def test_face_guard_build_needs_its_own_apk_evidence():
    assert "face_guard_in_build_but_no_apk_evidence_for_this_sha256" in pg.gate("x64", FG, SHA, [E2E])
    assert pg.gate("x64", FG, SHA, [E2E, FGE]) == []
    partial = {"face_guard_apk": {"x64": {"apk_sha256": SHA, "summary": {"FAIL": 0},
                                           "scenarios": {"nofaces": "PASS", "one": "PASS", "two": "NOT_RUN"}}}}
    assert pg.gate("x64", FG, SHA, [E2E, partial])
    failed = {"face_guard_apk": {"x64": {"apk_sha256": SHA, "summary": {"FAIL": 1},
                                          "scenarios": {"nofaces": "PASS", "one": "PASS", "two": "PASS"}}}}
    assert pg.gate("x64", FG, SHA, [E2E, failed])


def test_arm64_needs_only_nofaces_and_never_counts_not_run_as_pass():
    e = {"arm64": {"apk_sha256": SHA, "summary": {"PASS": 9, "FAIL": 0, "NOT_RUN": 1}}}
    fg = {"face_guard_apk": {"arm64": {"apk_sha256": SHA, "summary": {"FAIL": 0}, "scenarios": {"nofaces": "PASS", "one": "NOT_RUN"}}}}
    assert pg.gate("arm64", FG, SHA, [e, fg]) == []
    fg["face_guard_apk"]["arm64"]["scenarios"]["nofaces"] = "NOT_RUN"
    assert pg.gate("arm64", FG, SHA, [e, fg])
