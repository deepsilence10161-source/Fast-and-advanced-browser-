import os, re, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "release"))
import update_manifest as um

A, B = "a" * 64, "b" * 64

def test_new_entries_use_upload_time():
    m = um.build(f"{A}  Swiftra-arm64.apk\n{B}  Swiftra-x64.apk\n", {"arm64": 5, "x64": 7})
    assert m["v"] == 1 and m["apks"]["arm64"]["published_ms"] == 5 and m["apks"]["x64"]["sha256"] == B
    assert m["apks"]["arm64"]["url"].endswith("/releases/latest/download/Swiftra-arm64.apk")

def test_unchanged_apk_keeps_old_time():
    old = um.build(f"{A}  Swiftra-arm64.apk\n", {"arm64": 5})
    m = um.build(f"{A}  Swiftra-arm64.apk\n", {"arm64": 99}, old)
    assert m["apks"]["arm64"]["published_ms"] == 5

def test_changed_apk_gets_new_time():
    old = um.build(f"{A}  Swiftra-arm64.apk\n", {"arm64": 5})
    assert um.build(f"{B}  Swiftra-arm64.apk\n", {"arm64": 99}, old)["apks"]["arm64"]["published_ms"] == 99

def _patch():
    return open(os.path.join(ROOT, "patches", "0020-swiftra-update-channel.patch")).read()

def test_patch_pins_project_and_key():
    p = _patch()
    assert '+        static final String RELEASES =' in p
    assert "deepsilence10161-source/Fast-and-advanced-browser-/releases/" in p
    key = re.search(r'PUBLIC_KEY =\n\+\s+"([A-Za-z0-9+/=]+)"', p).group(1)
    shield = open(os.path.join(ROOT, "patches", "0006-swiftra-shield.patch")).read()
    assert key in shield                       # same embedded public key the workflow checks the signer against
    assert '"swiftra-update-v1\\n".getBytes' in p   # domain separation from shield.swz signatures
    assert "GooglePlayServicesUtil" not in "".join(l for l in p.splitlines() if l.startswith("+"))

def test_https_update_uses_own_browser_not_a_nonbrowser_only_handler():
    p = _patch()
    added = '\n'.join(l[1:] for l in p.splitlines() if l.startswith('+') and not l.startswith('+++'))
    removed = '\n'.join(l[1:] for l in p.splitlines() if l.startswith('-') and not l.startswith('---'))
    assert 'intent.setPackage(context.getPackageName());' in added
    assert 'intent.addFlags(Intent.FLAG_ACTIVITY_REQUIRE_NON_BROWSER);' in removed
    assert 'FLAG_ACTIVITY_REQUIRE_NON_BROWSER' not in added
    assert 'if (newTask) intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);' in p
    # Still the normal browser download/security path, no certificate or installer bypass.
    assert 'ignore-certificate-errors' not in added and 'ACTION_INSTALL_PACKAGE' not in added


def test_patch_ascii_and_in_series():
    assert all(ord(c) < 128 for c in _patch())
    series = open(os.path.join(ROOT, "patches", "series")).read().split()
    assert "0020-swiftra-update-channel.patch" in series


sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))


def test_update_e2e_verdict_and_tamper():
    import update_e2e as ue
    m = b'{\n "apks": {\n  "arm64": {\n   "published_ms": 4102444800000\n  }\n }\n}\n'
    t = ue.tamper(m)
    assert t != m and len(t) == len(m) and b"published_ms" in t
    ok = {"fetched": True, "item": True, "badge": True}
    no = {"fetched": True, "item": False, "badge": False}
    assert ue.verdict({"cases": {"bad": no, "good": ok}}) == "pass"
    assert ue.verdict({"cases": {"bad": ok, "good": ok}}) == "fail"          # tampered manifest accepted
    assert ue.verdict({"cases": {"bad": no, "good": dict(ok, badge=False)}}) == "fail"
    assert ue.verdict({"cases": {"bad": {"fetched": False}, "good": {"fetched": False}}}) == "not_run"
    assert ue.verdict({}) == "not_run"


def test_run_capture_runs_update_e2e():
    s = open(os.path.join(ROOT, "scripts", "ci", "run_capture.sh")).read()
    assert "scripts/ci/update_e2e.py" in s


def test_safety_check_uses_update_channel_honestly():
    p = open(os.path.join(ROOT, "patches", "0005-safety-hub-no-false-up-to-date.patch")).read()
    added = "\n".join(l for l in p.splitlines() if l.startswith("+"))
    assert "UpdateStatusProvider.swiftraCheckedRecently()" in added          # "up to date" only after a recent signed check
    assert "startIntentUpdate(mPreference.getContext()" in added             # Update button -> signed channel link
    assert "if (!BuildConfig.IS_CHROME_BRANDED) return null;\n" not in p.split("getSecondaryButtonText")[0].split("getUpdateStatus")[1]
    q = open(os.path.join(ROOT, "patches", "0020-swiftra-update-channel.patch")).read()
    assert "public static boolean swiftraCheckedRecently()" in q and ".putLong(PREF_LAST_OK, now)" in q
