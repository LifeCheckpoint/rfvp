#!/usr/bin/env python3
from __future__ import annotations
import argparse,re
from pathlib import Path
HERE=Path(__file__).resolve().parent.parent
MODULES=['runtime/int32.luax','runtime/rv32core.luax','runtime/host.luax']

def max_gt(text):
    vals=[int(x) for x in re.findall(r'GT\[(\d+)\]',text)]
    return max(vals,default=0)

def max_g(text):
    vals=[int(x) for x in re.findall(r'\bg(\d+)\b',text)]
    return max(vals,default=0)

def declarations(n):
    names=[f'g{i}' for i in range(n+1)]
    lines=[]
    for i in range(0,len(names),16): lines.append('global '+', '.join(names[i:i+16]))
    return '\n'.join(lines)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--aot',type=Path,required=True); ap.add_argument('--wad-rom',type=Path,required=True); ap.add_argument('-o','--out',type=Path,required=True); ns=ap.parse_args()
    parts=[(HERE/rel).read_text() for rel in MODULES]
    parts += [ns.aot.read_text(),ns.wad_rom.read_text()]
    body='\n\n'.join(parts)
    max_global=max(max_gt(body),max_g(body),855,120)
    pre=declarations(max_global)
    main='''\nfunction main()\n  -- RFVP scripts are cooperatively scheduled.  Keep the main context alive\n  -- forever; doom_host_main_loop() owns the explicit ThreadNext cadence.\n  doom_host_main_loop()\nend\n'''
    ns.out.write_text(pre+'\n\n'+body+main,encoding='utf-8')
    print(f'globals=0..{max_global} highest_GT={max_gt(body)} highest_g={max_g(body)}')
if __name__=='__main__': main()
