#!/usr/bin/env python3
from __future__ import annotations
import argparse, struct
from dataclasses import dataclass
from pathlib import Path

PT_LOAD=1
PF_X=1
EM_RISCV=243
SHT_PROGBITS=1
SHT_SYMTAB=2
SHT_NOBITS=8
SHF_ALLOC=0x2
SHF_EXECINSTR=0x4
STT_FUNC=2

@dataclass(frozen=True)
class Insn:
    pc:int; raw:int; op:str; rd:int=0; rs1:int=0; rs2:int=0; imm:int=0


def sx(v,b):
    m=1<<(b-1); return (v^m)-m

def decode(pc:int, x:int)->Insn:
    if x & 3 != 3: raise ValueError(f'compressed/non-32-bit instruction at 0x{pc:08x}')
    op=x&0x7f; rd=(x>>7)&31; f3=(x>>12)&7; rs1=(x>>15)&31; rs2=(x>>20)&31; f7=(x>>25)&0x7f
    if op==0x37: return Insn(pc,x,'LUI',rd,imm=sx(x&0xfffff000,32))
    if op==0x17: return Insn(pc,x,'AUIPC',rd,imm=sx(x&0xfffff000,32))
    if op==0x6f:
        imm=((x>>21)&0x3ff)<<1 | ((x>>20)&1)<<11 | ((x>>12)&0xff)<<12 | ((x>>31)&1)<<20
        return Insn(pc,x,'JAL',rd,imm=sx(imm,21))
    if op==0x67 and f3==0: return Insn(pc,x,'JALR',rd,rs1,imm=sx(x>>20,12))
    if op==0x63 and f3 in (0,1,4,5,6,7):
        names={0:'BEQ',1:'BNE',4:'BLT',5:'BGE',6:'BLTU',7:'BGEU'}
        imm=((x>>8)&0xf)<<1 | ((x>>25)&0x3f)<<5 | ((x>>7)&1)<<11 | ((x>>31)&1)<<12
        return Insn(pc,x,names[f3],rs1=rs1,rs2=rs2,imm=sx(imm,13))
    if op==0x03 and f3 in (0,1,2,4,5):
        return Insn(pc,x,{0:'LB',1:'LH',2:'LW',4:'LBU',5:'LHU'}[f3],rd,rs1,imm=sx(x>>20,12))
    if op==0x23 and f3 in (0,1,2):
        imm=((x>>7)&31)|((x>>25)&0x7f)<<5
        return Insn(pc,x,{0:'SB',1:'SH',2:'SW'}[f3],rs1=rs1,rs2=rs2,imm=sx(imm,12))
    if op==0x13:
        if f3==0:return Insn(pc,x,'ADDI',rd,rs1,imm=sx(x>>20,12))
        if f3==2:return Insn(pc,x,'SLTI',rd,rs1,imm=sx(x>>20,12))
        if f3==3:return Insn(pc,x,'SLTIU',rd,rs1,imm=sx(x>>20,12))
        if f3==4:return Insn(pc,x,'XORI',rd,rs1,imm=sx(x>>20,12))
        if f3==6:return Insn(pc,x,'ORI',rd,rs1,imm=sx(x>>20,12))
        if f3==7:return Insn(pc,x,'ANDI',rd,rs1,imm=sx(x>>20,12))
        sh=(x>>20)&31
        if f3==1 and f7==0:return Insn(pc,x,'SLLI',rd,rs1,imm=sh)
        if f3==5 and f7==0:return Insn(pc,x,'SRLI',rd,rs1,imm=sh)
        if f3==5 and f7==0x20:return Insn(pc,x,'SRAI',rd,rs1,imm=sh)
    if op==0x33:
        if f7==0:return Insn(pc,x,('ADD','SLL','SLT','SLTU','XOR','SRL','OR','AND')[f3],rd,rs1,rs2)
        if f7==0x20 and f3==0:return Insn(pc,x,'SUB',rd,rs1,rs2)
        if f7==0x20 and f3==5:return Insn(pc,x,'SRA',rd,rs1,rs2)
        if f7==1:return Insn(pc,x,('MUL','MULH','MULHSU','MULHU','DIV','DIVU','REM','REMU')[f3],rd,rs1,rs2)
    if op==0x0f and f3 in (0,1):return Insn(pc,x,'FENCE' if f3==0 else 'FENCE.I')
    if op==0x73 and f3==0 and ((x>>20)&0xfff)==0:return Insn(pc,x,'ECALL')
    raise ValueError(f'unsupported instruction 0x{x:08x} at 0x{pc:08x}')


