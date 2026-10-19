"""tools/security/apk_audit.py decisions with a fake APK object (the real APK run is in CI / evidence)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "security"))

import apk_audit as aa  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

NS = "http://schemas.android.com/apk/res/android"
CERT = open(os.path.join(ROOT, "patches", "signing_cert_sha256.txt")).read()
WANT = [l for l in CERT.split() if len(l) == 64][0]


class FakeApk:
    def __init__(self, app_attrs, extra_export=False, cert=None, v3=True):
        self.m = ET.fromstring(f'<manifest xmlns:android="{NS}"><application {app_attrs}/></manifest>')
        base = [l.strip() for l in open(aa.BASELINE) if l.strip() and not l.startswith("#")]
        app = self.m.find("application")
        for entry in base + (["receiver com.swiftra.Evil"] if extra_export else []):
            tag, name = entry.split(" ", 1)
            ET.SubElement(app, tag, {f"{{{NS}}}name": name, f"{{{NS}}}exported": "true"})
        self.cert, self.v3 = cert, v3

    def get_android_manifest_xml(self): return self.m
    def get_package(self): return "com.swiftra.app"
    def get_target_sdk_version(self): return "37"
    def is_signed_v2(self): return True
    def is_signed_v3(self): return self.v3
    def get_certificates_der_v3(self): return [self.cert or b"x"]
    def get_certificates_der_v2(self): return []


def run(monkeypatch, tmp_path, fake, imgs=()):
    apk = tmp_path / "a.apk"
    apk.write_bytes(b"PK")
    monkeypatch.setattr(aa, "load_apk", lambda p: fake)
    monkeypatch.setattr(aa, "brand_images", lambda a, p: (list(imgs), 10))
    monkeypatch.setattr(aa.hashlib, "sha256", _sha(fake))
    return aa.audit(str(apk))[0]


def _sha(fake):
    import hashlib as h
    real = h.sha256

    class S:
        def __init__(self, d=b""): self.d = d
        def hexdigest(self): return WANT if self.d == b"GOOD" else real(self.d).hexdigest()
    return S


def test_good_apk_passes(monkeypatch, tmp_path):
    c = run(monkeypatch, tmp_path, FakeApk('android:allowBackup="false"'.replace("android:", f"{{{NS}}}") if False else
                                           f'xmlns:a="{NS}" a:allowBackup="false"', cert=b"GOOD"))
    assert all(c.values()), c


def test_each_problem_fails(monkeypatch, tmp_path):
    ok = f'xmlns:a="{NS}" a:allowBackup="false"'
    assert not run(monkeypatch, tmp_path, FakeApk(f'xmlns:a="{NS}" a:allowBackup="false" a:debuggable="true"',
                                                  cert=b"GOOD"))["not_debuggable"]
    assert not run(monkeypatch, tmp_path, FakeApk(f'xmlns:a="{NS}" a:allowBackup="true"', cert=b"GOOD"))[
        "allow_backup_false"]
    assert not run(monkeypatch, tmp_path, FakeApk(ok, cert=b"OTHER"))["signer_cert_expected"]
    assert not run(monkeypatch, tmp_path, FakeApk(ok, cert=b"GOOD", v3=False))["signed_v2_v3"]
    assert not run(monkeypatch, tmp_path, FakeApk(ok, cert=b"GOOD", extra_export=True))["no_new_exported_entry_points"]
    assert not run(monkeypatch, tmp_path, FakeApk(ok, cert=b"GOOD"), imgs=["drawable/google_logo"])[
        "no_google_chrome_logo_images"]
