#!/usr/bin/env python3
from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
TESTS=[
    'build_smokes.py',
    'test_aot_structure.py',
    'test_combined_luax.py',
    'test_elf_audit.py',
    'test_fixeddiv_double.py',
    'test_int32.py',
    'test_manifest_verify.py',
    'test_rv32_math.py',
    'test_wad_rom.py',
    'test_zero_rfvp_patch.py',
]

def main():
    for rel in TESTS:
        print(f'=== tests/{rel} ===',flush=True)
        subprocess.run([sys.executable,str(ROOT/'tests'/rel)],cwd=ROOT,check=True)
    print('ALL CURRENT TESTS: PASS')

if __name__=='__main__':main()
