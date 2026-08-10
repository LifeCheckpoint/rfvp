#!/usr/bin/env python3
from __future__ import annotations
import struct
from pathlib import Path

MASK=0xffffffff

def u32(x): return x & MASK
def i32(x):
    x &= MASK
    return x-0x100000000 if x&0x80000000 else x

def sx(v,bits):
    v &= (1<<bits)-1
    return v-(1<<bits) if v&(1<<(bits-1)) else v

def parse_elf(path):
    d=Path(path).read_bytes()
    assert d[:4]==b'\x7fELF' and d[4]==1 and d[5]==1
    entry=struct.unpack_from('<I',d,24)[0]
    phoff=struct.unpack_from('<I',d,28)[0]
    phentsz=struct.unpack_from('<H',d,42)[0]
    phnum=struct.unpack_from('<H',d,44)[0]
    mem={}
    for i in range(phnum):
        off=phoff+i*phentsz
        typ,fo,va,pa,fs,ms,fl,al=struct.unpack_from('<IIIIIIII',d,off)
        if typ!=1: continue
        for j,b in enumerate(d[fo:fo+fs]): mem[va+j]=b
    return entry,mem

class RV:
    def __init__(self,entry,mem):
        self.r=[0]*32; self.pc=entry; self.mem=dict(mem); self.r[2]=0x03f00000
        self.running=True; self.exit=None; self.steps=0; self.jalr_targets=[]
    def rb(self,a): return self.mem.get(u32(a),0)
    def wb(self,a,v): self.mem[u32(a)]=v&255
    def rw(self,a,n,sign=False):
        v=0
        for i in range(n): v|=self.rb(a+i)<<(8*i)
        return sx(v,n*8) if sign else v
    def ww(self,a,v,n):
        for i in range(n):self.wb(a+i,v>>(8*i))
    def reg(self,i): return self.r[i]
    def setr(self,i,v):
        if i:self.r[i]=u32(v)
    def step(self):
        ins=self.rw(self.pc,4); pc=self.pc; npc=u32(pc+4)
        op=ins&0x7f; rd=(ins>>7)&31; f3=(ins>>12)&7; rs1=(ins>>15)&31; rs2=(ins>>20)&31; f7=(ins>>25)&0x7f
        a=self.r[rs1]; b=self.r[rs2]
        if op==0x37:self.setr(rd,ins&0xfffff000)
        elif op==0x17:self.setr(rd,pc+(ins&0xfffff000))
        elif op==0x6f:
            imm=sx(((ins>>31)&1)<<20|((ins>>12)&0xff)<<12|((ins>>20)&1)<<11|((ins>>21)&0x3ff)<<1,21)
            self.setr(rd,pc+4);npc=u32(pc+imm)
        elif op==0x67:
            imm=sx(ins>>20,12); self.setr(rd,pc+4);npc=u32((a+imm)&~1); self.jalr_targets.append(npc)
        elif op==0x63:
            imm=sx(((ins>>31)&1)<<12|((ins>>7)&1)<<11|((ins>>25)&0x3f)<<5|((ins>>8)&0xf)<<1,13)
            take={0:a==b,1:a!=b,4:i32(a)<i32(b),5:i32(a)>=i32(b),6:a<b,7:a>=b}[f3]
            if take:npc=u32(pc+imm)
        elif op==0x03:
            imm=sx(ins>>20,12); addr=u32(a+imm)
            if f3==0:v=self.rw(addr,1,True)
            elif f3==1:v=self.rw(addr,2,True)
            elif f3==2:v=self.rw(addr,4,False)
            elif f3==4:v=self.rw(addr,1,False)
            elif f3==5:v=self.rw(addr,2,False)
            else:raise RuntimeError(('load',hex(pc),f3))
            self.setr(rd,v)
        elif op==0x23:
            imm=sx(((ins>>25)<<5)|((ins>>7)&31),12);addr=u32(a+imm)
            if f3==0:self.ww(addr,b,1)
            elif f3==1:self.ww(addr,b,2)
            elif f3==2:self.ww(addr,b,4)
            else:raise RuntimeError(('store',hex(pc),f3))
        elif op==0x13:
            imm=sx(ins>>20,12)
            if f3==0:v=a+imm
            elif f3==2:v=1 if i32(a)<imm else 0
            elif f3==3:v=1 if a<u32(imm) else 0
            elif f3==4:v=a^u32(imm)
            elif f3==6:v=a|u32(imm)
            elif f3==7:v=a&u32(imm)
            elif f3==1:v=a<<((ins>>20)&31)
            elif f3==5:
                sh=(ins>>20)&31
                v=(i32(a)>>sh) if ((ins>>30)&1) else (a>>sh)
            else:raise RuntimeError(('opimm',hex(pc),f3))
            self.setr(rd,v)
        elif op==0x33:
            if f7==0:
                if f3==0:v=a+b
                elif f3==1:v=a<<(b&31)
                elif f3==2:v=1 if i32(a)<i32(b) else 0
                elif f3==3:v=1 if a<b else 0
                elif f3==4:v=a^b
                elif f3==5:v=a>>(b&31)
                elif f3==6:v=a|b
                elif f3==7:v=a&b
            elif f7==0x20:
                if f3==0:v=a-b
                elif f3==5:v=i32(a)>>(b&31)
                else:raise RuntimeError(('op32',hex(pc),f3))
            elif f7==1:
                sa=i32(a);sb=i32(b)
                if f3==0:v=sa*sb
                elif f3==1:v=(sa*sb)>>32
                elif f3==2:v=(sa*b)>>32
                elif f3==3:v=(a*b)>>32
                elif f3==4:
                    if b==0:v=-1
                    elif sa==-2147483648 and sb==-1:v=sa
                    else:v=abs(sa)//abs(sb)*(-1 if (sa<0)^(sb<0) else 1)
                elif f3==5:v=MASK if b==0 else a//b
                elif f3==6:
                    if b==0:v=a
                    elif sa==-2147483648 and sb==-1:v=0
                    else:
                        q=abs(sa)//abs(sb)*(-1 if (sa<0)^(sb<0) else 1);v=sa-q*sb
                elif f3==7:v=a if b==0 else a%b
            else:raise RuntimeError(('op',hex(pc),f7,f3))
            self.setr(rd,v)
        elif op==0x0f:pass
        elif op==0x73:
            if f3!=0:raise RuntimeError(('system',hex(pc),f3))
            n=self.r[17]
            if n==2:self.exit=i32(self.r[10]);self.running=False
            elif n in (1,3,4,5,6): raise RuntimeError(f'host ecall {n} not supported by test emulator')
            else:raise RuntimeError(('ecall',n,hex(pc)))
        else:raise RuntimeError(('opcode',hex(pc),hex(op),hex(ins)))
        self.pc=npc;self.r[0]=0;self.steps+=1
    def run(self,limit=10_000_000):
        while self.running and self.steps<limit:self.step()
        if self.running:raise RuntimeError('step limit')
        return self.exit

def run_elf(path,limit=10_000_000):
    e,m=parse_elf(path);rv=RV(e,m);return rv.run(limit),rv

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('elf');ns=ap.parse_args()
    code,rv=run_elf(ns.elf);print(f'exit={code} steps={rv.steps}')
