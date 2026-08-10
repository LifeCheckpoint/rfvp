#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
VERIFY=ROOT/'tools/verify_source_manifest.py'

def sha(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def main():
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); src=td/'src'; src.mkdir(); (src/'sub').mkdir()
        a=b'int a(void){return 1;}\n'; h=b'#define X 7\n'; ignored=b'not an input\n'
        (src/'a.c').write_bytes(a); (src/'sub/x.h').write_bytes(h); (src/'README').write_bytes(ignored)
        man=td/'manifest.json'
        man.write_text(json.dumps({'format':2,'original_source_c_h_sha256':{'a.c':sha(a),'sub/x.h':sha(h)}}))
        subprocess.run([sys.executable,str(VERIFY),str(man),str(src)],check=True,capture_output=True,text=True)
        (src/'a.c').write_bytes(b'int a(void){return 2;}\n')
        p=subprocess.run([sys.executable,str(VERIFY),str(man),str(src)],capture_output=True,text=True)
        assert p.returncode!=0
        assert 'hash mismatch: a.c' in p.stderr
    print('source manifest verifier: PASS')

if __name__=='__main__':main()
