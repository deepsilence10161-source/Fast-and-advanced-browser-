"""Second personal source layer: real source/host logic, NEVER Android acceptance."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import random

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools/personal_browser"
LAYER = ROOT / "patches/personal"
NAV = "components/external_intents/android/java/src/org/chromium/components/external_intents/ExternalNavigationHandler.java"
SHARE = "components/browser_ui/share/android/java/src/org/chromium/components/browser_ui/share/ShareHelper.java"
PATHS = "base/android/java/src/org/chromium/base/PathUtils.java"
PREFS = "chrome/browser/download/download_prefs.cc"
TARGET = "chrome/browser/download/download_target_determiner.cc"
DIRS = "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/DownloadDirectoryProvider.java"
SYSTEM = "chrome/browser/download/android/java/src/org/chromium/chrome/browser/download/DownloadManagerBridge.java"
COLLECTION = "components/download/internal/common/android/java/src/org/chromium/components/download/DownloadCollectionBridge.java"
SERVICE = "chrome/android/java/src/org/chromium/chrome/browser/download/DownloadManagerService.java"
UTILS = "chrome/android/java/src/org/chromium/chrome/browser/download/DownloadUtils.java"
BASE = "chrome/android/java/src/org/chromium/chrome/browser/ChromeBaseAppCompatActivity.java"
SNAPSHOT = "chrome/android/java/src/org/chromium/chrome/browser/incognito/IncognitoSnapshotController.java"
CLIP = "ui/android/java/src/org/chromium/ui/base/Clipboard.java"
PRIVATE_CLIP = "ui/android/java/src/org/chromium/ui/base/BrowserContainedClipboard.java"


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixtures = load("egress_source_fixtures", TOOLS / "source_fixture.py")
guard = load("egress_source_guard", LAYER / "0102-personal-egress-source-guard.py")
host = load("egress_host_probe", TOOLS / "egress_host_probe.py")


@pytest.fixture(scope="module")
def originals():
    return fixtures.load_sources()


@pytest.fixture(scope="module")
def patched(tmp_path_factory, originals):
    root = tmp_path_factory.mktemp("personal-egress-pinned")
    for relative, text in originals.items():
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
    receipts = fixtures.apply_strict(root)
    assert len(receipts) == 8
    assert all(row.get("fuzz", 0) == 0 and row.get("offset", 0) == 0 for row in receipts)
    return root


def body(text, signature):
    """Read a pinned method body while ignoring braces in comments/literals."""
    assert text.count(signature) == 1, signature
    start = text.index("{", text.index(signature))
    i, depth, state = start + 1, 1, None
    while depth:
        char, pair = text[i], text[i:i + 2]
        if state == "line":
            if char == "\n":
                state = None
        elif state == "block":
            if pair == "*/":
                state = None
                i += 1
        elif state in ('"', "'"):
            if char == "\\":
                i += 1
            elif char == state:
                state = None
        elif pair == "//":
            state = "line"
            i += 1
        elif pair == "/*":
            state = "block"
            i += 1
        elif char in ('"', "'"):
            state = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        i += 1
    return text[start + 1:i - 1]


@pytest.mark.parametrize("relative", sorted(guard.EXPECTED))
def test_every_new_source_input_is_pinned_and_refused_on_drift(tmp_path, originals, relative):
    for name in guard.EXPECTED:
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(originals[name])
    guard.check(tmp_path)
    file = tmp_path / relative
    file.write_text(file.read_text() + "\n// drift\n")
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        guard.check(tmp_path)
    assert not any((tmp_path / path).exists() for path in guard.NEW_PATHS)


@pytest.mark.parametrize("relative", sorted(guard.EXPECTED))
def test_missing_new_source_cannot_be_silently_skipped(tmp_path, originals, relative):
    for name in guard.EXPECTED:
        if name != relative:
            file = tmp_path / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(originals[name])
    with pytest.raises(ValueError, match="source_input_missing"):
        guard.check(tmp_path)


@pytest.mark.parametrize("signature", [
    "public OverrideUrlLoadingResult shouldOverrideUrlLoading(",
    "private OverrideUrlLoadingResult doStartActivity(",
    "protected OverrideUrlLoadingResult startActivity(",
    "private OverrideUrlLoadingResult startActivityWithChooser(",
])
def test_navigation_entry_and_terminal_sinks_return_no_external_action(patched, signature):
    code = body((patched / NAV).read_text(), signature)
    assert "return OverrideUrlLoadingResult.forNoOverride();" in code
    for forbidden in ("parseUri", "getUrl()", "startActivity(", "showCancelableIntent(", "resolveActivity(", "Log."):
        assert forbidden not in code


def test_share_cancels_without_payload_or_chooser_and_low_level_fire_is_denied(patched):
    text = (patched / SHARE).read_text()
    code = body(text, "public static void shareWithSystemShareSheetUi(")
    assert "callback::onCancel" in code and "TaskTraits.UI_DEFAULT" in code
    assert "getShareIntent" not in code and "TargetChosenReceiver(" not in code
    code = body(text, "protected static void fireIntent(")
    assert "Activity.RESULT_CANCELED, null" in code
    assert "window.showIntent" not in code and ".startActivity" not in code
    code = body(text, "protected void sendChooserIntent(")
    assert "cancel();" in code and "registerReceiver" not in code and "fireIntent" not in code


def test_private_clipboard_and_native_header_are_in_build_targets(patched):
    assert "new BrowserContainedClipboard()" in body((patched / CLIP).read_text(), "Clipboard getInstance()")
    assert '"java/src/org/chromium/ui/base/BrowserContainedClipboard.java"' in (patched / "ui/android/BUILD.gn").read_text()
    assert '"browser_contained_download_path.h"' in (patched / "chrome/browser/download/BUILD.gn").read_text()
    text = (patched / PRIVATE_CLIP).read_text()
    for forbidden in ("ContextUtils", "ClipboardManager", "FileProvider", "ContentResolver", "getSystemService("):
        # Documentation names these threats; production statements must not call them.
        statements = "\n".join(line for line in text.splitlines()
                               if not line.lstrip().startswith(("//", "*", "/**")))
        assert forbidden not in statements
    assert "void onWindowFocusChanged" not in text  # Base no-op: no focus-loss wipe.


@pytest.mark.parametrize("signature", [
    "String getDownloadsDirectory()", "String[] getAllPrivateDownloadsDirectories()",
    "String[] getExternalDownloadVolumesNames()",
])
def test_java_download_locations_do_not_enumerate_external_or_media_storage(patched, signature):
    code = body((patched / PATHS).read_text(), signature)
    for forbidden in ("getExternalFilesDirs", "MediaStore", "getCache", "Environment.", "ForTesting"):
        assert forbidden not in code
    assert "getDataDirectory()" in code or "getDownloadsDirectory()" in code or "new String[0]" in code


def test_internal_directory_failure_has_no_shared_or_cache_fallback_or_delete(patched):
    text = (patched / DIRS).read_text()
    code = body(text, "public static @Nullable File getPrimaryDownloadDirectory()")
    assert "getCanonicalFile()" in code and "mkdirs()" in code
    assert "return null;" in code and "getDataDirectory()" in code
    assert ".delete" not in code and "getCacheDir" not in code and "Environment" not in code
    assert "registerSDCardReceiver" not in body(text, "protected DownloadDirectoryProvider()")
    assert "Environment" not in body(text, "protected ArrayList<DirectoryOption> doInBackground()")
    assert "return false;" in body((patched / SERVICE).read_text(), "private boolean isFilePathOnMissingExternalDrive(")
    assert "getExternalStorageDirectory" not in body((patched / SERVICE).read_text(), "private void maybeShowMissingSdCardError(")


def test_native_root_does_not_trust_preferences_or_temp_fallback_on_android(patched):
    text = (patched / PREFS).read_text()
    code = body(text, "  void Initialize()")
    android = code.split("#if BUILDFLAG(IS_ANDROID)", 1)[1].split("#else", 1)[0]
    assert "base::DIR_ANDROID_APP_DATA" in android and 'Append("Downloads")' in android
    assert "GetTempDir" not in android and "private_root.ReferencesParent()" in android
    code = body(text, "base::FilePath DownloadPrefs::SanitizeDownloadTargetPath(")
    android = code.split("#if BUILDFLAG(IS_ANDROID)", 1)[1].split("#else", 1)[0]
    assert "return GetDefaultDownloadDirectoryForProfile();" in android
    assert "skip_sanitize_download_target_path_for_testing_" not in android


@pytest.mark.parametrize("signature", [
    "bool DownloadPrefs::IsAutoOpenEnabled(", "bool DownloadPrefs::IsAutoOpenByPolicy(",
    "bool DownloadPrefs::IsAutoOpenByUserUsed()", "bool DownloadPrefs::EnableAutoOpenByUserBasedOnExtension(",
])
def test_auto_open_cannot_claim_to_be_enabled_against_the_containment_policy(patched, signature):
    code = body((patched / PREFS).read_text(), signature)
    assert "#if BUILDFLAG(IS_ANDROID)" in code
    android = code.split("#if BUILDFLAG(IS_ANDROID)", 1)[1].split("#else", 1)[0]
    assert "return false;" in android
    assert "insert(" not in android and "SaveAutoOpenState" not in android


@pytest.mark.parametrize("signature,operation", [
    ("DownloadTargetDeterminer::DoReserveVirtualPath()", "delegate_->ReserveVirtualPath("),
    ("DownloadTargetDeterminer::DoDetermineLocalPath()", "delegate_->DetermineLocalPath("),
    ("void DownloadTargetDeterminer::DetermineLocalPathDone(", "local_path_ = local_path;"),
    ("void DownloadTargetDeterminer::ScheduleCallbackAndDeleteSelf(", "download::DownloadTargetInfo target_info;"),
])
def test_native_guards_precede_reservation_platform_substitution_and_success(patched, signature, operation):
    code = body((patched / TARGET).read_text(), signature)
    assert code.index("IsBrowserContainedDownloadPath(") < code.index(operation)
    assert "DOWNLOAD_INTERRUPT_REASON_FILE_ACCESS_DENIED" in code


def test_target_patch_only_adds_guards_without_removing_existing_security_lines():
    patch = (LAYER / "0103-personal-egress-and-storage.patch").read_text()
    start = patch.index("+++ b/" + TARGET + "\n")
    end = patch.find("\n--- ", start)
    fragment = patch[start:end if end >= 0 else None]
    assert not any(line.startswith("-") for line in fragment.splitlines())


@pytest.mark.parametrize("signature,value", [
    ("String createIntermediateUriForPublish(", "null"),
    ("boolean shouldPublishDownload(", "false"),
    ("boolean copyFileToIntermediateUri(", "false"),
    ("String publishDownload(", '""'),
    ("int openIntermediateUri(", "-1"),
    ("boolean renameDownloadUri(", "false"),
    ("Uri getDownloadUriForFileName(", "null"),
    ("String getDisplayName(", "null"),
])
def test_media_store_entry_points_fail_without_system_io(patched, signature, value):
    code = body((patched / COLLECTION).read_text(), signature)
    assert "return " + value + ";" in code
    for forbidden in ("getContentResolver", "openPending", "FileUtils.copy", "createPending", ".publish("):
        assert forbidden not in code


def test_legacy_downloader_denies_before_cookie_referrer_copy_and_at_sink(patched):
    code = body((patched / SERVICE).read_text(), "public void enqueueNewDownload(")
    assert "onDownloadFailed" in code and "TaskTraits.UI_DEFAULT" in code
    assert "getCookie" not in code and "getReferrer" not in code and "DownloadEnqueueRequest" not in code
    text = (patched / SYSTEM).read_text()
    code = body(text, "public static void enqueueNewDownload(")
    assert "response.result = false" in code and "callback.onResult(response)" in code
    assert "EnqueueNewDownloadTask" not in code
    code = body(text, "public Boolean doInBackground()")
    assert "return false;" in code and ".enqueue(" not in code and '"Cookie"' not in code
    assert "getSystemService" not in body(text, "public static DownloadQueryResult queryDownloadResult(")
    assert "manager.remove" not in body(text, "public static void removeCompletedDownload(")


@pytest.mark.parametrize("signature", [
    "public static boolean openFileWithExternalApps(", "private static boolean showDownloadInFilesApp(",
    "private static boolean openDownloadInFilesAppIfNoHandlerFound()", "static boolean fireOpenIntentForDownload(",
])
def test_download_external_viewer_chooser_and_files_fallback_deny(patched, signature):
    code = body((patched / UTILS).read_text(), signature)
    assert "return false;" in code
    assert "startActivity" not in code and "createViewIntent" not in code


def test_internal_viewer_is_pinned_to_own_package_and_hides_export_actions(patched):
    text = (patched / UTILS).read_text()
    code = body(text, "private static boolean doOpenFile(")
    assert "openInChromeInternal(req)" in code
    for forbidden in ("resolveActivity", "getPackageManager", "openFileWithExternalApps", "fireOpenIntent", "ACTION_VIEW_DOWNLOADS"):
        assert forbidden not in code
    code = body(text, "static boolean openInChromeInternal(")
    assert "intent.setPackage(ownPackage)" in code and "getComponent().getPackageName()" in code
    assert "/* allowExternalAppHandlers= */ false" in code and "/* allowShareAction= */ false" in code
    assert "ACTION_VIEW_DOWNLOADS" not in body((patched / SERVICE).read_text(), "public static void openDownloadsPage(")


def test_window_hardening_precedes_view_creation_and_normal_transition_cannot_clear(patched):
    code = body((patched / BASE).read_text(), "protected void onCreate(")
    assert code.index("FLAG_SECURE") < code.index("super.onCreate(")
    assert "setRecentsScreenshotEnabled(false)" in code
    assert "IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS" in code
    assert "IMPORTANT_FOR_CONTENT_CAPTURE_NO_EXCLUDE_DESCENDANTS" in code
    code = body((patched / SNAPSHOT).read_text(), "protected void updateIncognitoTabSnapshotState()")
    assert "FLAG_SECURE" in code and "clearFlags" not in code and "sIncognitoScreenshot" not in code


def test_source_layer_adds_no_profile_wipe_or_real_file_deletion():
    patch = (LAYER / "0103-personal-egress-and-storage.patch").read_text()
    added = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
    for forbidden in ("pm clear", "deleteRecursive", ".delete(", "clearBrowsingData(", "wipeSyncUserData(",
                      "removeAllCookies(", "--incognito", "setIncognito("):
        assert forbidden not in added


def path_cases():
    root = b"/data/user/0/org.example.containmentdev/app_chrome/Downloads"
    cases = [(root, root + b"/" + name, True) for name in (
        b"file.bin", b"file (1).bin", b"file.crdownload", b"Unconfirmed 123.crdownload", b"..not-parent", b"\xe0\xa4\xa8.bin")]
    cases += [(root, value, False) for value in (
        b"", root, root + b"/", root + b"/.", root + b"/..", root + b"//file", root + b"/a/b",
        root + b"/../outside", root + b"_sibling/file", root + b"x/file", root + b"/file\0tail",
        b"content://media/external/downloads/1", b"file://" + root + b"/file", b"/sdcard/Download/file",
        b"/storage/emulated/0/Download/file", b"relative/file")]
    cases += [(value, value + b"/file", False) for value in (
        b"", b"/", b"relative", b"/data/./Downloads", b"/data/../Downloads", b"/data//Downloads", b"/data/Downloads/", b"/data\0/Downloads")]
    rng = random.Random(155805980)
    # Independent adversarial component construction, not a claim of comprehensive security fuzzing.
    for _ in range(2000):
        name = ("f" + str(rng.randrange(10000000)) + ".bin").encode()
        cases.append((root, root + b"/" + name, True))
        cases.append((root, root + b"/../" + name, False))
        cases.append((root, root + b"_other/" + name, False))
    return cases


def test_real_native_predicate_with_sanitizers_and_adversarial_paths(patched):
    cases = path_cases()
    report = host.run_paths(patched, cases)
    (patched / "HOST_PATH_PROBE.json").write_text(json.dumps(report, indent=2) + "\n")
    assert report["status"] == "PASS (host native predicate, sanitized)", report
    assert not report["dependency_stubs"] and report["output_lines"] == len(cases)
    assert report["product_containment"] == "NOT RUN / NOT CERTIFIED"


def test_native_predicate_mutation_cannot_reintroduce_parent_or_sibling_paths(patched):
    source = (patched / host.PATH_HEADER).read_text()
    old = 'candidate[root.size()] != \'/\''
    assert old in source
    mutated = source.replace(old, "false", 1)
    # A same-length prefix without the separator is rejected by the production helper.
    root = b"/data/private/Downloads"
    cases = [(root, root + b"xfile", False)]
    report = host.run_paths(patched, cases, override=mutated)
    assert report["compiler_exit"] == 0 and report["runtime_exit"] == 0, report
    assert report["status"] == "FAIL (host native predicate)", report
    assert report["mismatch_indices"] == [0]


def test_real_private_clipboard_and_snapshot_classes_on_host(patched):
    report = host.run_java(patched)
    (patched / "HOST_JAVA_EGRESS_PROBE.json").write_text(json.dumps(report, indent=2) + "\n")
    assert report["status"] == "PASS (host component with stubs)", report
    assert report["assertions"] >= 40, report
    assert report["product_containment"] == "NOT RUN / NOT CERTIFIED"


@pytest.mark.parametrize("relative,old,new", [
    (CLIP, "new BrowserContainedClipboard()", '''new ClipboardImpl((android.content.ClipboardManager)
        org.chromium.base.ContextUtils.getApplicationContext().getSystemService(android.content.Context.CLIPBOARD_SERVICE))'''),
    (PRIVATE_CLIP, "mPng = png == null ? null : png.clone();", "mPng = png;"),
    (SNAPSHOT, "mWindow.addFlags(WindowManager.LayoutParams.FLAG_SECURE);", "mWindow.clearFlags(WindowManager.LayoutParams.FLAG_SECURE);"),
])
def test_host_probe_rejects_platform_clipboard_alias_and_secure_flag_regressions(patched, relative, old, new):
    source = (patched / relative).read_text()
    assert old in source
    key = next(key for key, value in host.JAVA_PATHS.items() if value == relative)
    report = host.run_java(patched, overrides={key: source.replace(old, new, 1)})
    assert report["compiler_exit"] == 0, report
    assert report["status"] == "FAIL (host component)", report
    assert report["runtime_exit"] != 0 and report["mutation_control"]