def parse_elf(path:Path):
    """Parse an ELF32 little-endian RISC-V executable without external tools.

    Decode instructions from SHF_EXECINSTR sections, not whole PF_X segments.
    A linker is allowed to place non-code bytes in an executable LOAD segment;
    treating the whole segment as instructions would silently corrupt the AOT
    translation.  Also collect STT_FUNC symbol addresses so indirect function
    pointer calls always land on a generated basic-block boundary.
    """
    data=path.read_bytes()
    if data[:4]!=b'\x7fELF' or data[4]!=1 or data[5]!=1:
        raise SystemExit('expected ELF32 little-endian')
    if struct.unpack_from('<H',data,18)[0]!=EM_RISCV:
        raise SystemExit('expected RISC-V ELF')
    entry=struct.unpack_from('<I',data,24)[0]
    shoff=struct.unpack_from('<I',data,32)[0]
    shentsize=struct.unpack_from('<H',data,46)[0]
    shnum=struct.unpack_from('<H',data,48)[0]
    shstrndx=struct.unpack_from('<H',data,50)[0]
    if shoff==0 or shentsize<40 or shnum==0:
        raise SystemExit('ELF section table is required for semantics-safe AOT')

    sections=[]
    for i in range(shnum):
        off=shoff+i*shentsize
        if off+40>len(data):
            raise SystemExit('truncated ELF section header table')
        sh=struct.unpack_from('<IIIIIIIIII',data,off)
        sections.append({
            'name_off':sh[0], 'type':sh[1], 'flags':sh[2], 'addr':sh[3],
            'offset':sh[4], 'size':sh[5], 'link':sh[6], 'info':sh[7],
            'addralign':sh[8], 'entsize':sh[9], 'index':i,
        })

    def section_blob(sec):
        if sec['type']==SHT_NOBITS:
            return b''
        a=sec['offset']; b=a+sec['size']
        if b>len(data):
            raise SystemExit(f"truncated ELF section #{sec['index']}")
        return data[a:b]

    # Section names are diagnostic only, but make audit failures actionable.
    if shstrndx<shnum:
        names=section_blob(sections[shstrndx])
        for sec in sections:
            no=sec['name_off']
            if no<len(names):
                z=names.find(b'\0',no)
                if z<0:z=len(names)
                sec['name']=names[no:z].decode('ascii','replace')
            else:
                sec['name']=f"#{sec['index']}"
    else:
        for sec in sections: sec['name']=f"#{sec['index']}"

    code={}
    data_bytes={}
    ranges=[]
    exec_section_indices=set()
    for sec in sections:
        if not (sec['flags'] & SHF_ALLOC):
            continue
        ranges.append((sec['name'],sec['addr'],sec['size'],sec['flags'],sec['type']))
        if sec['type']==SHT_NOBITS:
            # Sparse guest memory reads as zero, exactly matching ELF BSS.
            continue
        blob=section_blob(sec)
        if sec['flags'] & SHF_EXECINSTR:
            exec_section_indices.add(sec['index'])
            if sec['addr']%4 or len(blob)%4:
                raise SystemExit(f"executable section {sec['name']} is not RV32 word aligned")
            for j in range(0,len(blob),4):
                raw=struct.unpack_from('<I',blob,j)[0]
                pc=sec['addr']+j
                code[pc]=decode(pc,raw)
        else:
            for j,b in enumerate(blob):
                data_bytes[sec['addr']+j]=b

    if entry not in code:
        raise SystemExit(f'ELF entry 0x{entry:08x} is not inside an executable section')

    func_starts=set()
    for sec in sections:
        if sec['type']!=SHT_SYMTAB or sec['entsize']==0 or sec['link']>=shnum:
            continue
        blob=section_blob(sec)
        strtab=section_blob(sections[sec['link']])
        if sec['entsize']<16:
            raise SystemExit('unsupported ELF32 symbol entry size')
        for off in range(0,len(blob)-15,sec['entsize']):
            st_name,st_value,st_size,st_info,st_other,st_shndx=struct.unpack_from('<IIIBBH',blob,off)
            if (st_info & 0x0f)!=STT_FUNC:
                continue
            if st_shndx in exec_section_indices and st_value in code:
                func_starts.add(st_value)
    func_starts.add(entry)
    return entry,code,data_bytes,ranges,func_starts

