#!/usr/bin/env python3
from __future__ import annotations
import argparse, shutil, subprocess, sys, re, hashlib, json
from pathlib import Path

HERE=Path(__file__).resolve().parent.parent
# Exact non-platform object list from id Software linuxdoom-1.10/Makefile.
CORE=[
'doomdef','doomstat','dstrings','tables','f_finale','f_wipe','d_main','d_net','d_items','g_game',
'm_menu','m_misc','m_argv','m_bbox','m_fixed','m_swap','m_cheat','m_random','am_map','p_ceilng',
'p_doors','p_enemy','p_floor','p_inter','p_lights','p_map','p_maputl','p_plats','p_pspr','p_setup',
'p_sight','p_spec','p_switch','p_mobj','p_telept','p_tick','p_saveg','p_user','r_bsp','r_data','r_draw',
'r_main','r_plane','r_segs','r_sky','r_things','w_wad','wi_stuff','v_video','st_lib','st_stuff',
'hu_stuff','hu_lib','s_sound','z_zone','info','sounds'
]
PLATFORM=['i_system','i_sound','i_video','i_net','i_main']

def run(cmd,**kw):
    print('+',' '.join(str(x) for x in cmd))
    subprocess.run([str(x) for x in cmd],check=True,**kw)

def sha256_file(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_hashes(root:Path)->dict[str,str]:
    # Hash every C/header input from the supplied source tree, not only the .c
    # translation units. Headers materially affect the compiled Doom semantics.
    out={}
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix.lower() in {'.c','.h'}:
            out[path.relative_to(root).as_posix()]=sha256_file(path)
    return out

def main():
    ap=argparse.ArgumentParser(description='Compile the official linuxdoom-1.10 C sources to a freestanding RV32IM guest ELF.')
    ap.add_argument('source',type=Path,help='path to official id-Software/DOOM linuxdoom-1.10 directory')
    ap.add_argument('-o','--out',type=Path,default=HERE/'generated/doom-rv32.elf')
    ap.add_argument('--clang',default=shutil.which('clang') or '/usr/local/swift/usr/bin/clang')
    ap.add_argument('--ld',help='path to LLVM ELF linker (ld.lld); defaults to ld.lld next to clang or from PATH')
    ap.add_argument('--keep-build',action='store_true')
    ap.add_argument('--manifest',type=Path,help='write an evidence manifest with source hashes, substitutions, flags and ELF hash')
    ns=ap.parse_args()
    src=ns.source.resolve(); build=HERE/'build/official-doom-rv32'
    missing=[n for n in CORE+PLATFORM if not (src/f'{n}.c').exists()]
    if missing:
        raise SystemExit('not an official linuxdoom-1.10 source tree; missing: '+', '.join(missing))
    original_tree_hashes=source_hashes(src)
    original_hashes={name+'.c':original_tree_hashes[name+'.c'] for name in CORE}
    original_platform_hashes={name+'.c':original_tree_hashes[name+'.c'] for name in PLATFORM}
    if build.exists(): shutil.rmtree(build)
    build.mkdir(parents=True)
    work=build/'src'; shutil.copytree(src,work)
    # The release contains id's integer FixedDiv2 implementation behind #if 0.
    # RV32IM deliberately has no floating-point ISA. Select that existing C
    # fallback rather than replacing Doom fixed-point arithmetic with a new
    # approximation. Keep the change mechanically auditable.
    mf=work/'m_fixed.c'; text=mf.read_text(errors='replace')
    needle='#if 0\n    long long c;\n    c = ((long long)a<<16) / ((long long)b);\n    return (fixed_t) c;\n#endif'
    if needle not in text:
        raise SystemExit('m_fixed.c does not match the official FixedDiv2 fallback expected by this port')
    text=text.replace(needle,'#if 1\n    long long c;\n    c = ((long long)a<<16) / ((long long)b);\n    return (fixed_t) c;\n#else',1)
    # The original double branch now belongs to the #else; close it at function end.
    marker='    return (fixed_t) c;\n}'
    pos=text.find(marker,text.find('#else'))
    if pos<0: raise SystemExit('cannot close FixedDiv2 #else')
    text=text[:pos]+ '    return (fixed_t) c;\n#endif\n}' + text[pos+len(marker):]
    mf.write_text(text)
    transformed_core_hashes={name+'.c':sha256_file(work/(name+'.c')) for name in CORE}

    cc=Path(ns.clang)
    if ns.ld:
        ld=Path(ns.ld)
    else:
        sibling_lld=cc.resolve().parent/'ld.lld'
        path_lld=shutil.which('ld.lld')
        if sibling_lld.is_file():
            ld=sibling_lld
        elif path_lld:
            ld=Path(path_lld)
        else:
            raise SystemExit(
                'LLVM ELF linker ld.lld not found. Install LLVM with LLD or pass --ld /path/to/ld.lld. '
                'On Homebrew LLVM this is normally /opt/homebrew/opt/llvm/bin/ld.lld.'
            )
    if not ld.is_file():
        raise SystemExit(f'ld.lld not found: {ld}')

    common=[str(cc),'--target=riscv32-none-elf','-march=rv32im','-mabi=ilp32','-std=gnu89',
            '-DNORMALUNIX','-DLINUX','-fsigned-char','-ffreestanding','-fno-builtin','-fno-stack-protector',
            '-fno-pic','-mno-relax','-msmall-data-limit=0','-fno-jump-tables','-fno-optimize-sibling-calls','-ffunction-sections','-fdata-sections','-O2',
            '-I'+str(HERE/'guest/include'),'-I'+str(HERE/'guest/platform'),'-I'+str(work)]
    objs=[]
    for name in CORE:
        obj=build/(name+'.o'); run(common+['-c',str(work/(name+'.c')),'-o',str(obj)]); objs.append(obj)
    for name in PLATFORM:
        obj=build/(name+'.o'); run(common+['-c',str(HERE/'guest/platform'/(name+'.c')),'-o',str(obj)]); objs.append(obj)
    for rel in ['guest/libc/hcb_libc.c','guest/libc/rv32_runtime.S']:
        obj=build/(Path(rel).stem+'.o'); run(common+['-c',str(HERE/rel),'-o',str(obj)]); objs.append(obj)
    ns.out.parent.mkdir(parents=True,exist_ok=True)
    link_flags=['--gc-sections','--no-relax','-T',str(HERE/'guest/doom_rv32.ld')]
    run([str(ld)]+link_flags+[str(x) for x in objs]+['-o',str(ns.out)])
    # Link must be self-contained. llvm-nm is optional, but if present reject
    # undefined compiler-runtime or libc symbols before generating HCB.
    nm=shutil.which('llvm-nm')
    if nm:
        p=subprocess.run([nm,'-u',str(ns.out)],text=True,capture_output=True,check=True)
        unresolved=[x.strip() for x in p.stdout.splitlines() if x.strip()]
        if unresolved: raise SystemExit('unresolved RV32 guest symbols:\n'+'\n'.join(unresolved))
    if ns.manifest:
        ns.manifest.parent.mkdir(parents=True,exist_ok=True)
        git_commit=None
        if (src.parent/'.git').exists() or (src/'.git').exists():
            try:
                git_commit=subprocess.run(['git','-C',str(src),'rev-parse','HEAD'],text=True,capture_output=True,check=True).stdout.strip()
            except (OSError,subprocess.CalledProcessError):
                git_commit=None
        support_hashes={rel:sha256_file(HERE/rel) for rel in ['guest/libc/hcb_libc.c','guest/libc/rv32_runtime.S']}
        platform_replacement_hashes={name+'.c':sha256_file(HERE/'guest/platform'/(name+'.c')) for name in PLATFORM}
        manifest={
            'format':2,
            'source_directory':str(src),
            'source_git_commit':git_commit,
            'core_policy':'CORE .c files are copied from the supplied linuxdoom-1.10 tree; only m_fixed.c receives the documented FixedDiv2 branch selection before compilation.',
            'original_source_c_h_sha256':original_tree_hashes,
            'original_core_sha256':original_hashes,
            'original_platform_sha256':original_platform_hashes,
            'compiled_core_sha256':transformed_core_hashes,
            'core_modules':CORE,
            'platform_replacements':[name+'.c' for name in PLATFORM],
            'platform_replacement_sha256':platform_replacement_hashes,
            'support_sources':['guest/libc/hcb_libc.c','guest/libc/rv32_runtime.S'],
            'support_source_sha256':support_hashes,
            'source_transformations':[{
                'file':'m_fixed.c',
                "purpose":"select id Software's existing integer FixedDiv2 implementation for an RV32IM target without floating-point ISA",
                'mechanical_match_count':1,
            }],
            'compiler':str(cc),
            'compile_flags':common[1:],
            'linker':str(ld),
            'link_flags':link_flags,
            'elf':str(ns.out),
            'elf_sha256':sha256_file(ns.out),
        }
        ns.manifest.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(f'MANIFEST: {ns.manifest}')
    print(f'OK: {ns.out}')
    if not ns.keep_build: shutil.rmtree(build)

if __name__=='__main__': main()
