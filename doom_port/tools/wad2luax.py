#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

PAGE_BYTES=4096
WORDS_PER_PAGE=PAGE_BYTES//4
CACHE_SLOTS=4
CACHE_TABLE_BASE=852
TAG_GLOBAL_BASE=117

KIND_BY_NAME={
    'doom2f.wad':1,'doom2.wad':2,'plutonia.wad':3,'tnt.wad':4,
    'doomu.wad':5,'doom.wad':6,'doom1.wad':7,
}

def i32(v:int)->int:
    v&=0xffffffff
    return v-0x100000000 if v>=0x80000000 else v

def word_le(data:bytes,off:int)->int:
    b=data[off:off+4]
    if len(b)<4:b=b+b'\0'*(4-len(b))
    return i32(int.from_bytes(b,'little'))

def emit_page(page:int,data:bytes,lines:list[str]):
    slot=page%CACHE_SLOTS; table=CACHE_TABLE_BASE+slot
    start=page*PAGE_BYTES; chunk=data[start:start+PAGE_BYTES]
    lines.append(f'function doom_wad_fill_page_{page}()')
    # Full pages overwrite all cache entries. Last partial page only needs the
    # words that can be observed because read() clamps against g112.
    words=(len(chunk)+3)//4
    for idx in range(words):
        lines.append(f'  GT[{table}][{idx}] = {word_le(chunk,idx*4)}')
        # Filling one 4 KiB IWAD cache page means up to 1024 HCB table writes.
        # Yield periodically so synchronous Doom read() calls cannot starve the
        # cooperative RFVP scheduler for the whole page fill.
        if (idx + 1) % 256 == 0:
            lines.append('  ThreadNext()')
    lines.append(f'  g{TAG_GLOBAL_BASE+slot} = {page}')
    lines.append('  return')
    lines.append('end')
    lines.append('')

def emit_dispatch(page_count:int,lines:list[str],leaf:int=8):
    serial=[0]
    def rec(lo:int,hi:int)->str:
        name=f'doom_wad_dispatch_{serial[0]}'; serial[0]+=1
        children=None
        if hi-lo>leaf:
            mid=(lo+hi)//2
            left=rec(lo,mid); right=rec(mid,hi); children=(mid,left,right)
        body=[f'function {name}(a0)']
        if children:
            mid,left,right=children
            body += [f'  if a0 < {mid} then',f'    {left}(a0)','  else',f'    {right}(a0)','  end']
        else:
            for p in range(lo,hi):
                kw='if' if p==lo else 'elseif'
                body += [f'  {kw} a0 == {p} then',f'    doom_wad_fill_page_{p}()']
            body += ['  else','    g102 = 9301','    g101 = 0','  end']
        body += ['  return','end','']
        lines.extend(body)
        return name
    return rec(0,page_count)