TERMS={'JAL','JALR','BEQ','BNE','BLT','BGE','BLTU','BGEU','ECALL'}

def audit_indirect_jumps(code:dict[int,Insn]):
    bad=[]
    for pc,ins in sorted(code.items()):
        if ins.op=='JALR' and ins.rd==0 and ins.rs1!=1:
            bad.append((pc,ins.rs1,ins.imm))
    if bad:
        detail='\n'.join(f'  0x{pc:08x}: jalr x0, x{rs1}, {imm}' for pc,rs1,imm in bad[:20])
        raise SystemExit('AOT refuses computed intra-function/tail jumps whose targets cannot be proven from the ELF. Compile with -fno-jump-tables; suspicious JALR(s):\n'+detail)

def blocks(code:dict[int,Insn],entry:int,func_starts:set[int] | None=None):
    starts={entry}
    if func_starts:
        starts.update(func_starts)
    pcs=sorted(code)
    for pc in pcs:
        ins=code[pc]
        nxt=pc+4
        if ins.op in {'BEQ','BNE','BLT','BGE','BLTU','BGEU'}:
            starts.add((pc+ins.imm)&0xffffffff); starts.add(nxt)
        elif ins.op=='JAL':
            starts.add((pc+ins.imm)&0xffffffff)
            if ins.rd!=0: starts.add(nxt)
        elif ins.op in {'JALR','ECALL'}:
            starts.add(nxt)
    starts={s for s in starts if s in code}
    out={}
    for start in sorted(starts):
        seq=[]; pc=start
        while pc in code:
            if pc!=start and pc in starts:break
            ins=code[pc]; seq.append(ins)
            if ins.op in TERMS:break
            pc+=4
        out[start]=seq
    covered={i.pc for seq in out.values() for i in seq}
    # Unreachable code can still be the target of a function pointer. Create blocks for all remaining instructions.
    for pc in pcs:
        if pc in covered:continue
        seq=[]; p=pc
        while p in code and p not in covered:
            ins=code[p];seq.append(ins);covered.add(p)
            if ins.op in TERMS:break
            p+=4
        out[pc]=seq
    return dict(sorted(out.items()))


def w32(x:int)->int:
    x&=0xffffffff; return x-0x100000000 if x>=0x80000000 else x

def addr_expr(rs:int,imm:int)->str:
    return f'doom_i32(rv_reg_read({rs}) + {imm})'

