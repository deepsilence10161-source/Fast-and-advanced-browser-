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


@pytest.mark.parametrize("hardware", [b"ranchu", b"goldfish", b"redroid"])
def test_pref_fixture_accepts_known_disposable_android_only(monkeypatch, hardware):
    def fake(*args, **kwargs):
        return hardware + b"\n" if args == ("shell", "getprop", "ro.hardware") else b"0\n"
    monkeypatch.setattr(s, "checked_adb", fake)
    s.root_device()
