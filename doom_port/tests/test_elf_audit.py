#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
from rv32_aot import decode


def enc_r(f7,rs2,rs1,f3,rd,op=0x33):
    return (f7<<25)|(rs2<<20)|(rs1<<15)|(f3<<12)|(rd<<7)|op

for f3,name in enumerate(('MUL','MULH','MULHSU','MULHU','DIV','DIVU','REM','REMU')):
    assert decode(0x1000,enc_r(1,2,1,f3,3)).op==name

for raw in (0x00000001,0x00101073):
    try:
        decode(0x1000,raw)
        raise AssertionError(f'unsupported instruction accepted: 0x{raw:08x}')
    except ValueError:
        pass
assert decode(0x1000,0x00000073).op=='ECALL'
print('ELF ISA decoder: PASS')
