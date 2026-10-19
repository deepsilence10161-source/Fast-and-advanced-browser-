import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ci"))
import keystore_e2e as k  # noqa: E402


def _db(value, enc):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "Cookies")
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE cookies (name TEXT, value TEXT, encrypted_value BLOB)")
        con.execute("INSERT INTO cookies VALUES (?,?,?)", (k.NAME, value, enc))
        con.commit(); con.close()
        return {"Cookies": open(p, "rb").read()}


def test_cookie_row_reads_encrypted_blob():
    assert k.cookie_row(_db("", b"sw1" + b"\x01" * 40)) == ("", b"sw1" + b"\x01" * 40)
    assert k.cookie_row({}) is None


def _res(prefix, **kw):
    r = {"row": {"value": "", "enc_prefix": prefix}, "token_in_plaintext": False, "restart_cookie_sent": True,
         "wrapped_pref": True}
    r.update(kw)
    return r


def test_verdicts():
    assert k.verdict(_res("sw1")) == "pass"
    assert k.verdict(_res("v10")) == "fail"                              # 0021 key exists but not used
    assert k.verdict(_res("v10", wrapped_pref=False)) == "not_run"       # APK without 0021
    assert k.verdict(_res("sw1", token_in_plaintext=True)) == "fail"
    assert k.verdict(_res("sw1", restart_cookie_sent=False)) == "fail"   # unwrap after restart broken
    assert k.verdict({"row": {"value": "plain", "enc_prefix": ""}, "wrapped_pref": True}) == "fail"
    assert k.verdict({"row": {"value": "plain", "enc_prefix": ""}, "wrapped_pref": False}) == "not_run"  # old APK never blocks
    assert k.verdict({}) == "not_run"


def test_hooked_and_gated():
    rc = open(os.path.join(ROOT, "scripts", "ci", "run_capture.sh")).read()
    assert "scripts/ci/keystore_e2e.py" in rc
    g = open(os.path.join(ROOT, "scripts", "release", "e2e_gate.py")).read()
    assert '"0021-swiftra-keystore-oscrypt.patch": "KEYSTORE_E2E"' in g


def test_patch_0021_design():
    p = open(os.path.join(ROOT, "patches", "0021-swiftra-keystore-oscrypt.patch")).read()
    add = "\n".join(l for l in p.splitlines() if l.startswith("+"))
    assert "kAES256GCM" in add and '"sw1"' in add and "precedence=*/10u" in add
    assert "kTemporarilyUnavailable" in add                       # never drops data on failure
    assert "base::ThreadPool::PostTaskAndReplyWithResult" in add  # Keystore off the UI thread
    assert 'KeyStore.getInstance("AndroidKeyStore")' in add and ".setKeySize(256)" in add
    assert "if (wrapKey == null) return new byte[0];" in add      # existing wrapped key never replaced
    assert all(ord(c) < 128 for c in p)
