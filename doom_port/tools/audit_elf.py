#!/usr/bin/env python3
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
from rv32_aot import parse_elf, audit_indirect_jumps, blocks


def main():
    ap=argparse.ArgumentParser(description='Audit the final guest ELF against the exact RV32IM subset accepted by the zero-patch AOT translator.')
    ap.add_argument('elf',type=Path)
    ns=ap.parse_args()
    entry,code,_data,ranges,funcs=parse_elf(ns.elf)
    if not code:
        raise SystemExit('no executable instructions found')
    audit_indirect_jumps(code)
    bb=blocks(code,entry,funcs)
    covered=[ins.pc for seq in bb.values() for ins in seq]
    if len(covered)!=len(set(covered)) or set(covered)!=set(code):
        raise SystemExit('AOT block partition does not cover executable instructions exactly once')
    counts=Counter(ins.op for ins in code.values())
    print(f'RV32IM/AOT audit: PASS ({len(code)} instructions, {len(bb)} blocks, {len(funcs)} function symbols)')
    print('instruction classes: '+', '.join(f'{k}={counts[k]}' for k in sorted(counts)))
    print('allocated sections: '+', '.join(f'{name}@0x{addr:08x}+0x{size:x}' for name,addr,size,_flags,_typ in ranges))

if __name__=='__main__': main()
