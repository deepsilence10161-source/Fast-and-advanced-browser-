import copy
import os
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
import safety_update_e2e as s

PKG = "com.swiftra.app"
VERSION = "155.0.8059.80"
PREFS = b'''<?xml version="1.0" encoding="utf-8"?>
<map>
 <string name="swiftra_oscrypt_wrapped_v1">wrapped-test-fixture-not-a-key</string>
 <boolean name="first_run_flow_complete" value="true" />
 <long name="swiftra_update_last_ok_ms" value="123" />
 <long name="swiftra_update_last_try_ms" value="124" />
 <string name="swiftra_update_manifest">{&quot;v&quot;:1}</string>
</map>'''


def mapping(raw):
    return {n.get("name"): (n.tag, dict(n.attrib), n.text) for n in ET.fromstring(raw)}


def xml_for(state, package=PKG, title=True, version=True, bounds="[0,0][500,50]", play=False):
    root = ET.Element("hierarchy")
    texts = []
    if title:
        texts.append("Safety check")
    texts.append({"current": "Swiftra is up to date", "outdated": "Swiftra is out of date",
                  "unavailable": "Can\u2019t check Swiftra version"}[state])
    if version:
        texts.append("Version " + VERSION)
    if play:
        texts.append("Go to Google Play")
    for text in texts:
        ET.SubElement(root, "node", {"package": package, "text": text,
                                    "resource-id": "android:id/title", "bounds": bounds})
    return ET.tostring(root, encoding="unicode")


def good_result():
    cases = {}
    for name, state in s.EXPECTED.items():
        cases[name] = {"ui": s.page_state(xml_for(state), PKG, VERSION),
                       "manifest_fetched": True, "signature_rejected": True,
                       "verified_by_app": name == "good_production",
                       "last_ok_before": 0 if name == "good_production" else 123,
                       "last_ok_after": 456 if name == "good_production" else 123}
    return {"cases": cases, "restored": True}


def test_reset_only_update_prefs_and_restore_original_nodes():
    reset = s.replace_update_nodes(PREFS, [])
    assert s.last_ok(reset) == 0
    assert mapping(reset) == {k: v for k, v in mapping(PREFS).items() if not k.startswith(s.PREFIX)}
    assert mapping(s.replace_update_nodes(reset, s.update_nodes(PREFS))) == mapping(PREFS)


def test_expiry_fixture_does_not_change_manifest_or_wrapped_key():
    changed = s.with_last_ok(PREFS, 999)
    before, after = mapping(PREFS), mapping(changed)
    assert s.last_ok(changed) == 999
    assert {k: v for k, v in before.items() if k != s.LAST_OK} == {k: v for k, v in after.items() if k != s.LAST_OK}


def test_private_prefs_validation_fails_closed():
    with pytest.raises(ValueError):
        s.update_nodes(b"<not-a-preference-map />")
    with pytest.raises(ValueError):
        s.last_ok(b'<map><string name="swiftra_update_last_ok_ms">123</string></map>')
    with pytest.raises(ValueError):
        s.last_ok(b'<map><long name="swiftra_update_last_ok_ms" value="1" /><long name="swiftra_update_last_ok_ms" value="2" /></map>')


@pytest.mark.parametrize("state", ["current", "unavailable", "outdated"])
def test_visible_native_state_and_curly_apostrophe(state):
    ui = s.page_state(xml_for(state), PKG, VERSION)
    assert ui["state"] == state and ui["states"] == [state]
    assert ui["page_title"] and ui["version"] and not ui["play_store"]


def test_invisible_other_app_and_malformed_xml_are_not_evidence():
    assert s.page_state(xml_for("current", bounds="[0,0][0,0]"), PKG, VERSION)["state"] is None
    assert s.page_state(xml_for("current", package="com.other.app"), PKG, VERSION)["state"] is None
    assert s.page_state("not xml", PKG, VERSION)["state"] is None
    assert s.page_state(xml_for("current"), PKG, "different-version")["version"] is False


