"""Hermetic API adapter checks with a NON-credential fixture and no network/token disclosure."""
from pathlib import Path
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def helper_fixture(tmp_path, curl_exit):
    vault=tmp_path/'fixture-vault';vault.mkdir(mode=0o700)
    (vault/'gh_token').write_text('NONCREDENTIAL_FIXTURE')
    redactor=tmp_path/'redact.py'
    redactor.write_text('import sys\nsys.stdout.write(sys.stdin.read().replace("NONCREDENTIAL_FIXTURE", "REDACTED"))\n')
    bindir=tmp_path/'bin';bindir.mkdir()
    curl=bindir/'curl'
    curl.write_text('#!/bin/sh\ncat >/dev/null\nprintf \'{"message":"fixture response"}\\n\'\nexit '+str(curl_exit)+'\n')
    curl.chmod(0o700)
    text=(ROOT/'tools/secret-guard/gh.sh').read_text()
    text=text.replace('V=/home/user/.secrets','V='+str(vault))
    text=text.replace('/home/user/fab/tools/secret-guard/redact.py',str(redactor))
    script=tmp_path/'fixture-gh.sh';script.write_text(text)
    return script,dict(os.environ,PATH=str(bindir)+':'+os.environ['PATH'])


def test_redaction_success_cannot_hide_http_or_transport_failure(tmp_path):
    script,env=helper_fixture(tmp_path,22)
    r=subprocess.run(['bash',str(script),'/repos/owner/repo/expected-missing'],env=env,capture_output=True)
    assert r.returncode==22
    assert b'NONCREDENTIAL_FIXTURE' not in r.stdout+r.stderr
    assert b'fixture response' in r.stdout


def test_http_success_still_works(tmp_path):
    script,env=helper_fixture(tmp_path,0)
    r=subprocess.run(['bash',str(script),'/repos/owner/repo'],env=env,capture_output=True)
    assert r.returncode==0 and b'fixture response' in r.stdout
    assert b'NONCREDENTIAL_FIXTURE' not in r.stdout+r.stderr


def test_credentials_never_sent_to_unapproved_host(tmp_path):
    script,env=helper_fixture(tmp_path,0)
    r=subprocess.run(['bash',str(script),'https://example.org/not-github'],env=env,capture_output=True)
    assert r.returncode==1 and b'fixture response' not in r.stdout
    assert b'NONCREDENTIAL_FIXTURE' not in r.stdout+r.stderr
