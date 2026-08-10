#!/usr/bin/env python3
from __future__ import annotations
import random
MASK=0xffffffff

def s32(x):
    x &= MASK
    return x-0x100000000 if x&0x80000000 else x

def u32(x): return x&MASK

def rv_mulhu_model(a,b):
    aa=[(u32(a)>>(8*i))&255 for i in range(4)]
    bb=[(u32(b)>>(8*i))&255 for i in range(4)]
    carry=aa[0]*bb[0]//256
    t=aa[0]*bb[1]+aa[1]*bb[0]+carry; carry=t//256
    t=aa[0]*bb[2]+aa[1]*bb[1]+aa[2]*bb[0]+carry; carry=t//256
    t=aa[0]*bb[3]+aa[1]*bb[2]+aa[2]*bb[1]+aa[3]*bb[0]+carry; carry=t//256
    t=aa[1]*bb[3]+aa[2]*bb[2]+aa[3]*bb[1]+carry; b4=t%256; carry=t//256
    t=aa[2]*bb[3]+aa[3]*bb[2]+carry; b5=t%256; carry=t//256
    t=aa[3]*bb[3]+carry; b6=t%256; b7=(t//256)%256
    return s32(b4|(b5<<8)|(b6<<16)|(b7<<24))

def rv_mulh_model(a,b):
    x=rv_mulhu_model(a,b)
    if a<0:x=s32(x-b)
    if b<0:x=s32(x-a)
    return x

def rv_mulhsu_model(a,b):
    x=rv_mulhu_model(a,b)
    if a<0:x=s32(x-b)
    return x

def rv_divu_model(a,b):
    if u32(b)==0:return -1
    rem=quot=0
    for bit in range(31,-1,-1):
        rem=((rem<<1)|((u32(a)>>bit)&1))&MASK
        if rem>=u32(b):
            rem=(rem-u32(b))&MASK
            quot|=1<<bit
    return s32(quot)

def rv_remu_model(a,b):
    if u32(b)==0:return s32(a)
    rem=0
    for bit in range(31,-1,-1):
        rem=((rem<<1)|((u32(a)>>bit)&1))&MASK
        if rem>=u32(b): rem=(rem-u32(b))&MASK
    return s32(rem)

EDGE=[0,1,-1,2,-2,0x7fffffff,-0x80000000,0x12345678,s32(0x89abcdef)]
for a in EDGE:
  for b in EDGE:
    ref=s32((u32(a)*u32(b))>>32)
    assert rv_mulhu_model(a,b)==ref,(a,b,'mulhu',rv_mulhu_model(a,b),ref)
    ref=s32(((a*b)&((1<<64)-1))>>32)
    assert rv_mulh_model(a,b)==ref,(a,b,'mulh',rv_mulh_model(a,b),ref)
    # signed * unsigned interpreted as 64-bit two's-complement product
    ref=s32(((a*u32(b))&((1<<64)-1))>>32)
    assert rv_mulhsu_model(a,b)==ref,(a,b,'mulhsu',rv_mulhsu_model(a,b),ref)
    if u32(b):
      assert rv_divu_model(a,b)==s32(u32(a)//u32(b))
      assert rv_remu_model(a,b)==s32(u32(a)%u32(b))

r=random.Random(0xD00D)
for _ in range(200000):
    a=s32(r.getrandbits(32)); b=s32(r.getrandbits(32))
    assert rv_mulhu_model(a,b)==s32((u32(a)*u32(b))>>32)
    assert rv_mulh_model(a,b)==s32(((a*b)&((1<<64)-1))>>32)
    assert rv_mulhsu_model(a,b)==s32(((a*u32(b))&((1<<64)-1))>>32)
    if u32(b):
        assert rv_divu_model(a,b)==s32(u32(a)//u32(b))
        assert rv_remu_model(a,b)==s32(u32(a)%u32(b))
print('RV32M high-multiply/unsigned-div tests: PASS')