def test_conflicting_states_are_not_a_pass():
    a = ET.fromstring(xml_for("current"))
    b = ET.fromstring(xml_for("unavailable"))
    a.extend(list(b))
    ui = s.page_state(ET.tostring(a, encoding="unicode"), PKG, VERSION)
    assert ui["state"] is None and len(ui["states"]) == 2
    assert not s.case_pass("good_production", dict(good_result()["cases"]["good_production"], ui=ui))


def test_all_cases_required_restoration_and_genuine_production_verification():
    ok = good_result()
    assert s.verdict(ok) == "pass"
    assert s.verdict(dict(ok, restored=False)) == "fail"
    assert s.verdict(dict(ok, error="fixture failed")) == "fail"
    for name in s.EXPECTED:
        bad = copy.deepcopy(ok)
        del bad["cases"][name]
        assert s.verdict(bad) == "fail"
    bad = copy.deepcopy(ok)
    bad["cases"]["good_production"]["verified_by_app"] = False
    assert s.verdict(bad) == "fail"
    bad["cases"]["good_production"]["verified_by_app"] = True
    bad["cases"]["good_production"]["last_ok_before"] = 123
    assert s.verdict(bad) == "fail"  # pre-seeding a positive timestamp is not the production acceptance case


def test_bad_signature_without_download_rejection_or_timestamp_integrity_cannot_pass():
    for key, value in (("manifest_fetched", False), ("signature_rejected", False), ("last_ok_after", 999)):
        bad = good_result()
        bad["cases"]["bad_fresh"][key] = value
        assert s.verdict(bad) == "fail"
    bad = good_result()
    bad["cases"]["bad_stale"]["ui"] = s.page_state(xml_for("current"), PKG, VERSION)
    assert s.verdict(bad) == "fail"
    bad = good_result()
    bad["cases"]["bad_recent"]["ui"] = s.page_state(xml_for("unavailable"), PKG, VERSION)
    assert s.verdict(bad) == "fail"


def test_play_store_dead_button_and_missing_title_cannot_pass():
    for kwargs in ({"play": True}, {"title": False}, {"version": False}):
        bad = good_result()
        bad["cases"]["good_production"]["ui"] = s.page_state(xml_for("current", **kwargs), PKG, VERSION)
        assert s.verdict(bad) == "fail"


def test_setup_blocked_not_claimed_as_android_pass():
    assert s.verdict({}) == "not_run"
    assert s.verdict({"setup_error": "root unavailable"}) == "not_run"
    assert s.verdict(dict(good_result(), unsupported=True)) == "not_run"


def test_focused_mode_uses_same_harness_but_never_dispatches_publish():
    from pathlib import Path
    root = Path(ROOT)
    wrapper = (root / "scripts/ci/run_capture.sh").read_text()
    assert 'if [ "${2:-full}" = safety_update ]; then' in wrapper
    assert 'safety_update_e2e.py --package "$ART_PKG" --apk "$APK_FILE"' in wrapper
    assert 'safety_update_e2e.py --package "$PKG"' in wrapper  # full regression path too
    for name, need in (("ui-capture.yml", "capture"), ("arm64-device-e2e.yml", "e2e")):
        text = (root / ".github/workflows" / name).read_text()
        assert "options: [full, safety_update]" in text
        assert "needs: " + need + "\n    if: always() && inputs.checks != 'safety_update'" in text
        assert '${{ inputs.checks || \'full\' }}' in text


def test_focused_safety_marker_alone_is_not_full_release_evidence(tmp_path):
    sys.path.insert(0, os.path.join(ROOT, "scripts", "release"))
    import e2e_gate
    sha = "a" * 64
    (tmp_path / "BUILD_INFO.txt").write_text(
        "--- patches\n0005-safety-hub-no-false-up-to-date.patch\n0020-swiftra-update-channel.patch\n"
        f"--- sha256\n{sha}\n")
    (tmp_path / "safety_update_e2e.txt").write_text("SAFETY_UPDATE_E2E PASS cases=5/5 restored=True\n")
    reasons = e2e_gate.gate(str(tmp_path), sha)
    assert reasons and any("DEVICE_CHECKS" in x for x in reasons)
    assert any("SHIELD_E2E" in x for x in reasons)
