"""Conservative proof for flat literal R/C/L/V/I circuits with entirely unused .LIB definitions.
Unknown devices/expressions remain refused; this is not a general model resolver.
"""
import re
from pathlib import Path
from .core import CadenceError
from .pspice_input import REFERENCE,ARGUMENT
NUM=r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?(?:MEG|MIL|[TGKMUNPF])?(?:VDC|VAC|OHM|[VAHFS])?'
NUMBER=re.compile(NUM+r'$',re.I)
NAME=re.compile(r'[A-Za-z0-9_.$:+-]+$')
BAD=re.compile(r'\b(?:FILE|PATH|LIBPATH|DLL|STMLIB|STIMULUS|TABLEFILE)\s*=',re.I)

def fail():raise CadenceError('model_use_unresolved','Literal built-in circuit and unused-library scope could not be proven.')
def logical_lines(text):
    records=[]
    for number,line in enumerate(text.splitlines(),1):
        s=line.strip()
        if not s or s.startswith(('*',';')):continue
        # PSpice semicolon ends the line; quotes on reference lines are handled separately.
        if s.startswith('+'):
            if not records:fail()
            records[-1][1]+=' '+s[1:].split(';',1)[0].strip()
        else:records.append([number,s if REFERENCE.match(s) else s.split(';',1)[0].strip()])
    return records

def prove_unused_libraries(root,files,rows,check):
    """Return deterministic proof; reference edges are bound to exact copied paths/physical lines."""
    by={r['relativePath']:r for r in rows}
    if set(files)!=set(by) or 'input.cir' not in files:fail()
    edges={}
    for name,raw in files.items():
        text=raw.decode('utf-8-sig',errors='surrogateescape');refs=by[name]['references'];declared={}
        for number,line in enumerate(text.splitlines(),1):
            if line.lstrip().startswith('*'):continue
            m=REFERENCE.match(line)
            if m:
                arg=ARGUMENT.fullmatch(m[2])
                if arg is None:fail()
                declared[number]=(m[1].upper(),next(x for x in arg.groups() if x is not None))
        if len(declared)!=len(refs):fail()
        outgoing=[]
        for ref in refs:
            if ref['line'] not in declared or ref['targetRelativePath'] not in files:fail()
            directive,path=declared[ref['line']]
            if directive!=ref['directive'] or Path(path).resolve()!=(root/ref['targetRelativePath']).resolve():fail()
            outgoing.append((directive,ref['targetRelativePath']))
        edges[name]=outgoing
    eager=set();pending=['input.cir']
    while pending:
        name=pending.pop()
        if name in eager:continue
        eager.add(name);pending.extend(target for directive,target in edges[name] if directive in ('INC','INCLUDE'))
    libraries=set();pending=[t for n in eager for d,t in edges[n] if d=='LIB']
    while pending:
        name=pending.pop()
        if name in libraries:continue
        if name in eager:fail()
        libraries.add(name)
        if any(d!='LIB' for d,t in edges[name]):fail()
        pending.extend(t for d,t in edges[name])
    if not libraries or eager|libraries!=set(files):fail()
    devices=0
    for name in sorted(eager):
        text=files[name].decode('utf-8-sig',errors='surrogateescape');check(text)
        for number,line in logical_lines(text):
            if name=='input.cir' and number==1:continue # SPICE title line
            fields=line.split();kind=fields[0].upper()
            if kind in ('.INC','.INCLUDE','.LIB','.END','.OP'):continue
            if kind in ('.AC','.DC','.TRAN'):
                args=fields[1:]
                if kind=='.AC':
                    if len(args)!=4 or args[0].upper() not in ('LIN','DEC','OCT') or not all(NUMBER.fullmatch(x) for x in args[1:]):fail()
                elif kind=='.DC':
                    if len(args)!=4 or not re.fullmatch(r'[VI][A-Za-z0-9_.$:+-]*',args[0],re.I) or not all(NUMBER.fullmatch(x) for x in args[1:]):fail()
                elif not 2<=len(args)<=4 or not all(NUMBER.fullmatch(x) for x in args):fail()
                continue
            if kind=='.OPTIONS':
                if fields[1:]!=['ADVCONV']:fail()
                continue
            if kind in ('.PROBE','.PROBE64','.PRINT'):
                args=fields[1:]
                if kind=='.PRINT':
                    if not args or args.pop(0).upper() not in ('AC','DC','TRAN'):fail()
                if not args or not all(re.fullmatch(r'(?:V|I|W|D|NOISE)\((?:alias\(\*\)|[A-Za-z0-9_.*:+,-]+)\)',a,re.I) for a in args):fail()
                continue
            if len(fields)<4 or not re.fullmatch(r'[RCLVI][A-Za-z0-9_.$:+-]*',fields[0],re.I) or not all(NAME.fullmatch(n) for n in fields[1:3]):fail()
            device=kind[0];values=fields[3:]
            if device in 'RCL':
                if not NUMBER.fullmatch(values[0]) or len(values)>2:fail()
                if len(values)==2 and (device=='L' or not re.fullmatch('TC='+NUM+','+NUM,values[1],re.I)):fail()
            else:
                if len(values)==1:
                    if not NUMBER.fullmatch(values[0]):fail()
                else:
                    if values[0].upper() not in ('DC','AC') or not NUMBER.fullmatch(values[1]):fail()
                    if len(values)>2 and (values[0].upper()!='DC' or len(values) not in (4,5) or values[2].upper()!='AC' or not all(NUMBER.fullmatch(x) for x in values[3:])):fail()
            devices+=1
    if not devices:fail()
    inactive_files=0
    for name in sorted(libraries):
        depth=0
        for number,line in logical_lines(files[name].decode('utf-8-sig',errors='surrogateescape')):
            if depth==0 and re.fullmatch(r'[-=]{3,}',line):continue
            fields=line.split();kind=fields[0].upper()
            if kind=='.SUBCKT':
                if len(fields)<2:fail()
                depth+=1
                if depth>32:fail()
            elif kind=='.ENDS':
                if depth==0:fail()
                depth-=1
            elif kind.startswith('.'):
                if kind not in ('.MODEL','.PARAM','.FUNC','.LIB','.IC','.NODESET','.OPTIONS','.END'):fail()
                check(line)
            elif depth==0:fail()
            # Only uninstantiated digital primitive FILE templates are exempted.
            if BAD.search(line):
                if depth>0 and re.fullmatch(r'U[A-Za-z0-9_.$:+-]*',fields[0],re.I):
                    if re.search(r'\b(?:PATH|LIBPATH|DLL|STMLIB|STIMULUS|TABLEFILE)\s*=',line,re.I):fail()
                    inactive_files+=1
                else:check(line)
        if depth:fail()
    return {'kind':'flat_literal_builtins_no_library_requests@1','eagerFiles':sorted(eager),'libraryFiles':sorted(libraries),'builtinDevices':devices,'inactiveDigitalFileTemplates':inactive_files,'modelRequests':0,'subcircuitRequests':0}
