#!/usr/bin/env python3
"""CI-only native menu tap -> download of the existing signed public project APK.

Never installs the downloaded payload. No screenshot/XML is saved after navigation to the release URL;
only allowlisted file metadata and SHA are persisted. Before-tap captures are the native menu over blank/NTP.
Menu visibility alone is NOT this test's pass criterion.
"""
import argparse
import hashlib
import http.server
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_e2e as u
from safety_update_e2e import checked_adb, prepare_browser, root_device, stop_browser
from startup_ablation import snapshot_flags, restore_flags
from startup_netlog import resolve_launcher
from shield_e2e import ui_nodes, tap


def expected_payload(manifest, abi):
    data=json.loads(manifest)
    item=data['apks'][abi]
    url=item['url'];parts=urllib.parse.urlsplit(url)
    prefix='/deepsilence10161-source/Fast-and-advanced-browser-/releases/'
    name='Swiftra-'+abi+'.apk'
    if (parts.scheme!='https' or parts.netloc!='github.com' or not parts.path.startswith(prefix)
            or not parts.path.endswith('/'+name) or parts.query or parts.fragment or '..' in parts.path
            or not re.fullmatch('[a-f0-9]{64}',item['sha256'])):
        raise RuntimeError('fixture payload is not an allowlisted project APK')
    return {'basename':name,'sha256':item['sha256']}


def item_node(xml):
    try:root=ET.fromstring(xml)
    except ET.ParseError:return None
    for n in root.iter('node'):
        if n.get('text','').strip().lower()!=u.ITEM_TEXT:continue
        m=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.get('bounds',''))
        if m:
            x1,y1,x2,y2=map(int,m.groups())
            if x2>x1 and y2>y1:return {'cx':(x1+x2)//2,'cy':(y1+y2)//2}
    return None


def candidates(basename):
    # Never enumerate/report unrelated downloads. This is a disposable CI profile, no account.
    text=checked_adb('shell','-T','if test -d /sdcard/Download; then find /sdcard/Download -maxdepth 1 -type f; fi').decode('utf-8','replace')
    pattern=re.compile(re.escape(basename[:-4])+r'(?: \(\d+\))?\.apk(?:\.crdownload)?$')
    return [line.strip() for line in text.splitlines() if pattern.fullmatch(Path(line.strip()).name)]


def hash_file(path):
    value=checked_adb('shell','sha256sum',path,timeout=120).decode().split()[0]
    return value if re.fullmatch('[a-f0-9]{64}',value) else None


def tap_and_download(menu_xml,payload):
    node=item_node(menu_xml)
    if not node:return {'tapped':False,'reason':'native update item not identifiable'}
    try:before=set(candidates(payload['basename']))
    except RuntimeError:before=set()
    tap(node)
    out={'tapped':True,'expected_basename':payload['basename'],'expected_sha256':payload['sha256'],
         'completed':False,'sha_matches':False,'consent_buttons':[],'post_tap_captures_saved':False}
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        # UI automation in memory only. Never tap Open/Install or persist a post-navigation screen.
        ns,_=ui_nodes()
        for title in ['Download anyway','Download','Keep']:
            hit=[n for n in ns if n.get('text')==title and n.get('h',0)>0]
            if hit:
                tap(hit[-1]);out['consent_buttons'].append(title);break
        for path in candidates(payload['basename']):
            if path in before or path.endswith('.crdownload'):continue
            size=int(checked_adb('shell','stat','-c','%s',path).strip())
            if size<=0:continue
            digest=hash_file(path)
            if digest==payload['sha256']:
                out.update(completed=True,sha_matches=True,bytes=size,observed_basename=Path(path).name)
                # Public test payload only; never leave ~400MB in the test device or repo artifacts.
                checked_adb('shell','rm','-f',path)
                checked_adb('shell','rm','-f','/sdcard/sb.xml')
                return out
        time.sleep(3)
    out['reason']='no newly completed matching APK after native tap (intent/consent/network not inferred)'
    checked_adb('shell','rm','-f','/sdcard/sb.xml')
    return out


def verdict(res):
    c=res.get('cases',{});bad=c.get('bad',{});good=c.get('good',{});download=good.get('tap_download')or{}
    if res.get('setup_error') or not (bad.get('fetched') and good.get('fetched')):return 'not_run'
    return ('pass' if not res.get('error') and res.get('flags_restored') and not bad.get('item') and not bad.get('badge')
            and good.get('item') and good.get('badge') and download.get('tapped') and download.get('completed')
            and download.get('sha_matches') else 'fail')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--package',required=True);ap.add_argument('--apk',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+',a.package):ap.error('invalid Android package')
    os.makedirs(a.out,exist_ok=True)
    result={'package':a.package,'cases':{},'flags_restored':False,'downloaded_payload_installed':False}
    disposable=False;snapshot=None;saved=False;srv=None
    try:
        root_device();disposable=True;snapshot=snapshot_flags();saved=True
        prepare_browser(a.package,a.apk,a.out)
        checked_adb('shell','settings','put','global','adb_enabled','1')
        checked_adb('shell','am','set-debug-app','--persistent',a.package)
        abi_raw=checked_adb('shell','getprop','ro.product.cpu.abi').strip()
        abi='arm64' if abi_raw==b'arm64-v8a' else 'x64' if abi_raw==b'x86_64' else None
        if not abi:raise RuntimeError('unsupported native test ABI')
        good,sig=u.fetch(u.REL+'swiftra-update-e2e.json'),u.fetch(u.REL+'swiftra-update-e2e.json.sig')
        payload=expected_payload(good,abi);result['payload']=payload
        bad=u.tamper(good)
        if not bad:raise RuntimeError('public fixture cannot be tampered safely')
        u.FILES.clear();u.HITS.clear();u.FILES.update({'/bad.json':bad,'/bad.json.sig':sig,'/good.json':good,'/good.json.sig':sig})
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',u.PORT),u.Handler)
        threading.Thread(target=srv.serve_forever,daemon=True).start()
        checked_adb('reverse','tcp:'+str(u.PORT),'tcp:'+str(u.PORT))
        comp=resolve_launcher(a.package)
        if not comp:raise RuntimeError('no native launcher')
        result['cases']['bad']=u.run_case(a.package,comp,'bad',a.out)
        result['cases']['good']=u.run_case(a.package,comp,'good',a.out,
                                         on_good_offer=lambda xml:tap_and_download(xml,payload))
    except Exception as e:
        key='error' if result['cases'] else 'setup_error'
        result[key]=str(e) if type(e)is RuntimeError else type(e).__name__+' (private details withheld)'
    finally:
        if disposable:
            try:
                stop_browser(a.package)
                if saved:result['flags_restored']=bool(restore_flags(snapshot))
                checked_adb('reverse','--remove','tcp:'+str(u.PORT))
                checked_adb('shell','rm','-f','/sdcard/sb.xml')
            except Exception as e:result['restore_error']=type(e).__name__
        if srv:srv.shutdown();srv.server_close()
    result['verdict']=verdict(result)
    Path(a.out,'update_download_e2e.json').write_text(json.dumps(result,indent=1)+'\n')
    print('UPDATE_DOWNLOAD_E2E',{'pass':'PASS','fail':'FAIL'}.get(result['verdict'],'NOT_RUN'),
          'sha_match='+str((result['cases'].get('good',{}).get('tap_download')or{}).get('sha_matches')),
          'flags_restored='+str(result['flags_restored']),flush=True)
    return {'pass':0,'fail':1,'not_run':2}[result['verdict']]


if __name__=='__main__':sys.exit(main())
