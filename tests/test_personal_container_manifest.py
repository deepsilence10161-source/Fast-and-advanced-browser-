"""Synthetic decoded-XML unit tests, NOT actual APK/device containment proof."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "security"))
import personal_container_manifest as pc  # noqa: E402

PACKAGE = "org.example.personalbrowser"


def section(parent, tag, **attributes):
    node = ET.SubElement(parent, tag, attributes)
    for domain in sorted(pc.DOMAINS):
        ET.SubElement(node, "exclude", domain=domain, path=".")
    return node


@pytest.fixture
def fixture(tmp_path):
    resources = tmp_path / "res"
    (resources / "xml").mkdir(parents=True)
    rules = ET.Element("data-extraction-rules")
    section(rules, "cloud-backup")
    section(rules, "device-transfer")
    section(rules, "cross-platform-transfer", platform="ios")
    resource = resources / "xml" / "no_transfer.xml"
    ET.ElementTree(rules).write(resource, encoding="utf-8")
    manifest = tmp_path / "AndroidManifest.xml"
    root = ET.Element("manifest", package=PACKAGE)
    ET.SubElement(root, "application", {
        pc.NS + "allowBackup": "false", pc.NS + "fullBackupContent": "false",
        pc.NS + "dataExtractionRules": "@xml/no_transfer",
    })
    ET.ElementTree(root).write(manifest, encoding="utf-8")
    return manifest, resources


def modify_manifest(fixture, change):
    manifest, _ = fixture
    root = ET.parse(manifest).getroot()
    change(root, root.find("application"))
    ET.ElementTree(root).write(manifest, encoding="utf-8")


def modify_rules(fixture, change):
    _, resources = fixture
    path = resources / "xml" / "no_transfer.xml"
    root = ET.parse(path).getroot()
    change(root)
    ET.ElementTree(root).write(path, encoding="utf-8")


def result(fixture):
    return pc.audit(*fixture, PACKAGE)


def test_good_static_inputs_are_not_product_certification(fixture):
    report = result(fixture)
    assert all(report["checks"].values())
    assert report["status"] == "PASS (static/signature/format only)"
    assert report["product_containment"] == "NOT RUN / NOT CERTIFIED"
    assert report["not_checked"]
    assert len(report["resource_evidence"]) == 1


def test_allow_backup_false_alone_is_not_enough(fixture):
    modify_manifest(fixture, lambda _, app: app.attrib.pop(pc.NS + "dataExtractionRules"))
    report = result(fixture)
    assert report["checks"]["allow_backup_explicit_false"]
    assert not report["checks"]["all_transfer_modes_denied"]
    assert report["status"].startswith("FAIL")


@pytest.mark.parametrize("attribute,value,check", [
    ("allowBackup", "true", "allow_backup_explicit_false"),
    ("allowBackup", "@bool/not_known", "allow_backup_explicit_false"),
    ("backupAgent", "org.example.BackupAgent", "no_backup_agent"),
    ("restoreAnyVersion", "true", "restore_any_version_disabled"),
    ("debuggable", "true", "not_debuggable"),
    ("debuggable", "@bool/debug", "not_debuggable"),
    ("testOnly", "true", "not_test_only"),
])
def test_unsafe_manifest_flags_fail(fixture, attribute, value, check):
    modify_manifest(fixture, lambda _, app: app.set(pc.NS + attribute, value))
    assert not result(fixture)["checks"][check]


@pytest.mark.parametrize("permission", sorted(pc.DENIED_PERMISSIONS))
def test_every_declared_account_storage_permission_rejected(fixture, permission):
    modify_manifest(fixture, lambda root, _: ET.SubElement(
        root, "uses-permission-sdk-23", {pc.NS + "name": permission}))
    assert not result(fixture)["checks"]["no_platform_account_or_shared_storage_permissions"]


@pytest.mark.parametrize("permission", [None, "@string/system_permission", "${permission}"])
def test_unresolved_permission_cannot_hide_a_forbidden_name(fixture, permission):
    attrs = {} if permission is None else {pc.NS + "name": permission}
    modify_manifest(fixture, lambda root, _: ET.SubElement(root, "uses-permission", attrs))
    assert not all(result(fixture)["checks"].values())


def test_google_current_account_permission_cannot_bypass_the_policy(fixture):
    modify_manifest(fixture, lambda root, _: ET.SubElement(
        root, "uses-permission", {pc.NS + "name": "com.google.android.apps.now.CURRENT_ACCOUNT_ACCESS"}))
    assert not result(fixture)["checks"]["no_platform_account_or_shared_storage_permissions"]


def test_internet_permission_not_misrepresented_as_zero_network(fixture):
    modify_manifest(fixture, lambda root, _: ET.SubElement(
        root, "uses-permission", {pc.NS + "name": "android.permission.INTERNET"}))
    assert all(result(fixture)["checks"].values())
    assert "network requests/telemetry" in result(fixture)["not_checked"]


def test_shared_uid_rejected(fixture):
    modify_manifest(fixture, lambda root, _: root.set(pc.NS + "sharedUserId", "org.example.uid"))
    assert not result(fixture)["checks"]["no_shared_user_id"]


def test_shell_profiling_rejected(fixture):
    modify_manifest(fixture, lambda _, app: ET.SubElement(
        app, "profileable", {pc.NS + "shell": "true"}))
    assert not result(fixture)["checks"]["no_shell_profileable"]


@pytest.mark.parametrize("attributes,grant_child,check", [
    ({"exported": "true"}, False, "providers_not_exported"),
    ({}, False, "providers_not_exported"),
    ({"exported": "false", "grantUriPermissions": "true"}, False, "providers_cannot_grant_uri_access"),
    ({"exported": "false"}, True, "providers_cannot_grant_uri_access"),
])
def test_provider_exports_and_grants_fail(fixture, attributes, grant_child, check):
    def change(_, app):
        provider = ET.SubElement(app, "provider", {pc.NS + k: v for k, v in attributes.items()})
        if grant_child:
            ET.SubElement(provider, "grant-uri-permission", {pc.NS + "pathPrefix": "/"})
    modify_manifest(fixture, change)
    assert not result(fixture)["checks"][check]


@pytest.mark.parametrize("name", sorted(pc.FILE_PROVIDERS_REQUIRING_GRANT_FLAG))
def test_file_provider_subclasses_need_the_grant_flag_to_start(fixture, name):
    """androidx FileProvider throws at process start without grantUriPermissions=true (real emulator crash)."""
    def add(grant):
        def change(_, app):
            ET.SubElement(app, "provider", {pc.NS + "name": name, pc.NS + "exported": "false",
                                            pc.NS + "grantUriPermissions": grant})
        return change
    modify_manifest(fixture, add("true"))
    assert result(fixture)["checks"]["providers_cannot_grant_uri_access"]
    modify_manifest(fixture, add("false"))
    assert not result(fixture)["checks"]["providers_cannot_grant_uri_access"]


@pytest.mark.parametrize("mode", sorted(pc.MODES))
def test_missing_transfer_mode_fails_including_d2d(fixture, mode):
    modify_rules(fixture, lambda root: root.remove(root.find(mode)))
    assert not result(fixture)["checks"]["all_transfer_modes_denied"]


def test_encrypted_backup_is_not_backup_opt_out(fixture):
    def change(root):
        cloud = root.find("cloud-backup")
        cloud.clear()
        cloud.set("disableIfNoEncryptionCapabilities", "true")
    modify_rules(fixture, change)
    assert not result(fixture)["checks"]["all_transfer_modes_denied"]


@pytest.mark.parametrize("change", [
    lambda r: r.find("device-transfer").remove(r.find("device-transfer")[0]),
    lambda r: r.find("device-transfer")[0].set("path", "./not-everything"),
    lambda r: ET.SubElement(r.find("device-transfer"), "include", domain="root", path="."),
    lambda r: ET.SubElement(r.find("device-transfer"), "exclude", domain="root", path="."),
    lambda r: ET.SubElement(r, "future-unknown-transfer-mode"),
    lambda r: r.find("cross-platform-transfer").set("platform", "unknown"),
])
def test_incomplete_includes_duplicates_unknown_modes_fail(fixture, change):
    modify_rules(fixture, change)
    assert not result(fixture)["checks"]["all_transfer_modes_denied"]


def test_qualified_resource_override_cannot_bypass_default(fixture):
    _, resources = fixture
    directory = resources / "xml-v37"
    directory.mkdir()
    (directory / "no_transfer.xml").write_text("<data-extraction-rules/>")
    assert not result(fixture)["checks"]["all_transfer_modes_denied"]


def test_all_valid_qualified_variants_recorded(fixture):
    _, resources = fixture
    directory = resources / "xml-v37"
    directory.mkdir()
    (directory / "no_transfer.xml").write_bytes((resources / "xml" / "no_transfer.xml").read_bytes())
    report = result(fixture)
    assert all(report["checks"].values())
    assert len(report["resource_evidence"]) == 2


@pytest.mark.parametrize("reference", [None, "@7f010001", "@xml/../../private", "@xml/missing"])
def test_missing_or_unresolved_resources_fail(fixture, reference):
    def change(_, app):
        if reference is None:
            app.attrib.pop(pc.NS + "dataExtractionRules")
        else:
            app.set(pc.NS + "dataExtractionRules", reference)
    modify_manifest(fixture, change)
    assert not result(fixture)["checks"]["all_transfer_modes_denied"]


def test_resource_symlink_escape_fails(fixture, tmp_path):
    _, resources = fixture
    target = tmp_path / "outside.xml"
    original = resources / "xml" / "no_transfer.xml"
    target.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(target)
    report = result(fixture)
    assert not report["checks"]["all_transfer_modes_denied"]
    assert any(e["code"] == "xml_resource_escapes_root" for e in report["input_errors"])


def test_legacy_full_backup_resource_requires_all_domains(fixture):
    _, resources = fixture
    rules = ET.Element("full-backup-content")
    for domain in sorted(pc.DOMAINS):
        ET.SubElement(rules, "exclude", domain=domain, path=".")
    path = resources / "xml" / "legacy.xml"
    ET.ElementTree(rules).write(path, encoding="utf-8")
    modify_manifest(fixture, lambda _, app: app.set(pc.NS + "fullBackupContent", "@xml/legacy"))
    assert result(fixture)["checks"]["legacy_backup_denied"]
    rules.remove(rules[0])
    ET.ElementTree(rules).write(path, encoding="utf-8")
    assert not result(fixture)["checks"]["legacy_backup_denied"]


def test_package_mismatch_fails(fixture):
    assert not pc.audit(*fixture, "org.example.different")["checks"]["expected_package"]


@pytest.mark.parametrize("payload", [
    "not XML", "<manifest>",
    '<!DOCTYPE manifest [<!ENTITY x "abc">]><manifest>&x;</manifest>',
    "<manifest><application/><application/></manifest>",
])
def test_bad_input_cli_fails_nonzero_without_pass(fixture, capsys, payload):
    manifest, resources = fixture
    manifest.write_text(payload)
    assert pc.main(["--manifest", str(manifest), "--resources", str(resources),
                    "--expected-package", PACKAGE]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "NOT RUN / INPUT ERROR"
    assert report["product_containment"] == "NOT RUN / NOT CERTIFIED"


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_dtd_guard_is_not_bypassed_by_utf16(fixture, encoding):
    manifest, _ = fixture
    payload = '<!DOCTYPE manifest [<!ENTITY x "unused">]>' + manifest.read_text()
    manifest.write_bytes(payload.encode(encoding))
    with pytest.raises(pc.AuditInputError, match="xml_dtd_or_entity_forbidden"):
        result(fixture)


def test_cli_exit_codes_for_static_only_success_and_failure(fixture, capsys):
    manifest, resources = fixture
    args = ["--manifest", str(manifest), "--resources", str(resources), "--expected-package", PACKAGE]
    assert pc.main(args) == 0
    assert json.loads(capsys.readouterr().out)["product_containment"] == "NOT RUN / NOT CERTIFIED"
    modify_manifest(fixture, lambda _, app: app.set(pc.NS + "allowBackup", "true"))
    assert pc.main(args) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "FAIL (static policy)"
