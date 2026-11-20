#!/usr/bin/env python3
"""Compose an opt-in, SOURCE-ONLY personal-browser development patch bundle.

No default package is chosen. The existing Swiftra package, Chrome packages,
existing output directories, source profiles and devices are never modified.
Output layout preserves 0013's ../adblock dependency and the existing PUBLIC
signer pin. No keys are copied/generated; no build, dispatch or install happens.
The ordinary patches/series and args.gn remain unchanged. A separate optional
manual development workflow may consume this bundle; this tool does not assess
CI execution. This is not a runnable high-privacy browser, release gate or a
substitute for both-ABI E2E.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}\Z")
VARIANT = re.compile(r"personal-[a-z0-9][a-z0-9-]{0,38}\Z")
BLOCKED_PACKAGES = ("com.swiftra.app", "com.android", "com.google", "org.chromium")


class PreparationError(ValueError):
    pass


def read_regular(path: Path, root: Path) -> bytes:
    """Reject symlinks/special files, including symlinked parent directories."""
    relative = path.relative_to(root)
    cursor = root
    if cursor.is_symlink():
        raise PreparationError("bundle_input_symlink")
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise PreparationError("bundle_input_symlink")
    if not path.is_file():
        raise PreparationError("bundle_input_missing_or_special")
    return path.read_bytes()


def patch_tools(repo: Path):
    spec = importlib.util.spec_from_file_location("personal_base_patch_tools", repo / "scripts/ci/patches.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(repo: Path, output: Path, package: str, variant: str) -> dict:
    if (not PACKAGE.fullmatch(package) or len(package) > 200 or any(
            package == item or package.startswith(item + ".") for item in BLOCKED_PACKAGES)):
        raise PreparationError("explicit_distinct_reviewable_package_required")
    if not VARIANT.fullmatch(variant):
        raise PreparationError("separate_personal_variant_required")
    if os.path.lexists(output):
        raise PreparationError("output_must_not_exist")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise PreparationError("output_parent_must_be_existing_directory")
    repo = repo.resolve(strict=True)
    base = repo / "patches"
    personal = base / "personal"
    read_regular(base / "series", repo)
    read_regular(personal / "series", repo)
    read_regular(repo / "scripts/ci/patches.py", repo)
    helper = patch_tools(repo)
    base_series = helper.read_series(str(base))
    personal_series = helper.read_series(str(personal))
    if not base_series or personal_series != [
            "0100-personal-source-guard.py", "0101-persistent-account-boundary.patch",
            "0102-personal-egress-source-guard.py", "0103-personal-egress-and-storage.patch",
            "0104-face-guard-source-guard.py", "0105-face-guard-presence-mode.patch",
            "0106-personal-signin-source-guard.py", "0107-personal-signin-message.patch",
            "0108-personal-omnibox-source-guard.py", "0109-personal-omnibox-clipboard.patch",
            "0110-personal-google-egress-source-guard.py", "0111-personal-google-egress.patch"]:
        raise PreparationError("unexpected_patch_series")
    if len(set(base_series + personal_series)) != len(base_series + personal_series):
        raise PreparationError("duplicate_patch_name")
    payloads = {}
    for directory, names in ((base, base_series), (personal, personal_series)):
        for name in names:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:py|patch)", name):
                raise PreparationError("unsafe_patch_name")
            payloads["patches/" + name] = read_regular(directory / name, repo)
    args = read_regular(base / "args.gn", repo).decode("utf-8")
    assignments = re.findall(r'^chrome_public_manifest_package\s*=\s*"([^"]+)"\s*$', args, re.M)
    if assignments != ["com.swiftra.app"] or len(re.findall(
            r"^\s*chrome_public_manifest_package\s*=", args, re.M)) != 1:
        raise PreparationError("unexpected_base_package_assignment")
    debug_values = [value.strip() for value in re.findall(
        r"^\s*debuggable_apks\s*=\s*([^\n#]+)", args, re.M)]
    if debug_values != ["false"]:
        raise PreparationError("base_must_remain_nondebuggable")
    args = args.replace('chrome_public_manifest_package = "com.swiftra.app"',
                        'chrome_public_manifest_package = "' + package + '"', 1)
    # A regex-matched but differently formatted assignment must never retain the old package.
    if re.findall(r'^chrome_public_manifest_package\s*=\s*"([^"]+)"\s*$', args, re.M) != [package]:
        raise PreparationError("package_replacement_failed")
    payloads["patches/args.gn"] = args.encode()
    payloads["patches/series"] = (
        "# Generated opt-in SOURCE-ONLY personal development bundle; not a privacy release.\n"
        + "\n".join(base_series + personal_series) + "\n").encode()
    cert = read_regular(base / "signing_cert_sha256.txt", repo)
    # The existing public pin file intentionally includes provenance comments.
    cert_values = [line.strip() for line in cert.decode("utf-8").splitlines()
                   if line.strip() and not line.lstrip().startswith("#")]
    if len(cert_values) != 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", cert_values[0]):
        raise PreparationError("invalid_existing_public_signer_pin")
    payloads["patches/signing_cert_sha256.txt"] = cert
    for relative in helper.overlay_files(str(base)):
        payloads["patches/overlay/" + relative] = read_regular(base / "overlay" / relative, repo)
    payloads["adblock/swiftra-ruleset.pb.gz"] = read_regular(repo / "adblock/swiftra-ruleset.pb.gz", repo)
    # Reserve a NEW directory exclusively. Never replace or clean an existing output.
    output.mkdir()
    try:
        for relative, data in sorted(payloads.items()):
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        receipt = {
            "schema_version": 2,
            "scope": "SOURCE-ONLY OPT-IN DEVELOPMENT BUNDLE; NOT A BUILT OR TESTED BROWSER",
            "pinned_tag": "155.0.8059.80",
            "package": package,
            "variant": variant,
            "base_patch_hash": helper.series_hash(str(base), base_series),
            "composed_patch_hash": helper.series_hash(str(output / "patches"), base_series + personal_series),
            "payload_sha256": {p: hashlib.sha256(b).hexdigest() for p, b in sorted(payloads.items())},
            "product_containment": "NOT RUN / NOT CERTIFIED",
            "release_ready": False,
            "apk_built": False,
            "existing_profile_touched": False,
            "ci_dispatch_performed_by_this_tool": False,
            "ci_workflow_in_repo": ".github/workflows/personal-source-build.yml" if (
                repo / ".github/workflows/personal-source-build.yml").is_file() else None,
            "ci_run_status": "NOT ASSESSED / SOURCE INPUT PREPARATION ONLY",
            "open_runtime_gates": [
                "x64 Actions and native ARM64 E2E", "physical/account/OEM backup acceptance",
                "external navigation/share/clipboard/credential/autofill calls",
                "app-internal downloads and complete storage inventory", "whole-profile encryption/key failure",
                "screen/recents/native-editor IME paths", "network audit", "persistent restart acceptance",
                "personal-package secure update channel; ordinary Swiftra update feed is not this variant",
            ],
        }
        (output / "PERSONAL_SOURCE_ONLY.json").write_text(json.dumps(receipt, indent=2) + "\n")
    except BaseException:
        shutil.rmtree(output)
        raise
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="Explicit distinct DEVELOPMENT application ID; not a migration")
    parser.add_argument("--variant", required=True, help="personal-...; never a1 or b1")
    parser.add_argument("--output", type=Path, required=True, help="New bundle directory; parent must exist")
    args = parser.parse_args(argv)
    try:
        receipt = prepare(ROOT, args.output, args.package, args.variant)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "REFUSED", "product_containment": "NOT RUN / NOT CERTIFIED", "error": (
            str(exc) if isinstance(exc, PreparationError) else "bundle_input_or_io_error")}))
        return 1
    print(json.dumps({key: receipt[key] for key in (
        "scope", "package", "variant", "composed_patch_hash", "product_containment", "release_ready")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
