#!/usr/bin/env python3
from __future__ import annotations
import random,re,tempfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import wad2luax

ASSIGN=re.compile(r'^  GT\[(\d+)\]\[(\d+)\] = (-?\d+)$')
HEAD=re.compile(r'^function doom_wad_fill_page_(\d+)\(\)$')

def u32(v):return v&0xffffffff

def main():
    rng=random.Random(0xD00D)
    payload=bytearray(b'IWAD'+(0).to_bytes(4,'little')+(12).to_bytes(4,'little'))
    payload += bytes(rng.randrange(256) for _ in range(3*4096+137))
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); wad=td/'doom1.wad'; out=td/'rom.luax';wad.write_bytes(payload);wad2luax.emit(wad,out)
        pages={};cur=None
        for line in out.read_text().splitlines():
            m=HEAD.match(line)
            if m:cur=int(m.group(1));pages[cur]={};continue
            m=ASSIGN.match(line)
            if m and cur is not None:
                table,idx,val=map(int,m.groups());pages[cur][idx]=(table,u32(val))
        expected_pages=(len(payload)+4095)//4096
        assert len(pages)==expected_pages,(len(pages),expected_pages)
        for off in range(0,len(payload),4):
            page=off//4096; idx=(off%4096)//4
            table,val=pages[page][idx]
            assert table==852+(page%4)
            raw=payload[off:off+4]+b'\0'*max(0,4-len(payload[off:off+4]))
            assert val==int.from_bytes(raw[:4],'little'),(off,val,raw)
    print('WAD ROM reconstruction: PASS')
if __name__=='__main__':main()
