#!/usr/bin/env python3
from __future__ import annotations
import argparse,re,sys,yaml
from dataclasses import dataclass
from pathlib import Path

TOK=re.compile(r'''\s*(?:(-?\d+(?:\.\d+)?)|([A-Za-z_]\w*)|("(?:\\.|[^"\\])*")|(==|~=|<=|>=|[()\[\],+*/%&<>-]))''')

class Error(Exception): pass

@dataclass
class Node:
    kind:str
    val:object=None
    kids:tuple=()

class ExprParser:
    def __init__(self,s):
        self.s=s; self.ts=[]; pos=0
        while pos<len(s):
            m=TOK.match(s,pos)
            if not m: raise Error(f'unsupported expression near {s[pos:]!r} in {s!r}')
            num,ident,string,op=m.groups(); pos=m.end()
            if num is not None: self.ts.append(('num',num))
            elif ident is not None: self.ts.append(('id',ident))
            elif string is not None: self.ts.append(('str',string))
            else:self.ts.append((op,op))
        self.i=0
    def peek(self,*k): return self.i<len(self.ts) and self.ts[self.i][0] in k
    def pop(self,k=None):
        if self.i>=len(self.ts):raise Error('unexpected end of expression')
        t=self.ts[self.i]
        if k and t[0]!=k:raise Error(f'expected {k}, got {t}')
        self.i+=1; return t
    def parse(self):
        n=self.or_()
        if self.i!=len(self.ts):raise Error(f'trailing token {self.ts[self.i]}')
        return n
    def or_(self):
        n=self.and_()
        while self.peek('id') and self.ts[self.i][1]=='or': self.pop(); n=Node('bin','or',(n,self.and_()))
        return n
    def and_(self):
        n=self.cmp()
        while self.peek('id') and self.ts[self.i][1]=='and': self.pop(); n=Node('bin','and',(n,self.cmp()))
        return n
    def cmp(self):
        n=self.add()
        while self.peek('==','~=','<','<=','>','>='):
            op=self.pop()[0]; n=Node('bin',op,(n,self.add()))
        return n
    def add(self):
        n=self.mul()
        while self.peek('+','-'):
            op=self.pop()[0]; n=Node('bin',op,(n,self.mul()))
        return n
    def mul(self):
        n=self.bitand()
        while self.peek('*','/','%'):
            op=self.pop()[0]; n=Node('bin',op,(n,self.bitand()))
        return n
    def bitand(self):
        n=self.unary()
        while self.peek('&'):
            self.pop(); n=Node('bin','&',(n,self.unary()))
        return n
    def unary(self):
        if self.peek('-'): self.pop(); return Node('neg',kids=(self.unary(),))
        return self.primary()
    def primary(self):
        if self.peek('num'): return Node('lit',self.pop()[1])
        if self.peek('str'): return Node('lit',self.pop()[1])
        if self.peek('('):
            self.pop(); n=self.or_(); self.pop(')'); return n
        if self.peek('id'):
            name=self.pop()[1]
            if name in ('nil','true','false'): return Node('lit',name)
            if self.peek('('):
                self.pop(); args=[]
                if not self.peek(')'):
                    while True:
                        args.append(self.or_())
                        if self.peek(','):self.pop();continue
                        break
                self.pop(')'); return Node('call',name,tuple(args))
            if name in ('GT','LT') and self.peek('['):
                self.pop(); idx=self.pop()
                if idx[0] not in ('num','-'): raise Error('table id must be integer')
                if idx[0]=='-': idx='-'+self.pop('num')[1]
                else: idx=idx[1]
                self.pop(']'); self.pop('['); key=self.or_(); self.pop(']')
                return Node('table',(name,idx),(key,))
            return Node('var',name)
        raise Error(f'unexpected token {self.ts[self.i] if self.i<len(self.ts) else None}')

def walk(n):
    yield n
    for k in n.kids:
        yield from walk(k)

def validate_expr(s, globals_, funcs, syscalls):
    n=ExprParser(s).parse()
    for x in walk(n):
        if x.kind=='var':
            name=x.val
            if not (re.fullmatch(r'[al]\d+',name) or re.fullmatch(r'S\d+',name) or name=='__ret' or name in globals_):
                raise Error(f'unsupported variable {name!r} in {s!r}')
        elif x.kind=='call':
            if x.val not in funcs and x.val not in syscalls and not x.val.startswith('f_'):
                raise Error(f'unknown callee {x.val!r} in {s!r}')
        elif x.kind=='bin' and x.val=='&':
            # lua2hcb only accepts (x & bit) ~= 0, where BitTest interprets RHS as bit index.
            pass
    # Reject plain bit-and unless it is exactly the left operand of !=0.
    def check(node,parent=None):
        if node.kind=='bin' and node.val=='&':
            ok=parent and parent.kind=='bin' and parent.val=='~=' and parent.kids[0] is node and parent.kids[1].kind=='lit' and str(parent.kids[1].val)=='0'
            if not ok: raise Error(f"plain '&' value unsupported in {s!r}")
        for c in node.kids: check(c,node)
    check(n)

