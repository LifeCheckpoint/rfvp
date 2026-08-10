#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tests'))
from rv32_aot import parse_elf, audit_indirect_jumps, blocks
from rv32_ref import run_elf


def check(path:Path):
    entry,code,_data,_ranges,funcs=parse_elf(path)
    audit_indirect_jumps(code)
    bb=blocks(code,entry,funcs)
    starts=set(bb)
    seen=[]
    for start,seq in bb.items():
        assert seq and seq[0].pc==start
        seen.extend(i.pc for i in seq)
    assert len(seen)==len(set(seen)), f'overlapping AOT blocks in {path.name}'
    assert set(seen)==set(code), f'AOT does not cover exactly all code in {path.name}'
    assert funcs <= starts, f'function symbol missing as block start in {path.name}'
    for pc,ins in code.items():
        if ins.op in {'BEQ','BNE','BLT','BGE','BLTU','BGEU','JAL'}:
            target=(pc+ins.imm)&0xffffffff
            assert target in starts, f'direct target 0x{target:08x} is not block start in {path.name}'
    exit_code,rv=run_elf(path)
    assert exit_code==0, f'{path.name} exits {exit_code}'
    bad=[x for x in rv.jalr_targets if x not in starts]
    assert not bad, f'JALR targets not represented by AOT blocks in {path.name}: {bad[:8]}'
    print(f'{path.name}: AOT structure PASS; insns={len(code)} blocks={len(bb)} funcs={len(funcs)} jalr_targets={len(rv.jalr_targets)}')


def main():
    for name in ('rv32_smoke.elf','rv32_div64_smoke.elf','rv32_fnptr_smoke.elf'):
        check(ROOT/'generated'/name)

if __name__=='__main__': main()
