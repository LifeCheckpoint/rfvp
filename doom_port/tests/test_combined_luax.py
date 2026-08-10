#!/usr/bin/env python3
from __future__ import annotations
import subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
TOOLS=ROOT/'tools'
GEN=ROOT/'generated'

def run(*args):
    subprocess.run([str(x) for x in args],cwd=ROOT,check=True,capture_output=True,text=True)

def main():
    elf=GEN/'rv32_fnptr_smoke.elf'
    if not elf.exists():
        run(sys.executable,ROOT/'tests/build_smokes.py')
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        wad=td/'doom1.wad'; aot=td/'aot.luax'; rom=td/'rom.luax'; combined=td/'combined.luax'
        # Structurally valid-enough byte payload for the ROM layer; Doom parsing
        # is not exercised by this smoke. The ROM test independently verifies
        # byte reconstruction across pages.
        wad.write_bytes(b'IWAD'+(0).to_bytes(4,'little')+(12).to_bytes(4,'little')+bytes(range(251))*20)
        run(sys.executable,TOOLS/'rv32_aot.py',elf,'-o',aot)
        run(sys.executable,TOOLS/'wad2luax.py',wad,'-o',rom)
        run(sys.executable,TOOLS/'make_combined.py','--aot',aot,'--wad-rom',rom,'-o',combined)
        run(sys.executable,TOOLS/'validate_luax.py',combined,'--meta',ROOT/'doom.yaml')
        text=combined.read_text(encoding='utf-8')
        assert 'function main()' in text
        assert 'function rv_aot_run_slice' in text
        assert 'function doom_wad_read_to_guest' in text
        assert 'function doom_host_present' in text
    print('combined zero-patch Luax pipeline: PASS')

if __name__=='__main__':main()
