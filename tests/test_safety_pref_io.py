"""Desktop functional checks of CI-only private-pref atomic IO; not Android E2E."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "ci"))
import safety_update_e2e as s

ORIGINAL = b'<map><string name="unrelated">keep-me</string><string name="swiftra_oscrypt_wrapped_v1">wrapped-fixture</string></map>'
NEW = b'<map><string name="unrelated">keep-me</string><string name="swiftra_oscrypt_wrapped_v1">wrapped-fixture</string><long name="swiftra_update_last_ok_ms" value="1" /></map>'


def local_transport(monkeypatch, drop=False, bad_metadata=False):
    calls = []

    def fake(*args, raw_input=None, timeout=45):
        calls.append(args)
        assert "wrapped-fixture" not in " ".join(args)  # private data only in stdin, never argv
        if args[:2] == ("exec-out", "cat"):
            return Path(args[2]).read_bytes()
        if args[:2] == ("shell", "-T"):
            p = subprocess.run(["bash", "-c", args[2]], input=b"" if drop else raw_input,
                               capture_output=True, timeout=timeout)
        elif args[:3] == ("shell", "ls", "-Zd"):
            return b"? " + args[3].encode() + b"\n"  # host filesystem has no Android SELinux labels
        elif args[:2] == ("shell", "stat"):
            if bad_metadata and args[-1].endswith(".swiftra_e2e.tmp"):
                return b"different-owner-mode\n"
            p = subprocess.run(args[1:], capture_output=True, timeout=timeout)
        elif args[0] == "shell" and args[1] in ("mv", "rm"):
            p = subprocess.run(args[1:], capture_output=True, timeout=timeout)
        else:
            raise AssertionError("unexpected fake transport operation")
        if p.returncode:
            raise RuntimeError("fake transport command failed")
        return p.stdout

    monkeypatch.setattr(s, "checked_adb", fake)
    return calls


def test_atomic_stdin_write_verifies_bytes_metadata_and_renames(tmp_path, monkeypatch):
    p = tmp_path / "prefs.xml"
    p.write_bytes(ORIGINAL)
    p.chmod(0o600)
    before = p.stat()
    calls = local_transport(monkeypatch)
    s.write_prefs(str(p), NEW)
    assert p.read_bytes() == NEW
    assert (p.stat().st_uid, p.stat().st_gid, p.stat().st_mode) == (before.st_uid, before.st_gid, before.st_mode)
    assert not Path(str(p) + ".swiftra_e2e.tmp").exists()
    assert any(c[:2] == ("shell", "-T") for c in calls)
    assert not any(c[0] == "exec-in" for c in calls)
    assert next(i for i, c in enumerate(calls) if c[:2] == ("exec-out", "cat")) < next(
        i for i, c in enumerate(calls) if c[:2] == ("shell", "mv"))


@pytest.mark.parametrize("drop,bad_metadata", [(True, False), (False, True)])
def test_bad_write_or_metadata_leaves_original_intact(tmp_path, monkeypatch, drop, bad_metadata):
    p = tmp_path / "prefs.xml"
    p.write_bytes(ORIGINAL)
    p.chmod(0o600)
    calls = local_transport(monkeypatch, drop=drop, bad_metadata=bad_metadata)
    with pytest.raises(RuntimeError):
        s.write_prefs(str(p), NEW)
    assert p.read_bytes() == ORIGINAL
    assert not Path(str(p) + ".swiftra_e2e.tmp").exists()
    assert not any(c[:2] == ("shell", "mv") for c in calls)


def test_private_pref_fixture_refuses_physical_device_before_adb_root(monkeypatch):
    calls = []
    def fake(*args, **kwargs):
        calls.append(args)
        return b"physical-phone-hardware\n"
    monkeypatch.setattr(s, "checked_adb", fake)
    with pytest.raises(RuntimeError, match="physical or unknown"):
        s.root_device()
    assert calls == [("shell", "getprop", "ro.hardware")]


def test_main_physical_refusal_has_no_cleanup_mutations(tmp_path, monkeypatch):
    mutations = []
    monkeypatch.setattr(sys, "argv", ["safety_update_e2e.py", "--package", "com.swiftra.app",
                                    "--out", str(tmp_path), "--apk", "must-not-install.apk"])
    monkeypatch.setattr(s, "checked_adb", lambda *a, **kw: b"physical-phone-hardware\n")
    monkeypatch.setattr(s, "adb", lambda *a, **kw: mutations.append(a))
    monkeypatch.setattr(s, "prepare_browser", lambda *a: pytest.fail("must not install on refused device"))
    assert s.main() == 2
    assert mutations == []  # no force-stop, flags removal or reverse removal in finally either


@pytest.mark.parametrize("hardware", [b"ranchu", b"goldfish", b"redroid"])
def test_pref_fixture_accepts_known_disposable_android_only(monkeypatch, hardware):
    def fake(*args, **kwargs):
        return hardware + b"\n" if args == ("shell", "getprop", "ro.hardware") else b"0\n"
    monkeypatch.setattr(s, "checked_adb", fake)
    s.root_device()


P1 = "0005-safety-hub-no-false-up-to-date.patch\n"
P2 = "0020-swiftra-update-channel.patch\n"


@pytest.mark.parametrize("patches,supported", [(None, False), ("", False), (P1, False),
                                               (P2, False), (P1 + P2, True),
                                               (P1.replace(".patch", "Xpatch") + P2, False)])
def test_wrapper_patch_awareness_is_executable_not_a_substring_check(tmp_path, patches, supported):
    wrapper = Path(__file__).resolve().parents[1] / "scripts/ci/run_capture.sh"
    body = wrapper.read_text().split("safety_update_supported() {", 1)[1].split("\n}", 1)[0]
    if patches is not None:
        (tmp_path / "BUILD_INFO.txt").write_text(patches)
    env = dict(os.environ, OUT=str(tmp_path))
    r = subprocess.run(["bash", "-c", "safety_update_supported() {" + body + "\n}\nsafety_update_supported"],
                       env=env, capture_output=True)
    assert (r.returncode == 0) is supported