def emit_runtime(root:str,size:int,kind:int,lines:list[str]):
    lines += [
'function doom_wad_init()',
f'  g112 = {size}',
f'  g116 = {kind}',
'  g117 = -1','  g118 = -1','  g119 = -1','  g120 = -1',
'  rv_store_u32(g114, g112)','  rv_store_u32(g114 + 4, g116)','  return','end','',
'function doom_wad_ensure_page(a0)','  local l0','  l0 = a0 % 4',
'  if l0 == 0 then','    if g117 == a0 then','      return','    end',
'  elseif l0 == 1 then','    if g118 == a0 then','      return','    end',
'  elseif l0 == 2 then','    if g119 == a0 then','      return','    end',
'  else','    if g120 == a0 then','      return','    end','  end',
f'  {root}(a0)','  return','end','',
'function doom_wad_word(a0)','  local l0','  local l1','  local l2',
'  l0 = a0 / 1024','  l1 = a0 % 1024','  doom_wad_ensure_page(l0)','  l2 = l0 % 4',
'  if l2 == 0 then','    return GT[852][l1]','  elseif l2 == 1 then','    return GT[853][l1]',
'  elseif l2 == 2 then','    return GT[854][l1]','  end','  return GT[855][l1]','end','',
'function doom_wad_read_u8(a0)','  local l0','  local l1','  if a0 < 0 then','    return 0','  end',
'  if a0 >= g112 then','    return 0','  end','  l0 = doom_wad_word(a0 / 4)','  l1 = a0 % 4',
'  return rv_bits(l0, l1 * 8, 8)','end','',
'function doom_wad_read_u32(a0)','  local l0','  if a0 < 0 then','    return 0','  end',
'  if a0 + 3 >= g112 then','    l0 = doom_wad_read_u8(a0)','    l0 = l0 + doom_wad_read_u8(a0 + 1) * 256',
'    l0 = l0 + doom_wad_read_u8(a0 + 2) * 65536','    l0 = l0 + doom_shl32(doom_wad_read_u8(a0 + 3), 24)','    return l0','  end',
'  if a0 % 4 == 0 then','    return doom_wad_word(a0 / 4)','  end',
'  l0 = doom_wad_read_u8(a0)','  l0 = l0 + doom_wad_read_u8(a0 + 1) * 256','  l0 = l0 + doom_wad_read_u8(a0 + 2) * 65536',
'  l0 = l0 + doom_shl32(doom_wad_read_u8(a0 + 3), 24)','  return l0','end','',
'function doom_wad_read_to_guest(a0, a1, a2)','  local l0','  local l1','  if a0 < 0 then','    return -1','  end',
'  if a1 < 0 then','    return -1','  end','  if a2 < 0 then','    return -1','  end','  if a0 >= g112 then','    return 0','  end',
'  l0 = g112 - a0','  if a2 < l0 then','    l0 = a2','  end','  l1 = 0',
'  while l1 < l0 do','    if a0 % 4 == 0 then','      if a1 % 4 == 0 then','        if l0 - l1 >= 4 then',
'          rv_store_u32(a1, doom_wad_read_u32(a0))','          a0 = a0 + 4','          a1 = a1 + 4','          l1 = l1 + 4','        else',
'          rv_store_u8(a1, doom_wad_read_u8(a0))','          a0 = a0 + 1','          a1 = a1 + 1','          l1 = l1 + 1','        end',
'      else','        rv_store_u8(a1, doom_wad_read_u8(a0))','        a0 = a0 + 1','        a1 = a1 + 1','        l1 = l1 + 1','      end',
'    else','      rv_store_u8(a1, doom_wad_read_u8(a0))','      a0 = a0 + 1','      a1 = a1 + 1','      l1 = l1 + 1','    end','  end','  return l0','end',''
    ]

def emit(wad:Path,out:Path):
    data=wad.read_bytes(); name=wad.name.lower(); kind=KIND_BY_NAME.get(name,0)
    if kind==0: raise SystemExit(f'unsupported IWAD basename {wad.name!r}; rename/use a canonical Doom IWAD basename')
    if len(data)<12 or data[:4] not in (b'IWAD',b'PWAD'):raise SystemExit('input is not a WAD file')
    page_count=(len(data)+PAGE_BYTES-1)//PAGE_BYTES
    lines=['-- generated read-only IWAD ROM; data is embedded in HCB code, RFVP VFS is not used.']
    for p in range(page_count):emit_page(p,data,lines)
    d=[];root=emit_dispatch(page_count,d);lines.extend(d);emit_runtime(root,len(data),kind,lines)
    out.write_text('\n'.join(lines),encoding='utf-8')
    print(f'IWAD={wad.name} bytes={len(data)} pages={page_count} cache_slots={CACHE_SLOTS}')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('wad',type=Path);ap.add_argument('-o','--out',type=Path,required=True);ns=ap.parse_args();emit(ns.wad,ns.out)
if __name__=='__main__':main()