def split_assignment(s):
    depthp=depthb=0; instr=False; esc=False
    for i,ch in enumerate(s):
        if instr:
            if esc:esc=False
            elif ch=='\\':esc=True
            elif ch=='"':instr=False
            continue
        if ch=='"':instr=True
        elif ch=='(':depthp+=1
        elif ch==')':depthp-=1
        elif ch=='[':depthb+=1
        elif ch==']':depthb-=1
        elif ch=='=' and depthp==0 and depthb==0:
            prev=s[i-1] if i else ''; nxt=s[i+1] if i+1<len(s) else ''
            if prev not in '=~<>' and nxt!='=': return s[:i].strip(),s[i+1:].strip()
    return None

def validate(path:Path, meta:Path):
    lines=path.read_text(encoding='utf-8').splitlines()
    doc=yaml.safe_load(meta.read_text())
    syscalls={v['name'] for v in doc['syscalls'].values()} if isinstance(doc['syscalls'],dict) else {v['name'] for v in doc['syscalls']}
    globals_=set(); funcs=set()
    firstfn=None
    for i,line in enumerate(lines):
        t=line.strip()
        if not t or t.startswith('--'):continue
        m=re.fullmatch(r'(?:local\s+)?function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)',t)
        if m:
            firstfn=i;break
        gm=re.fullmatch(r'(?:volatile\s+)?global\s+(.+)',t)
        if not gm:raise Error(f'{i+1}: invalid top-level {t!r}')
        for n in gm.group(1).split(','):
            n=n.strip()
            if not re.fullmatch(r'(?:g|vg)\d+',n):raise Error(f'{i+1}: bad global {n}')
            globals_.add(n)
    if firstfn is None:raise Error('no function')
    for line in lines[firstfn:]:
        m=re.fullmatch(r'(?:local\s+)?function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)',line.strip())
        if m:funcs.add(m.group(1))
    stack=[]
    for i,line in enumerate(lines[firstfn:],start=firstfn+1):
        t=line.strip()
        if not t or t.startswith('--'):continue
        if re.fullmatch(r'(?:local\s+)?function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)',t): stack.append('function');continue
        if t.startswith('if ') and t.endswith(' then'):
            validate_expr(t[3:-5],globals_,funcs,syscalls); stack.append('if');continue
        if t.startswith('elseif ') and t.endswith(' then'):
            if not stack or stack[-1]!='if':raise Error(f'{i}: elseif outside if')
            validate_expr(t[7:-5],globals_,funcs,syscalls);continue
        if t=='else':
            if not stack or stack[-1]!='if':raise Error(f'{i}: else outside if')
            continue
        if t.startswith('while ') and t.endswith(' do'):
            validate_expr(t[6:-3],globals_,funcs,syscalls); stack.append('while');continue
        if t=='end':
            if not stack:raise Error(f'{i}: unmatched end')
            stack.pop();continue
        if t=='break':continue
        if t=='return':continue
        if t.startswith('return '): validate_expr(t[7:].strip(),globals_,funcs,syscalls);continue
        if t.startswith('local ') and '=' not in t:continue
        s=t[6:].strip() if t.startswith('local ') else t
        asn=split_assignment(s)
        if asn:
            lhs,rhs=asn
            if not (re.fullmatch(r'[al]\d+',lhs) or re.fullmatch(r'S\d+',lhs) or lhs=='__ret' or lhs in globals_ or re.fullmatch(r'GT\[\d+\]\[.+\]',lhs) or re.fullmatch(r'LT\[-?\d+\]\[.+\]',lhs)):
                raise Error(f'{i}: unsupported lhs {lhs!r}')
            if lhs.startswith('GT[') or lhs.startswith('LT['):
                key=lhs[lhs.find('][',2)+2:-1]; validate_expr(key,globals_,funcs,syscalls)
            validate_expr(rhs,globals_,funcs,syscalls);continue
        validate_expr(s,globals_,funcs,syscalls)
    if stack:raise Error(f'unclosed blocks: {stack}')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('luax',type=Path);ap.add_argument('--meta',type=Path,required=True);ns=ap.parse_args()
    try: validate(ns.luax,ns.meta)
    except Error as e: print(f'ERROR: {e}',file=sys.stderr);raise SystemExit(1)
    print('Luax static validation: OK')