def emit_ins(ins:Insn, lines:list[str], last:bool):
    p=ins.pc; n=w32(p+4); o=ins.op
    rr=lambda r:f'rv_reg_read({r})'
    wr=lambda r,e: lines.append(f'  rv_reg_write({r}, {e})') if r else None
    if o=='LUI':wr(ins.rd,str(w32(ins.imm)))
    elif o=='AUIPC':wr(ins.rd,f'doom_i32({w32(p)} + {ins.imm})')
    elif o=='ADDI':wr(ins.rd,f'doom_i32({rr(ins.rs1)} + {ins.imm})')
    elif o=='SLTI':wr(ins.rd,f'rv_slt({rr(ins.rs1)}, {ins.imm})')
    elif o=='SLTIU':wr(ins.rd,f'rv_sltu({rr(ins.rs1)}, {w32(ins.imm)})')
    elif o=='XORI':wr(ins.rd,f'doom_bxor32({rr(ins.rs1)}, {w32(ins.imm)})')
    elif o=='ORI':wr(ins.rd,f'doom_bor32({rr(ins.rs1)}, {w32(ins.imm)})')
    elif o=='ANDI':wr(ins.rd,f'doom_band32({rr(ins.rs1)}, {w32(ins.imm)})')
    elif o=='SLLI':wr(ins.rd,f'doom_shl32({rr(ins.rs1)}, {ins.imm})')
    elif o=='SRLI':wr(ins.rd,f'doom_shr_u32({rr(ins.rs1)}, {ins.imm})')
    elif o=='SRAI':wr(ins.rd,f'doom_sar32({rr(ins.rs1)}, {ins.imm})')
    elif o=='ADD':wr(ins.rd,f'doom_i32({rr(ins.rs1)} + {rr(ins.rs2)})')
    elif o=='SUB':wr(ins.rd,f'doom_i32({rr(ins.rs1)} - {rr(ins.rs2)})')
    elif o=='SLL':wr(ins.rd,f'doom_shl32({rr(ins.rs1)}, doom_u5({rr(ins.rs2)}))')
    elif o=='SLT':wr(ins.rd,f'rv_slt({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='SLTU':wr(ins.rd,f'rv_sltu({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='XOR':wr(ins.rd,f'doom_bxor32({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='SRL':wr(ins.rd,f'doom_shr_u32({rr(ins.rs1)}, doom_u5({rr(ins.rs2)}))')
    elif o=='SRA':wr(ins.rd,f'doom_sar32({rr(ins.rs1)}, doom_u5({rr(ins.rs2)}))')
    elif o=='OR':wr(ins.rd,f'doom_bor32({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='AND':wr(ins.rd,f'doom_band32({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='MUL':wr(ins.rd,f'doom_i32({rr(ins.rs1)} * {rr(ins.rs2)})')
    elif o=='MULH':wr(ins.rd,f'rv_mulh_signed({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='MULHSU':wr(ins.rd,f'rv_mulhsu({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='MULHU':wr(ins.rd,f'rv_mulhu({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='DIV':wr(ins.rd,f'rv_div({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='DIVU':wr(ins.rd,f'rv_divu({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='REM':wr(ins.rd,f'rv_rem({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o=='REMU':wr(ins.rd,f'rv_remu({rr(ins.rs1)}, {rr(ins.rs2)})')
    elif o in {'LB','LH','LW','LBU','LHU'}:
        fn={'LB':'rv_load_i8','LH':'rv_load_i16','LW':'rv_load_i32','LBU':'rv_load_u8','LHU':'rv_load_u16'}[o]
        wr(ins.rd,f'{fn}({addr_expr(ins.rs1,ins.imm)})')
    elif o in {'SB','SH','SW'}:
        fn={'SB':'rv_store_u8','SH':'rv_store_u16','SW':'rv_store_u32'}[o]
        lines.append(f'  {fn}({addr_expr(ins.rs1,ins.imm)}, {rr(ins.rs2)})')
    elif o in {'FENCE','FENCE.I'}:pass
    elif o=='JAL':
        wr(ins.rd,str(n)); lines.append(f'  g100 = {w32(p+ins.imm)}'); return True
    elif o=='JALR':
        lines.append(f'  l0 = {addr_expr(ins.rs1,ins.imm)}')
        wr(ins.rd,str(n)); lines.append('  if l0 % 2 ~= 0 then'); lines.append('    l0 = l0 - 1'); lines.append('  end'); lines.append('  g100 = l0'); return True
    elif o in {'BEQ','BNE','BLT','BGE','BLTU','BGEU'}:
        if o=='BEQ':cond=f'{rr(ins.rs1)} == {rr(ins.rs2)}'
        elif o=='BNE':cond=f'{rr(ins.rs1)} ~= {rr(ins.rs2)}'
        elif o=='BLT':cond=f'{rr(ins.rs1)} < {rr(ins.rs2)}'
        elif o=='BGE':cond=f'{rr(ins.rs1)} >= {rr(ins.rs2)}'
        elif o=='BLTU':cond=f'doom_u32_lt({rr(ins.rs1)}, {rr(ins.rs2)}) ~= 0'
        else:cond=f'doom_u32_lt({rr(ins.rs1)}, {rr(ins.rs2)}) == 0'
        lines.append(f'  if {cond} then');lines.append(f'    g100 = {w32(p+ins.imm)}');lines.append('  else');lines.append(f'    g100 = {n}');lines.append('  end');return True
    elif o=='ECALL':
        lines.append('  rv_ecall()'); lines.append(f'  g100 = {n}'); return True
    else: raise AssertionError(o)
    if last:
        lines.append(f'  g100 = {n}')
    return False


def data_words(data_bytes):
    words={}
    for a,b in data_bytes.items():
        wa=a&~3; sh=(a&3)*8; words[wa]=words.get(wa,0)|(b<<sh)
    return {a:w32(v) for a,v in words.items()}


def emit_dispatch(starts:list[int], lines:list[str], leaf=16):
    counter=[0]
    def rec(vals):
        name=f'rv_aot_dispatch_{counter[0]}';counter[0]+=1
        body=[f'function {name}()']
        if len(vals)<=leaf:
            for i,pc in enumerate(vals):
                kw='if' if i==0 else 'elseif';body.append(f'  {kw} g100 == {w32(pc)} then');body.append(f'    rv_aot_bb_{pc}()')
            body += ['  else','    g102 = 9201','    g101 = 0','  end','  return','end','']
        else:
            m=len(vals)//2; left=rec(vals[:m]); right=rec(vals[m:]); pivot=vals[m]
            body += [f'  if g100 < {w32(pivot)} then',f'    {left}()','  else',f'    {right}()','  end','  return','end','']
        lines.extend(body)
        return name
    root=rec(starts)
    return root


def emit(elf:Path,out:Path,fb_base:int,palette_base:int,config_base:int,stack_top:int):
    entry,code,db,ranges,func_starts=parse_elf(elf); audit_indirect_jumps(code); bs=blocks(code,entry,func_starts); lines=['-- generated RV32IM AOT guest; original machine semantics, no Doom gameplay rewrite.']
    # Emit block functions first.
    for start,seq in bs.items():
        lines.append(f'function rv_aot_bb_{start}()');lines.append('  local l0')
        for idx,ins in enumerate(seq):
            terminated=emit_ins(ins,lines,idx==len(seq)-1)
            if terminated: break
        lines.append(f'  g104 = doom_i32(g104 + {len(seq)})');lines.append('  GT[800][0] = 0');lines.append('  return');lines.append('end');lines.append('')
    dlines=[]; root=emit_dispatch(list(bs),dlines); lines.extend(dlines)
    words=data_words(db)
    # Guest image initialization is itself frame-stepped by the permanent HCB
    # scheduler loop.  Never hide tens of thousands of GT stores behind one
    # long function that only occasionally calls ThreadNext().
    image_items=sorted(words.items())
    image_chunk_words=256
    image_chunks=[image_items[i:i+image_chunk_words] for i in range(0,len(image_items),image_chunk_words)]
    for chunk_idx,chunk in enumerate(image_chunks):
        lines.append(f'function doom_guest_image_init_chunk_{chunk_idx}()')
        for addr,val in chunk:
            lines.append(f'  GT[801][{addr//4}] = {val}')
        lines += ['  return','end','']
    lines += ['function doom_guest_image_init_step()']
    if image_chunks:
        for chunk_idx in range(len(image_chunks)):
            kw='if' if chunk_idx==0 else 'elseif'
            lines += [f'  {kw} g123 == {chunk_idx} then',f'    doom_guest_image_init_chunk_{chunk_idx}()']
        lines += ['  else','    return 1','  end']
        lines += ['  g123 = g123 + 1']
        lines += [f'  if g123 < {len(image_chunks)} then','    return 0','  end']
    lines += [f'  g110 = {w32(entry)}',f'  g106 = {fb_base}','  g107 = 4000','  g111 = 0','  g112 = 0',f'  g113 = {palette_base}',f'  g114 = {config_base}',f'  g115 = {stack_top}','  g116 = 0','  return 1','end','']
    lines += ['function rv_aot_run_slice(a0)','  local l0','  l0 = 0','  g105 = 0','  while g101 ~= 0 do','    if l0 >= a0 then','      return','    end','    if g105 ~= 0 then','      return','    end',f'    {root}()','    l0 = l0 + 1','  end','  return','end','']
    out.write_text('\n'.join(lines),encoding='utf-8')
    print(f'entry=0x{entry:08x} instructions={len(code)} blocks={len(bs)} functions={len(func_starts)} data_words={len(words)} ranges={ranges}')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('elf',type=Path);ap.add_argument('-o','--out',type=Path,required=True)
    ap.add_argument('--fb-base',type=lambda s:int(s,0),default=0x10000000);ap.add_argument('--palette-base',type=lambda s:int(s,0),default=0x10001000);ap.add_argument('--config-base',type=lambda s:int(s,0),default=0x10002000);ap.add_argument('--stack-top',type=lambda s:int(s,0),default=0x03f00000)
    ns=ap.parse_args();emit(ns.elf,ns.out,ns.fb_base,ns.palette_base,ns.config_base,ns.stack_top)
if __name__=='__main__':main()
