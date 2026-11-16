"""Pinned-source/host-component tests only. None are Android/privacy acceptance."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import jinja2
import pytest

ROOT = Path(__file__).resolve().parents[1]
PERSONAL = ROOT / "patches/personal"
FIXTURES = ROOT / "tools/personal_browser"
JAVA = "components/signin/public/android/java/src/org/chromium/components/signin/"
MANIFEST = "chrome/android/java/AndroidManifest.xml"
SIGNIN = "chrome/browser/signin/services/android/java/src/org/chromium/chrome/browser/signin/services/SigninManagerImpl.java"
IME = "content/public/android/java/src/org/chromium/content/browser/input/ImeAdapterImpl.java"
A = "{http://schemas.android.com/apk/res/android}"
T = "{http://schemas.android.com/tools}"
PACKAGE = "org.example.containmentdev"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load("personal_source_guard", PERSONAL / "0100-personal-source-guard.py")
prep = load("personal_prepare", FIXTURES / "prepare.py")
host = load("personal_host_probe", FIXTURES / "host_probe.py")
static = load("personal_static_audit", ROOT / "tools/security/personal_container_manifest.py")
patch_tools = load("personal_patch_tools", ROOT / "scripts/ci/patches.py")
fixture_tools = load("personal_source_fixture", FIXTURES / "source_fixture.py")
egress_guard = load("personal_egress_guard", PERSONAL / "0102-personal-egress-source-guard.py")


@pytest.fixture(scope="module")
def upstream():
    # Both immutable source fixtures retain byte/source-index verification in this helper.
    return fixture_tools.load_sources()


def write_inputs(folder, sources):
    for relative, text in sources.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


@pytest.fixture(scope="module")
def patched(tmp_path_factory, upstream):
    folder = tmp_path_factory.mktemp("personal-pinned-src")
    write_inputs(folder, upstream)
    receipts = fixture_tools.apply_strict(folder)
    assert [row["entry"] for row in receipts] == fixture_tools.series()
    assert len(receipts) == 4
    return folder


def test_real_pinned_patch_applies_and_outputs_are_registered(patched):
    facade = JAVA + "BrowserContainedAccountManagerFacade.java"
    assert (patched / facade).is_file()
    assert '"java/src/org/chromium/components/signin/BrowserContainedAccountManagerFacade.java"' in (
        patched / "components/signin/public/android/BUILD.gn").read_text()
    assert '"java/res_base/xml/personal_no_data_transfer.xml"' in (patched / "chrome/android/BUILD.gn").read_text()
    assert (patched / "chrome/android/java/res_base/xml/personal_no_data_transfer.xml").is_file()
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        guard.check(patched)  # Never treat a second application as pristine source.


@pytest.mark.parametrize("relative", sorted(guard.EXPECTED))
def test_source_drift_is_refused_before_any_write(tmp_path, upstream, relative):
    write_inputs(tmp_path, upstream)
    path = tmp_path / relative
    path.write_text(path.read_text() + "\n// deliberately changed source\n")
    before = {p: (tmp_path / p).read_bytes() for p in upstream}
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        guard.check(tmp_path)
    assert {p: (tmp_path / p).read_bytes() for p in upstream} == before
    assert not any((tmp_path / p).exists() for p in guard.NEW_PATHS)


def test_guard_refuses_missing_and_symlinked_source(tmp_path, upstream):
    write_inputs(tmp_path, upstream)
    relative = next(iter(guard.EXPECTED))
    path = tmp_path / relative
    data = path.read_bytes()
    path.unlink()
    with pytest.raises(ValueError, match="source_input_missing"):
        guard.check(tmp_path)
    outside = tmp_path / "outside-source"
    outside.write_bytes(data)
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="source_symlink_refused"):
        guard.check(tmp_path)


@pytest.mark.parametrize("relative", guard.NEW_PATHS)
def test_guard_will_not_replace_existing_new_output(tmp_path, upstream, relative):
    write_inputs(tmp_path, upstream)
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("preserve existing output")
    with pytest.raises(ValueError, match="new_source_output_already_exists"):
        guard.check(tmp_path)
    assert path.read_text() == "preserve existing output"


def test_guard_targets_do_not_overlap_the_ordinary_series():
    touched = set()
    for name in patch_tools.read_series(str(ROOT / "patches")):
        if name.endswith(".patch"):
            touched.update(patch_tools.patched_files(ROOT / "patches" / name))
    guarded_paths = set(guard.EXPECTED) | set(egress_guard.EXPECTED)
    assert not touched.intersection(guarded_paths)
    # Transform scripts have their own input sets. Check the current ones explicitly too.
    for name in patch_tools.read_series(str(ROOT / "patches")):
        if name.endswith(".py"):
            text = (ROOT / "patches" / name).read_text()
            assert not any(path in text for path in guarded_paths)


def test_provider_does_not_even_initialize_a_platform_delegate(patched):
    provider = (patched / JAVA / "AccountManagerFacadeProvider.java").read_text()
    assert "INSTANCE = new BrowserContainedAccountManagerFacade();" in provider
    assert "ServiceLoaderUtil" not in provider
    assert "new AccountManagerFacadeImpl" not in provider
    assert "AccountManagerDelegate" not in provider
    facade = (patched / JAVA / "BrowserContainedAccountManagerFacade.java").read_text()
    assert "AccountManager.get" not in facade
    assert "ContextUtils" not in facade and "RecordUserAction" not in facade
    assert "getAccounts().then" not in facade
    assert "new AccountCapabilities(new String[0], new boolean[0])" in facade
    assert "callback.onGetTokenFailure" in facade
    assert "GoogleServiceAuthErrorState.REQUEST_CANCELED" in facade


def method(text, signature):
    start = text.index(signature)
    start = text.index("{", start)
    depth = 1
    end = start + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start + 1:end - 1]


def test_signin_entry_points_reject_without_signout_or_wipe(patched):
    text = (patched / SIGNIN).read_text()
    for signature in ("boolean isSigninAllowed()", "boolean isSigninSupported(", "boolean isSwitchAccountAllowed()"):
        body = method(text, signature)
        assert "return false;" in body
        assert "mPrefService" not in body and "ExternalAuthUtils" not in body
    body = method(text, "public void signin(")
    assert "callback::onSignInAborted" in body
    assert "signinInternal(" not in body
    assert "signOut(" not in body and "wipe" not in body.lower()
    body = method(text, "public void turnOnSyncForTesting(")
    assert "UnsupportedOperationException" in body and "setPrimaryAccount" not in body


def test_keyboard_learning_is_disabled_for_both_public_overloads(patched):
    text = (patched / IME).read_text()
    body = method(text, "InputConnection onCreateInputConnection(EditorInfo outAttrs)")
    assert "onCreateInputConnection(outAttrs, false)" in body
    assert "isIncognito" not in body
    body = method(text, "ChromiumBaseInputConnection onCreateInputConnection(")
    assert "outAttrs.imeOptions |= EditorInfoCompat.IME_FLAG_NO_PERSONALIZED_LEARNING;" in body
    assert "if (!allowKeyboardLearning)" not in body
    assert "offline-keyboard guarantee" in body


def rendered_manifest(patched, channel, backup_key, definitions_in_split="false"):
    # A source-template model ONLY. tools:node removes below model tombstones,
    # not the real Android manifest merger, dependencies or final APK.
    context = dict(manifest_package=PACKAGE, channel=channel, library_name="chrome",
                   zygote_preload_class="org.example.Preloader", target_sdk_version="37",
                   definitions_in_split=definitions_in_split)
    if backup_key:
        context["backup_key"] = "public-synthetic-backup-key"
    xml = jinja2.Environment().from_string((patched / MANIFEST).read_text()).render(**context)
    root = ET.fromstring(xml)
    for parent in root.iter():
        for node in list(parent):
            if node.get(T + "node") == "remove":
                parent.remove(node)
    return root


@pytest.mark.parametrize("channel", ["stable", "beta", "dev", "canary", "default"])
@pytest.mark.parametrize("backup_key", [False, True])
@pytest.mark.parametrize("definitions_in_split", ["false", "true"])
def test_source_manifest_policy_in_synthetic_jinja_configs(patched, tmp_path, channel, backup_key, definitions_in_split):
    root = rendered_manifest(patched, channel, backup_key, definitions_in_split)
    path = tmp_path / "AndroidManifest.xml"
    ET.ElementTree(root).write(path)
    resources = patched / "chrome/android/java/res_base"
    report = static.audit(path, resources, PACKAGE)
    assert all(report["checks"].values()), report["checks"]
    assert report["product_containment"] == "NOT RUN / NOT CERTIFIED"
    assert not root.findall(".//meta-data[@" + A + "name='com.google.android.backup.api_key']")
    assert root.find("application").get(A + "fullBackupContent") == "false"
    assert "APK binding/signature/install" in report["not_checked"]


def test_permission_tombstones_cover_merger_reintroduction(patched):
    xml = (patched / MANIFEST).read_text()
    env = jinja2.Environment()
    root = ET.fromstring(env.from_string(xml).render(
        manifest_package=PACKAGE, channel="default", library_name="chrome",
        zygote_preload_class="org.example.Preloader"))
    removes = {p.get(A + "name") for p in root.findall("uses-permission") if p.get(T + "node") == "remove"}
    assert static.DENIED_PERMISSIONS.issubset(removes)
    assert "com.google.android.apps.now.CURRENT_ACCOUNT_ACCESS" in removes
    assert "android.permission.INTERNET" not in removes


def test_no_persistent_data_deletion_added():
    patch = (PERSONAL / "0101-persistent-account-boundary.patch").read_text()
    added = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
    for forbidden in ("pm clear", "deleteRecursive", "deleteRecursively", ".delete(", "clearBrowsingData(",
                      "wipeSyncUserData(", "signOut(", "setIncognito(", "--incognito"):
        assert forbidden not in added


def test_actual_facade_and_provider_compile_and_execute_on_host(patched):
    report = host.run_probe(patched)
    assert report["status"] == "PASS (host component with stubs)", report
    assert report["output"] == "PERSONAL_ACCOUNT_HOST_PROBE assertions=29"
    assert report["product_containment"] == "NOT RUN / NOT CERTIFIED"
    assert report["dependency_stubs"]


@pytest.mark.parametrize("old,new", [
    ("callback.onResult(null)", "callback.onResult(new Intent())"),
    ("GoogleServiceAuthErrorState.REQUEST_CANCELED", "0"),
    ("if (completedRunnable != null) completedRunnable.run();", "// deliberately drop completion"),
])
def test_host_probe_rejects_account_intent_and_callback_regressions(patched, old, new):
    source = (patched / JAVA / "BrowserContainedAccountManagerFacade.java").read_text()
    assert old in source
    # Alter only the Add Account callback, not the separate Bundle callback.
    report = host.run_probe(patched, facade_override=source.replace(old, new, 1))
    assert report.get("javac_exit") == 0, report
    assert report["status"] == "FAIL (host component)", report
    assert report["mutation_control"]


@pytest.mark.parametrize("package", [
    "com.swiftra.app", "com.swiftra.app.child", "com.android.chrome", "com.google.chrome.dev",
    "org.chromium.chrome", "org.chromium.personal", "org.example.thing\n#injection", "two.parts",
    "org.example.9invalid", "org.example.bad-name", "org.Example.invalid", "../org.example.thing",
])
def test_bundle_never_reuses_existing_browser_package(tmp_path, package):
    output = tmp_path / "bundle"
    with pytest.raises(prep.PreparationError, match="explicit_distinct"):
        prep.prepare(ROOT, output, package, "personal-test")
    assert not output.exists()


@pytest.mark.parametrize("variant", ["a1", "b1", "personal-", "personal-X", "personal-a/../b", "personal-a\nb1"])
def test_bundle_cannot_target_ordinary_build_state(tmp_path, variant):
    with pytest.raises(prep.PreparationError, match="separate_personal_variant"):
        prep.prepare(ROOT, tmp_path / "bundle", PACKAGE, variant)


def test_bundle_is_explicit_separate_and_reproducible(tmp_path):
    before = {p: (ROOT / "patches" / p).read_bytes() for p in ("args.gn", "series", "signing_cert_sha256.txt")}
    first = prep.prepare(ROOT, tmp_path / "one", PACKAGE, "personal-host-test")
    second = prep.prepare(ROOT, tmp_path / "two", PACKAGE, "personal-host-test")
    assert first == second
    assert first["product_containment"] == "NOT RUN / NOT CERTIFIED"
    assert not first["release_ready"] and not first["apk_built"]
    assert not first["ci_dispatch_performed_by_this_tool"]
    assert first["ci_workflow_in_repo"] == ".github/workflows/personal-source-build.yml"
    assert first["ci_run_status"] == "NOT ASSESSED / SOURCE INPUT PREPARATION ONLY"
    assert first["package"] == PACKAGE
    assert {p: (ROOT / "patches" / p).read_bytes() for p in before} == before
    series = patch_tools.read_series(str(tmp_path / "one/patches"))
    native_series = patch_tools.read_series(str(PERSONAL))
    assert len(native_series) == 4
    assert series[:-len(native_series)] == patch_tools.read_series(str(ROOT / "patches"))
    assert series[-len(native_series):] == native_series
    assert first["base_patch_hash"] != first["composed_patch_hash"]
    assert (tmp_path / "one/adblock/swiftra-ruleset.pb.gz").read_bytes() == (ROOT / "adblock/swiftra-ruleset.pb.gz").read_bytes()
    for relative, digest in first["payload_sha256"].items():
        assert hashlib.sha256((tmp_path / "one" / relative).read_bytes()).hexdigest() == digest
    assert PACKAGE in (tmp_path / "one/patches/args.gn").read_text()
    assert "com.swiftra.app\"" not in (tmp_path / "one/patches/args.gn").read_text()


def test_bundle_refuses_existing_directory_and_preserves_files(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "preserve"
    marker.write_text("retain this data")
    with pytest.raises(prep.PreparationError, match="output_must_not_exist"):
        prep.prepare(ROOT, output, PACKAGE, "personal-test")
    assert marker.read_text() == "retain this data"


def test_bundle_refuses_symlink_output_and_inputs(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (tmp_path / "symlink").symlink_to(target)
    with pytest.raises(prep.PreparationError, match="output_must_not_exist"):
        prep.prepare(ROOT, tmp_path / "symlink", PACKAGE, "personal-test")
    source = tmp_path / "linked"
    source.symlink_to(ROOT / "patches/args.gn")
    with pytest.raises(prep.PreparationError, match="bundle_input_symlink"):
        prep.read_regular(source, tmp_path)


def test_bundle_rejects_a_later_debug_override(tmp_path, monkeypatch):
    original = prep.read_regular
    def changed(path, root):
        data = original(path, root)
        return data + b"\ndebuggable_apks = true\n" if path == ROOT / "patches/args.gn" else data
    monkeypatch.setattr(prep, "read_regular", changed)
    with pytest.raises(prep.PreparationError, match="base_must_remain_nondebuggable"):
        prep.prepare(ROOT, tmp_path / "bundle", PACKAGE, "personal-test")
    assert not (tmp_path / "bundle").exists()


def test_existing_patch_engine_tracks_the_opt_in_native_layer(tmp_path, upstream):
    source = tmp_path / "src"
    source.mkdir()
    write_inputs(source, upstream)
    output = tmp_path / "state.json"
    assert patch_tools.apply(str(source), str(PERSONAL), "-", str(output), now=1234567890) == 0
    state = json.loads(output.read_text())
    assert state["series"] == patch_tools.read_series(str(PERSONAL))
    assert set(state["files"]) == (set(guard.EXPECTED) | set(guard.NEW_PATHS)
                                   | set(egress_guard.EXPECTED) | set(egress_guard.NEW_PATHS))
    assert state["epoch"] == 1234567890 and state["changed"]
    for path in state["files"]:
        assert (source / path).stat().st_mtime == 1234567890


@pytest.mark.parametrize("pin", [b"not-a-digest", b"0" * 64 + b"\n" + b"1" * 64])
def test_bundle_refuses_invalid_or_ambiguous_public_signer_pin(tmp_path, monkeypatch, pin):
    original = prep.read_regular
    def changed(path, root):
        return pin if path == ROOT / "patches/signing_cert_sha256.txt" else original(path, root)
    monkeypatch.setattr(prep, "read_regular", changed)
    with pytest.raises(prep.PreparationError, match="invalid_existing_public_signer_pin"):
        prep.prepare(ROOT, tmp_path / "bundle", PACKAGE, "personal-test")
    assert not (tmp_path / "bundle").exists()


def test_prepare_cli_failure_is_explicit_not_native_pass(tmp_path, capsys):
    assert prep.main(["--package", "com.swiftra.app", "--variant", "personal-test", "--output", str(tmp_path / "bundle")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "REFUSED"
    assert report["product_containment"] == "NOT RUN / NOT CERTIFIED"
