#!/usr/bin/env python3
from __future__ import annotations
import random
MAX=0x7fffffff; MIN=-0x80000000

def sat(a,b): return MIN if ((a^b)<0) else MAX

def div_int(a,b):
    if b==0 or (abs(a)>>14)>=abs(b): return sat(a,b)
    n=a<<16
    q=abs(n)//abs(b)
    return -q if (n<0)^(b<0) else q

def div_linux_double(a,b):
    if b==0 or (abs(a)>>14)>=abs(b): return sat(a,b)
    return int((float(a)/float(b))*65536.0)

edge=[-0x7fffffff,-123456789,-65537,-65536,-1,0,1,65535,65536,65537,123456789,0x7fffffff]
for a in edge:
  for b in edge:
    if b and div_int(a,b)!=div_linux_double(a,b): raise AssertionError((a,b,div_int(a,b),div_linux_double(a,b)))
r=random.Random(0xF1ED)
for _ in range(2000000):
    a=r.randint(-0x7fffffff,0x7fffffff); b=r.randint(-0x7fffffff,0x7fffffff)
    if b and div_int(a,b)!=div_linux_double(a,b): raise AssertionError((a,b,div_int(a,b),div_linux_double(a,b)))
print('FixedDiv integer branch matches active double branch on 2,000,000 random + edge vectors: PASS')
