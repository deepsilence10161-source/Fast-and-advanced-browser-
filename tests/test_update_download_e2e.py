"""Host controls only; native tap/download is not proven by these fixtures."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/ci'))
import update_download_e2e as d

URL='https://github.com/deepsilence10161-source/Fast-and-advanced-browser-/releases/latest/download/Swiftra-arm64.apk'


def manifest(url=URL,sha='a'*64):
    return json.dumps({'apks':{'arm64':{'url':url,'sha256':sha}}}).encode()


def test_payload_is_existing_owned_https_apk_only():
    assert d.expected_payload(manifest(),'arm64')=={'basename':'Swiftra-arm64.apk','sha256':'a'*64}
    for url in [URL.replace('https:','http:'),URL.replace('github.com','example.org'),
                URL.replace('/deepsilence10161-source/','/other-owner/'),URL+'?token=not-allowed',
                URL.replace('Swiftra-arm64.apk','other.apk'),URL.replace('/latest/','/../')]:
        with pytest.raises(RuntimeError):d.expected_payload(manifest(url),'arm64')
    with pytest.raises(RuntimeError):d.expected_payload(manifest(sha='bad'),'arm64')


def good_result():
    return {'flags_restored':True,'cases':{'bad':{'fetched':True,'item':False,'badge':False},
            'good':{'fetched':True,'item':True,'badge':True,'tap_download':
                    {'tapped':True,'completed':True,'sha_matches':True}}}}


def test_menu_badge_alone_can_never_pass_download_acceptance():
    r=good_result();assert d.verdict(r)=='pass'
    for field in ['tapped','completed','sha_matches']:
        x=copy.deepcopy(r);x['cases']['good']['tap_download'][field]=False;assert d.verdict(x)=='fail'
    x=copy.deepcopy(r);x['cases']['good'].pop('tap_download');assert d.verdict(x)=='fail'
    x=copy.deepcopy(r);x['cases']['bad']['item']=True;assert d.verdict(x)=='fail'
    x=copy.deepcopy(r);x['flags_restored']=False;assert d.verdict(x)=='fail'
    x=copy.deepcopy(r);x['cases']['good']['fetched']=False;assert d.verdict(x)=='not_run'


def test_tap_identifies_exact_native_item_and_visible_bounds():
    raw='<hierarchy><node text="Update Swiftra" bounds="[100,200][500,250]" /></hierarchy>'
    assert d.item_node(raw)=={'cx':300,'cy':225}
    assert d.item_node(raw.replace('[100,200][500,250]','[0,0][0,0]')) is None
    assert d.item_node(raw.replace('Update Swiftra','Unrelated')) is None
    assert d.item_node('<broken') is None


def test_only_allowlisted_download_files_are_enumerated(monkeypatch):
    text='/sdcard/Download/Swiftra-arm64.apk\n/sdcard/Download/Swiftra-arm64 (1).apk.crdownload\n/sdcard/Download/private-file.txt\n/sdcard/Download/Swiftra-x64.apk\n'
    monkeypatch.setattr(d,'checked_adb',lambda *a,**kw:text.encode())
    got=d.candidates('Swiftra-arm64.apk')
    assert len(got)==2 and all('arm64' in p for p in got)
    assert 'private-file' not in json.dumps(got)


def test_download_operation_does_not_offer_install_or_capture_after_tap():
    source=Path(d.__file__).read_text()
    section=source.split('def tap_and_download(',1)[1].split('\ndef verdict(',1)[0]
    assert 'screenshot(' not in section and 'ui_xml(' not in section
    assert "['Download anyway','Download','Keep']" in section
    assert "'Install'" not in section and "'Open'" not in section
    assert 'sha_matches=True' in section
