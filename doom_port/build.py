#!/usr/bin/env python3
from __future__ import annotations
import argparse, shutil, subprocess, sys, hashlib, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
TOOLS=HERE/'tools'
GENERATED=HERE/'generated'

def run(cmd,*,cwd=None):
    print('+',' '.join(str(x) for x in cmd));subprocess.run([str(x) for x in cmd],cwd=cwd,check=True)

def main():
    ap=argparse.ArgumentParser(description='Build official linuxdoom-1.10 into a zero-RFVP-patch HCB program. The IWAD is embedded in HCB code at build time.')
    ap.add_argument('source',type=Path,help='official id-Software/DOOM/linuxdoom-1.10 source directory')
    ap.add_argument('iwad',type=Path,nargs='?',help='legally obtained canonical IWAD (required unless --elf-only is used)')
    ap.add_argument('-o','--out',type=Path,default=GENERATED/'doom.hcb')
    ap.add_argument('--keep-build',action='store_true')
    mode=ap.add_mutually_exclusive_group()
    mode.add_argument('--luax-only',action='store_true',help='stop after generating and validating combined Luax')
    mode.add_argument('--elf-only',action='store_true',help='stop after compiling and auditing the complete RV32IM Doom ELF; IWAD is not required')
    ns=ap.parse_args()
    if ns.iwad is None and not ns.elf_only:
        ap.error('iwad is required unless --elf-only is used')
    GENERATED.mkdir(parents=True,exist_ok=True)
    elf=GENERATED/'doom-rv32.elf';aot=GENERATED/'doom-rv32-aot.luax';wadrom=GENERATED/'doom-iwad-rom.luax';combined=GENERATED/'doom-zero-combined.luax';manifest=GENERATED/'doom-build-manifest.json';source_manifest=GENERATED/'doom-source-manifest.json'
    build=[sys.executable,TOOLS/'build_official_doom.py',ns.source,'-o',elf,'--manifest',source_manifest]
    if ns.keep_build:build.append('--keep-build')
    run(build)
    run([sys.executable,TOOLS/'audit_elf.py',elf])
    if ns.elf_only:
        print(f'OK: compiled and audited RV32IM Doom ELF: {elf}')
        print(f'SOURCE MANIFEST: {source_manifest}')
        return
    run([sys.executable,TOOLS/'rv32_aot.py',elf,'-o',aot])
    run([sys.executable,TOOLS/'wad2luax.py',ns.iwad,'-o',wadrom])
    run([sys.executable,TOOLS/'make_combined.py','--aot',aot,'--wad-rom',wadrom,'-o',combined])
    run([sys.executable,TOOLS/'validate_luax.py',combined,'--meta',HERE/'doom.yaml'])
    artifacts={
        'format':1,
        'rfvp_source_changes_required':False,
        'source_manifest':str(source_manifest),
        'iwad':str(ns.iwad.resolve()),
        'iwad_sha256':hashlib.sha256(ns.iwad.read_bytes()).hexdigest(),
        'artifacts':{},
    }
    for label,path in [('elf',elf),('aot_luax',aot),('wad_rom_luax',wadrom),('combined_luax',combined),('meta',HERE/'doom.yaml')]:
        artifacts['artifacts'][label]={'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest.write_text(json.dumps(artifacts,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'MANIFEST: {manifest}')
    if ns.luax_only:
        print(f'OK: validated zero-patch Luax: {combined}');return
    cargo=shutil.which('cargo')
    if not cargo:raise SystemExit(f'validated Luax generated, but Cargo is unavailable; output retained at {combined}')
    ns.out.parent.mkdir(parents=True,exist_ok=True)
    run([cargo,'run','--release','-p','lua2hcb_compiler','--','--meta',HERE/'doom.yaml','--lua',combined,'--out',ns.out],cwd=ROOT)
    print(f'OK: HCB: {ns.out}')
if __name__=='__main__':main()
