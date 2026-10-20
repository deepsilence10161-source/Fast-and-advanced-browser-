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


@pytest.mark.parametrize("point", [n for n in range(32) if n not in (9, 10, 13)])
def test_android_control_references_preserved_losslessly(point):
    raw = ('<map><string name="unrelated">A&#%d;B</string>'
           '<string name="swiftra_update_test">U&#x%x;V</string>'
           '<string name="swiftra_oscrypt_wrapped_v1">wrapped-fixture</string>'
           '<long name="swiftra_update_last_ok_ms" value="123" /></map>' % (point, point)).encode()
    before = s.pref_root(raw)
    assert before.find("string").text == "A" + chr(point) + "B"
    original = s.update_nodes(raw)
    reset = s.replace_update_nodes(raw, [])
    assert s.pref_root(reset).find("string").text == "A" + chr(point) + "B"
    assert ("&#%d;" % point).encode() in reset
    assert bytes([point]) not in reset
    restored = s.replace_update_nodes(reset, original)
    def data(blob):
        return {n.get("name"): (n.tag, dict(n.attrib), n.text) for n in s.pref_root(blob)}
    assert data(restored) == data(raw)
    assert data(reset)["swiftra_oscrypt_wrapped_v1"] == data(raw)["swiftra_oscrypt_wrapped_v1"]


def test_control_codec_keeps_literal_references_unicode_and_marker_collisions():
    raw = ('<map><string name="unrelated">नमस्ते __SWIFTRA_XML_CONTROL_0__ &amp;#0; &#0;</string>'
           '<string name="attribute&#1;key">value</string></map>').encode()
    a = s.pref_root(raw)
    b = s.pref_root(s.replace_update_nodes(raw, []))
    assert a.find("string").text == b.find("string").text
    assert "&amp;#0;" in s.prefs_bytes(b).decode()
    assert list(a)[1].get("name") == list(b)[1].get("name") == "attribute" + chr(1) + "key"


def test_encoded_legal_references_cannot_collide_with_control_placeholders():
    raw = b'<map><string name="unrelated">&#95;&#x5f;SWIFTRA_XML_CONTROL_0__&#0;</string></map>'
    expected = "__SWIFTRA_XML_CONTROL_0__" + chr(0)
    assert s.pref_root(raw).find("string").text == expected
    assert s.pref_root(s.replace_update_nodes(raw, [])).find("string").text == expected


def test_all_32_android_controls_roundtrip_in_text_and_attributes():
    refs = "".join("&#%d;" % p for p in range(32))
    controls = "".join(chr(p) for p in range(32))
    raw = ('<map><string name="key%s">value%s</string></map>' % (refs, refs)).encode()
    restored = s.pref_root(s.replace_update_nodes(raw, [])).find("string")
    assert restored.get("name") == "key" + controls
    assert restored.text == "value" + controls  # raw CR must not be normalized to LF


def test_control_codec_does_not_repair_unsupported_xml_constructs():
    for raw in (b'<!DOCTYPE map [<!ENTITY x "value">]><map />',
                b'<map><string name="x"><![CDATA[&#0;]]></string></map>',
                b'<map><str&#1;ing name="x">value</str&#1;ing></map>'):
        with pytest.raises((RuntimeError, ET.ParseError)):
            s.pref_root(raw)
    with pytest.raises(ET.ParseError):
        s.pref_root(b'<map><string name="x">&#x110000;</string></map>')


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


def test_native_current_module_is_expanded_before_asserting_version(tmp_path, monkeypatch):
    taps = []
    menu = {"id": PKG + ":id/menu_button", "h": 48, "text": "Menu"}
    header = {"id": "android:id/title", "h": 48, "text": "Swiftra is up to date"}
    collapsed = xml_for("current").replace("Version " + VERSION, "")
    screens = iter([([menu], ""), ([header], collapsed), ([header], xml_for("current"))])
    monkeypatch.setattr(s, "to_browser", lambda *a: True)
    monkeypatch.setattr(s, "ui_nodes", lambda: next(screens))
    monkeypatch.setattr(s, "find_text", lambda text, **kw: ({"text": text}, ""))
    monkeypatch.setattr(s, "tap", lambda n: taps.append(n.get("text")))
    monkeypatch.setattr(s, "screenshot", lambda *a: None)
    monkeypatch.setattr(s.time, "sleep", lambda *a: None)
    ui = s.open_safety(PKG, str(tmp_path), "current", VERSION)
    assert taps[-1] == "Swiftra is up to date"
    assert ui["expanded_for_version"] and ui["version"] and ui["state"] == "current"


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
    assert 'if [ "$MODE" = safety_update ]; then' in wrapper
    assert 'safety_update_e2e.py --package "$ART_PKG" --apk "$APK_FILE"' in wrapper
    assert 'safety_update_e2e.py --package "$PKG"' in wrapper  # full regression path too
    for name, need in (("ui-capture.yml", "capture"), ("arm64-device-e2e.yml", "e2e")):
        text = (root / ".github/workflows" / name).read_text()
        assert "options: [full, safety_update, startup_ablation]" in text
        assert "needs: " + need + "\n    if: always() && (inputs.checks == 'full' || inputs.checks == '')" in text
        assert '${{ inputs.checks || \'full\' }}' in text


def test_private_parse_error_has_metadata_not_content(monkeypatch):
    private = b"not-xml private-sentinel-do-not-print"
    monkeypatch.setattr(s, "checked_adb", lambda *args, **kwargs: private)
    with pytest.raises(RuntimeError) as error:
        s.read_prefs("/private/test.xml")
    message = str(error.value)
    assert "prefs parse refused" in message and "bytes=" in message and "position=" in message
    assert "private-sentinel" not in message and "not-xml" not in message


@pytest.mark.parametrize("raw,kind,controls", [(b"ABX\x00", "abx", 1), (b"", "empty", 0),
                                               (b"<?xml broken\x01", "xml", 1)])
def test_parse_metadata_classifies_without_dumping_content(monkeypatch, raw, kind, controls):
    monkeypatch.setattr(s, "checked_adb", lambda *args, **kwargs: raw)
    with pytest.raises(RuntimeError) as error:
        s.read_prefs("/private/test.xml")
    assert "format=" + kind in str(error.value)
    assert "controls=" + str(controls) in str(error.value)


def test_stop_flushes_activity_before_force_stop(monkeypatch):
    calls = []
    monkeypatch.setattr(s, "adb", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(s, "checked_adb", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(s.time, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    s.stop_browser(PKG)
    assert calls == [("shell", "input", "keyevent", "KEYCODE_HOME"), ("sleep", 2),
                     ("shell", "am", "force-stop", PKG)]


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
