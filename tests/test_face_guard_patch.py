"""Source-level checks of the opt-in Face Guard patch layer (0104 guard + 0105 patch).

These are HOST checks of patch structure only. They do not prove Face Guard works on a device.
"""
import hashlib
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PERSONAL = ROOT / "patches/personal"
PATCH = PERSONAL / "0105-face-guard-presence-mode.patch"
GUARD = PERSONAL / "0104-face-guard-source-guard.py"
FG = ROOT / "tools/face_guard/src/org/chromium/chrome/browser/swiftra/faceguard"
J = "chrome/android/java/src/org/chromium/chrome/browser/swiftra/faceguard/"


def guard_module():
    spec = importlib.util.spec_from_file_location("fg_guard", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def patch_text():
    return PATCH.read_text(encoding="utf-8")


def test_series_is_personal_only_and_ordered():
    names = [n for n in (PERSONAL / "series").read_text().splitlines() if n and not n.startswith("#")]
    assert names[4:6] == ["0104-face-guard-source-guard.py", "0105-face-guard-presence-mode.patch"]
    assert names[6:8] == ["0106-personal-signin-source-guard.py", "0107-personal-signin-message.patch"]
    assert names[8:] == ["0108-personal-omnibox-source-guard.py", "0109-personal-omnibox-clipboard.patch"]
    assert names.index("0103-personal-egress-and-storage.patch") < names.index(names[4])
    ordinary = (ROOT / "patches/series").read_text()
    assert "face-guard" not in ordinary and "0104" not in ordinary and "0105" not in ordinary


def test_patch_touches_exactly_the_guarded_files_and_new_files():
    guard = guard_module()
    text = patch_text()
    plus = re.findall(r"^\+\+\+ b/(\S+)$", text, re.M)
    minus_null = re.findall(r"^--- /dev/null$", text, re.M)
    assert len(plus) == len(set(plus))
    created = [p for p in plus if p in guard.NEW_PATHS]
    modified = [p for p in plus if p not in guard.NEW_PATHS]
    assert sorted(created) == sorted(guard.NEW_PATHS) and len(minus_null) == len(guard.NEW_PATHS)
    assert sorted(modified) == sorted(guard.EXPECTED)
    assert all(not p.startswith(("/", "..")) and ".." not in p.split("/") for p in plus)


def test_every_new_java_file_is_listed_in_the_build_and_matches_the_repo_copy():
    text = patch_text()
    for path in sorted(FG.glob("*.java")):
        assert ('"java/src/org/chromium/chrome/browser/swiftra/faceguard/%s"' % path.name) in text, path.name
        body = "".join("+" + line for line in path.read_text().splitlines(True))
        assert body.rstrip("\n") in text, "patch copy of %s differs from tools/face_guard" % path.name
    assert "tab_ui/FaceGuardLockState.java" in text


def test_guard_pins_and_refuses_drift_and_existing_outputs(tmp_path):
    guard = guard_module()
    for relative in guard.EXPECTED:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x")
    guard.EXPECTED = {k: hashlib.sha256(b"x").hexdigest() for k in guard.EXPECTED}
    guard.check(tmp_path)  # pristine -> ok
    victim = next(iter(guard.EXPECTED))
    (tmp_path / victim).write_bytes(b"changed")
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        guard.check(tmp_path)
    (tmp_path / victim).write_bytes(b"x")
    created = tmp_path / guard.NEW_PATHS[0]
    created.parent.mkdir(parents=True, exist_ok=True)
    created.write_text("already here")
    with pytest.raises(ValueError, match="new_source_output_already_exists"):
        guard.check(tmp_path)
    created.unlink()
    (tmp_path / "missing_root_marker").write_text("")
    with pytest.raises(ValueError):
        guard.check(tmp_path / "does-not-exist")


def test_guard_hashes_are_sha256_and_not_shared_with_earlier_guards():
    guard = guard_module()
    assert all(re.fullmatch(r"[0-9a-f]{64}", v) for v in guard.EXPECTED.values())
    for other in ("0100-personal-source-guard.py", "0102-personal-egress-source-guard.py"):
        source = (PERSONAL / other).read_text()
        for relative in guard.EXPECTED:
            assert '"%s"' % relative not in source, (other, relative)


def test_default_is_off_and_no_android_permission_is_added():
    controller = (FG / "FaceGuardController.java").read_text()
    assert re.search(r'getBoolean\(KEY_ENABLED, false\)', controller)
    text = patch_text()
    assert "AndroidManifest.xml" not in text
    xml_added = "".join(re.findall(r"^\+.*swiftra_face_guard.*$", text, re.M))
    assert "swiftra_face_guard" in xml_added


def test_no_image_persistence_logging_or_network_in_face_guard_sources():
    banned = ("FileOutputStream", "FileWriter", "Bitmap.compress", "java.net", "okhttp", "HttpURLConnection",
              "android.util.Log", "Log.d(", "Log.e(", "Log.i(", "Log.w(", "MediaRecorder", "ImageWriter",
              "openFileOutput", "getExternalFilesDir", "Socket", "DownloadManager")
    log_words = ("android.util.Log", "Log.d(", "Log.e(", "Log.i(", "Log.w(")
    for path in FG.glob("*.java"):
        source = path.read_text()
        for word in banned:
            if path.name == "FaceCameraSource.java" and word in log_words:
                continue   # counters-only diagnostics, checked below
            assert word not in source, (path.name, word)
    camera = (FG / "FaceCameraSource.java").read_text()
    lines = [l for l in camera.splitlines() if "Log." in l]
    assert lines and all("TAG" in l for l in lines)
    assert all(w not in l for l in lines for w in ("getBuffer", "pixels", "plane", "gray", "image."))
    assert 'TAG = "SwiftraFaceGuard"' in camera


def test_lock_overlay_is_opaque_and_swallows_touch():
    overlay = (FG / "FaceGuardOverlay.java").read_text()
    assert "0xFF10151A" in overlay and "setOnTouchListener((v, e) -> true)" in overlay


def test_tab_switcher_is_opened_via_hub_and_thumbnails_are_blocked_while_locked():
    bridge = (FG / "FaceGuardChromeBridge.java").read_text()
    assert "showLayout(LayoutType.HUB, /* animate= */ false)" in bridge
    assert "isTabStateInitialized()" in bridge and "model.index() < 0" in bridge
    text = patch_text()
    assert len(re.findall(r"^\+.*FaceGuardLockState.isLocked\(\) \|\|", text, re.M)) == 2
    assert "FaceGuardController.onActivityResumed(this);" in text
    assert "FaceGuardController.onActivityPaused(this);" in text
    assert "FaceGuardController.onActivityDestroyed(this);" in text


def test_turning_off_needs_device_credential_when_one_exists():
    settings = (FG / "FaceGuardSettings.java").read_text()
    assert "hasDeviceCredential" in settings and "return false;" in settings
    auth = (FG / "FaceGuardAuth.java").read_text()
    assert "DEVICE_CREDENTIAL" in auth and "onFailure.run()" in auth


def test_owner_only_mode_never_uses_camera_and_cannot_lock_the_owner_out():
    src = ROOT / "tools/face_guard/src/org/chromium/chrome/browser/swiftra/faceguard"
    ctl = (src / "FaceGuardController.java").read_text()
    st = (src / "FaceGuardSettings.java").read_text()
    ov = (src / "FaceGuardOverlay.java").read_text()
    # owner-only counts only when the device has a credential (so the owner can always get back in)
    assert "getBoolean(KEY_OWNER_ONLY, false) && FaceGuardAuth.hasDeviceCredential(context)" in ctl
    # no camera and no camera permission requirement in that mode; a visible face never counts as the owner
    assert "enabled && mForeground && !mOwnerOnly && hasCameraPermission(a)" in ctl
    assert "mPolicy.setPermissionGranted(mOwnerOnly || hasCameraPermission(a))" in ctl
    assert "!mOwnerOnly && faces >= 1" in ctl
    # the owner prompt opens once per foreground session, never in a loop
    assert "!mAutoPrompted" in ctl and ctl.count("mAutoPrompted = true") == 1
    # switching it on is refused without a device credential; switching it off needs the owner check
    assert "Set a device PIN, pattern or password first." in st and "return false;   // never switch on" in st
    assert "FaceGuardAuth.authenticate(activity, () -> {\n                FaceGuardController.setOwnerOnly(activity, false);" in st
    assert "Owner only. Unlock with" in ov
