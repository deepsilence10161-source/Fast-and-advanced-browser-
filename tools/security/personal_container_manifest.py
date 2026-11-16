#!/usr/bin/env python3
"""Strict *static* preflight for a future persistent personal-browser variant.

Input: an already merged/decoded Android manifest and decoded res/ directory.
This does NOT decode/bind an APK, inspect Java/native behavior, change any data,
prove encryption, or certify app containment. A static PASS is never a device
PASS. Every resource configuration is checked; unresolved references fail shut.

The policy deliberately differs from ordinary Chrome compatibility: no platform
account/storage permissions, no provider export/grant, and deny-all backup rules
for legacy, cloud, D2D and the documented iOS transfer mode. No auto-delete or
incognito behavior is introduced. Existing Swiftra build/release gates unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://schemas.android.com/apk/res/android}"
FILE_PROVIDERS_REQUIRING_GRANT_FLAG = frozenset({
    "org.chromium.chrome.browser.util.ChromeFileProvider",
    "org.chromium.chrome.browser.download.DownloadFileProvider",
})
DOMAINS = frozenset({
    "root", "file", "database", "sharedpref", "external", "device_root",
    "device_file", "device_database", "device_sharedpref",
})
MODES = frozenset({"cloud-backup", "device-transfer", "cross-platform-transfer"})
DENIED_PERMISSIONS = frozenset("android.permission." + name for name in (
    "GET_ACCOUNTS", "GET_ACCOUNTS_PRIVILEGED", "MANAGE_ACCOUNTS",
    "AUTHENTICATE_ACCOUNTS", "USE_CREDENTIALS", "READ_SYNC_SETTINGS",
    "WRITE_SYNC_SETTINGS", "READ_SYNC_STATS",
    "CREDENTIAL_MANAGER_QUERY_CANDIDATE_CREDENTIALS",
    "CREDENTIAL_MANAGER_SET_ALLOWED_PROVIDERS", "CREDENTIAL_MANAGER_SET_ORIGIN",
    "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE", "MANAGE_EXTERNAL_STORAGE",
    "ACCESS_MEDIA_LOCATION", "READ_MEDIA_IMAGES", "READ_MEDIA_VIDEO",
    "READ_MEDIA_AUDIO", "READ_MEDIA_VISUAL_USER_SELECTED",
)) | frozenset({"com.google.android.apps.now.CURRENT_ACCOUNT_ACCESS"})
RESOURCE = re.compile(r"@xml/([a-z][a-z0-9_]*)\Z")
MAX_XML_BYTES = 2 * 1024 * 1024


class AuditInputError(ValueError):
    """Unsafe, malformed, missing or unresolved static input."""


def read_xml(path: Path) -> tuple[ET.Element, str]:
    with path.open("rb") as handle:
        data = handle.read(MAX_XML_BYTES + 1)
    if len(data) > MAX_XML_BYTES:
        raise AuditInputError("xml_too_large")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise AuditInputError("xml_dtd_or_entity_forbidden")
    class NoDtdBuilder(ET.TreeBuilder):
        def doctype(self, name, pubid, system):
            # Parser callback also catches UTF-16/32 declarations missed by a byte scan.
            raise AuditInputError("xml_dtd_or_entity_forbidden")

    try:
        root = ET.fromstring(data, parser=ET.XMLParser(target=NoDtdBuilder()))
    except ET.ParseError as exc:
        raise AuditInputError("xml_parse_error") from exc
    return root, hashlib.sha256(data).hexdigest()


def deny_all_section(section: ET.Element) -> bool:
    """Exact whole-domain excludes, no includes, unexpected nodes or paths."""
    seen = set()
    if section.text and section.text.strip():
        return False
    for element in section:
        if (element.tag != "exclude" or set(element.attrib) != {"domain", "path"}
                or element.get("path") != "." or len(element)
                or (element.text and element.text.strip())
                or (element.tail and element.tail.strip())):
            return False
        domain = element.get("domain")
        if domain not in DOMAINS or domain in seen:
            return False
        seen.add(domain)
    return seen == DOMAINS


def resource_variants(reference: str | None, resources: Path):
    match = RESOURCE.fullmatch(reference or "")
    if not match:
        raise AuditInputError("unresolved_xml_resource")
    base = resources.resolve(strict=True)
    name = match.group(1) + ".xml"
    default = base / "xml" / name
    if not default.is_file():
        raise AuditInputError("default_xml_resource_missing")
    candidates = sorted(
        folder / name for folder in base.iterdir()
        if folder.is_dir() and (folder.name == "xml" or folder.name.startswith("xml-"))
        and (folder / name).exists()
    )
    out = []
    for candidate in candidates:
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(base):
            raise AuditInputError("xml_resource_escapes_root")
        root, digest = read_xml(resolved)
        out.append((candidate.relative_to(base).as_posix(), root, digest))
    return out


def modern_rules(root: ET.Element) -> bool:
    if root.tag != "data-extraction-rules" or root.attrib:
        return False
    if root.text and root.text.strip():
        return False
    seen = set()
    for section in root:
        if section.tag not in MODES or section.tag in seen:
            return False
        if section.tail and section.tail.strip():
            return False
        if section.tag == "cross-platform-transfer":
            if section.attrib != {"platform": "ios"}:
                return False
        elif section.tag == "cloud-backup":
            if section.attrib not in ({}, {"disableIfNoEncryptionCapabilities": "true"}):
                return False
        elif section.attrib:
            return False
        if not deny_all_section(section):
            return False
        seen.add(section.tag)
    return seen == MODES


def audit(manifest: Path, resources: Path, expected_package: str) -> dict:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", expected_package):
        raise AuditInputError("invalid_expected_package")
    root, digest = read_xml(manifest)
    apps = root.findall("application")
    if root.tag != "manifest" or len(apps) != 1:
        raise AuditInputError("expected_one_manifest_application")
    app = apps[0]
    permissions = {
        element.get(NS + "name") for element in root
        if element.tag == "uses-permission" or element.tag.startswith("uses-permission-sdk-")
    }
    providers = list(app.findall("provider"))
    checks = {
        "expected_package": root.get("package") == expected_package,
        "no_shared_user_id": NS + "sharedUserId" not in root.attrib,
        "no_shell_profileable": all(
            item.get(NS + "shell", "false") == "false" for item in app.findall("profileable")
        ),
        "not_debuggable": app.get(NS + "debuggable", "false") == "false",
        "not_test_only": app.get(NS + "testOnly", "false") == "false",
        "allow_backup_explicit_false": app.get(NS + "allowBackup") == "false",
        "no_backup_agent": NS + "backupAgent" not in app.attrib,
        "restore_any_version_disabled": app.get(NS + "restoreAnyVersion", "false") == "false",
        "permission_names_resolved": all(
            isinstance(name, str) and re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", name
            ) is not None for name in permissions
        ),
        "no_platform_account_or_shared_storage_permissions": not permissions & DENIED_PERMISSIONS,
        "providers_not_exported": all(p.get(NS + "exported") == "false" for p in providers),
        # androidx FileProvider.attachInfo throws "Provider must grant uri permissions" at process start
        # (real x64 emulator crash, run 43922660826). Only these two non-exported FileProvider subclasses
        # may declare it; they can only hand out access when the app itself attaches a URI grant.
        "providers_cannot_grant_uri_access": all(
            p.get(NS + "grantUriPermissions", "false") == (
                "true" if p.get(NS + "name") in FILE_PROVIDERS_REQUIRING_GRANT_FLAG else "false")
            and not p.findall("grant-uri-permission") for p in providers
        ),
    }
    resource_evidence = []
    errors = []
    legacy = app.get(NS + "fullBackupContent")
    if legacy == "false":
        checks["legacy_backup_denied"] = True
    else:
        try:
            variants = resource_variants(legacy, resources)
            checks["legacy_backup_denied"] = all(
                r.tag == "full-backup-content" and not r.attrib and deny_all_section(r)
                for _, r, _ in variants
            )
            resource_evidence.extend({"path": p, "sha256": h} for p, _, h in variants)
        except (AuditInputError, OSError) as exc:
            checks["legacy_backup_denied"] = False
            errors.append({"check": "legacy_backup_denied", "code": (
                str(exc) if isinstance(exc, AuditInputError) else "resource_io_error")})
    try:
        variants = resource_variants(app.get(NS + "dataExtractionRules"), resources)
        checks["all_transfer_modes_denied"] = all(modern_rules(r) for _, r, _ in variants)
        resource_evidence.extend({"path": p, "sha256": h} for p, _, h in variants)
    except (AuditInputError, OSError) as exc:
        checks["all_transfer_modes_denied"] = False
        errors.append({"check": "all_transfer_modes_denied", "code": (
            str(exc) if isinstance(exc, AuditInputError) else "resource_io_error")})
    return {
        "schema_version": 1,
        "scope": "STATIC DECODED MANIFEST/RESOURCES ONLY; NOT APK OR DEVICE ACCEPTANCE",
        "status": "PASS (static/signature/format only)" if all(checks.values()) else "FAIL (static policy)",
        "product_containment": "NOT RUN / NOT CERTIFIED",
        "manifest_sha256": digest,
        "checks": checks,
        "resource_evidence": resource_evidence,
        "input_errors": errors,
        "not_checked": [
            "APK binding/signature/install", "actual backup/restore/OEM migration behavior",
            "Java/native account and external-intent calls", "clipboard/IME/autofill/credential IPC",
            "network requests/telemetry", "full-profile encryption or Keystore failure",
            "file paths/URI grants at runtime", "screen/recents/accessibility", "persistent restart behavior",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--expected-package", required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(args.manifest, args.resources, args.expected_package)
    except (AuditInputError, OSError) as exc:
        result = {
            "scope": "STATIC INPUT ONLY", "status": "NOT RUN / INPUT ERROR",
            "product_containment": "NOT RUN / NOT CERTIFIED",
            "error": str(exc) if isinstance(exc, AuditInputError) else "input_io_error",
        }
        print(json.dumps(result, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
