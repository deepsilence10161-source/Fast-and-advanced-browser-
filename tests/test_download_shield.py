"""Patch 0015 (Swiftra Download Shield): static checks, Shield DB canary, and the device E2E logic (fake adb)."""
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "shield"))
PATCH = os.path.join(ROOT, "patches", "0015-swiftra-download-shield.patch")
FILES = ["chrome/browser/download/chrome_download_manager_delegate.cc",
         "chrome/browser/safe_browsing/download_protection/download_protection_delegate_android.cc",
         "components/safe_browsing/android/remote_database_manager.cc"]


def text():
    return open(PATCH, encoding="ascii").read()          # ASCII only (fails on any non-ASCII byte)


def added():
    return "\n".join(l for l in text().splitlines() if l.startswith("+") and not l.startswith("+++"))


def test_patch_files_and_series():
    t = text()
    assert [l.split()[1] for l in t.splitlines() if l.startswith("+++ ")] == ["b/" + f for f in FILES]
    assert t.count("\n@@ ") == 8
    series = [l.strip() for l in open(os.path.join(ROOT, "patches", "series")) if l.strip() and not l.startswith("#")]
    assert "0015-swiftra-download-shield.patch" in series
    # no other patch touches these files (the order in series then does not matter for applying)
    for name in os.listdir(os.path.join(ROOT, "patches")):
        if name.startswith("0015") or not name.endswith((".patch", ".py")):
            continue
        body = open(os.path.join(ROOT, "patches", name), encoding="utf-8", errors="replace").read()
        assert not any(f in body for f in FILES), name


def test_patch_switch_points():
    a = added()
    assert "StartNextDownloadCheck" in a and "ReportSafeOnStop" in a
    assert "SB_THREAT_TYPE_URL_BINARY_MALWARE" in a         # DownloadUrlSBClient::IsDangerous accepts only this
    assert "ANDROID_SAFEBROWSING" in a                      # replaces NOTREACHED in GetNonBrowseUrlThreatSource
    assert "IsSafeBrowsingEnabled" in a                     # ShouldCheckDownloadUrl follows the SB setting
    assert "kMaliciousApkDownloadCheck" in a                # content check stays behind the upstream flag
    removed = [l for l in text().splitlines() if l.startswith("-") and not l.startswith("---")]
    assert any("NOTREACHED();" in l for l in removed)
    assert any(l.strip() == "-  return true;" for l in removed)   # the unconditional "safe" of CheckDownloadUrl
    # no server ping: the ClientDownloadRequest gate (MayCheckClientDownload) is not touched
    assert not [l for l in a.splitlines() if "MayCheckClientDownload" in l and not l[1:].lstrip().startswith("//")]


@pytest.mark.skipif(not os.path.isdir("/tmp/p15/a"), reason="pristine @155 copies not present (tmpfs)")
def test_patch_applies_to_pristine_155(tmp_path):
    shutil.copytree("/tmp/p15/a", tmp_path / "src")
    r = subprocess.run(["patch", "-p1", "--dry-run", "-i", os.path.abspath(PATCH)], cwd=tmp_path / "src",
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "fuzz" not in r.stdout.lower() and "offset" not in r.stdout.lower(), r.stdout


def test_download_canary_listed_exactly():
    import build_shield_db as B
    assert ("127.0.0.1/__swiftra_shield_canary__/download/swiftra-canary.zip", B.MALWARE) in B.CANARIES


class FakeAdb:
    """Simulates the device side of shield_e2e.download_case."""

    def __init__(self, shield, se):
        self.shield, self.se, self.files, self.dialog, self.cancelled, self.taps = shield, se, [], False, False, []

    def __call__(self, *args, timeout=None):
        if args[:2] == ("shell", "am"):
            url = args[args.index("-d") + 1]
            case = url.split("f=")[1]
            self.se.DL_HITS.append(f"/{self.se.DL_DIR}/" + ("redirect.zip" if case == "redirect" else
                                                         "swiftra-canary.zip" if case == "canary" else "clean.zip"))
            if self.shield and case != "clean":
                self.dialog, self.cancelled = True, False
            else:
                self.files.append(f"swiftra-{case}-1.zip")
            return ""
        if args[:3] == ("shell", "uiautomator", "dump"):
            return ""
        if args[:2] == ("shell", "cat"):
            if self.dialog and not self.cancelled:
                return ('<node text="File might be harmful" bounds="[0,0][10,10]"/>'
                        '<node text="Download anyway" bounds="[0,20][10,30]"/><node text="Cancel" bounds="[20,20][40,30]"/>')
            return '<node text="Swiftra download test" bounds="[0,0][10,10]"/>'
        if args[:3] == ("shell", "input", "tap"):
            self.taps.append(args[3:])
            if args[3:] == ("30", "25"):
                self.cancelled = True
            return ""
        if args[:2] == ("shell", "ls"):
            return "\n".join(self.files)
        raise AssertionError(args)


@pytest.mark.parametrize("shield", [True, False])
def test_download_case_verdicts(monkeypatch, tmp_path, shield):
    import shield_e2e as se
    fake = FakeAdb(shield, se)
    monkeypatch.setattr(se, "adb", fake)
    clock = [1000.0]

    def sleep(sec):
        clock[0] += sec
    monkeypatch.setattr(se, "time", type("T", (), {"time": staticmethod(lambda: clock[0]), "sleep": staticmethod(sleep)}))
    monkeypatch.setattr(se.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": b""})())
    got = {c: se.download_case("com.swiftra.app", c, e, str(tmp_path)) for c, e in se.DL_CASES}
    if shield:
        assert [got[c]["verdict"] for c in ("canary", "redirect", "clean")] == ["blocked_dialog"] * 2 + ["downloaded"]
        assert all(r["pass"] for r in got.values())
        assert ("30", "25") in fake.taps and ("5", "25") not in fake.taps   # Cancel, never "Download anyway"
    else:   # an APK without 0015: both dangerous downloads complete -> FAIL, the control still passes
        assert [got[c]["verdict"] for c in ("canary", "redirect", "clean")] == ["downloaded"] * 3
        assert [got[c]["pass"] for c in ("canary", "redirect", "clean")] == [False, False, True]
