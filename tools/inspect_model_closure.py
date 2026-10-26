"""Bounded read-only model closure inventory; never executes or copies vendor models."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.pspice_input import PSpiceInputs,REFERENCE,ARGUMENT,FILE_DIRECTIVES
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','cir'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.cir.resolve();service=PSpiceInputs(Config(a.install_root,root/'work',(source.parent.parent,a.install_root/'tools/pspice/library')));seen={};stack=set();total=0
result={'passed':False}
def visit(path,depth):
 global total
 if path in stack:raise ValueError('cycle')
 if path in seen:return
 if depth>32 or len(seen)>=1024 or path.stat().st_size>32*1024*1024:raise ValueError('diagnostic_limit')
 raw=path.read_bytes();total+=len(raw)
 if total>256*1024*1024:raise ValueError('diagnostic_total_limit')
 text=raw.decode('utf-8-sig',errors='surrogateescape');assert '\x00' not in text
 seen[path]={'sha256':sha256(path),'size':len(raw),'opaqueBytes':sum(0xdc80<=ord(c)<=0xdcff for c in text),'depth':depth};stack.add(path)
 for i,line in enumerate(text.splitlines(),1):
  s=line.strip()
  if not s or s.startswith('*'):continue
  if s.split()[0].upper() in FILE_DIRECTIVES:raise ValueError('unsupported_file_directive:'+str(path)+':'+str(i))
  m=REFERENCE.match(line)
  if m:
   arg=ARGUMENT.fullmatch(m[2])
   if not arg:raise ValueError('unsupported_reference:'+str(path)+':'+str(i))
   name=next(x for x in arg.groups() if x is not None);visit(service._reference(path,name),depth+1)
 stack.remove(path)
try:visit(source,0);result['passed']=True
except Exception as e:result.update(error=str(e),errorCode=getattr(e,'code',None))
result.update(fileCount=len(seen),totalBytes=total,maxFileBytes=max([v['size'] for v in seen.values()],default=0),maxDepth=max([v['depth'] for v in seen.values()],default=0),files={str(k):v for k,v in seen.items()});(root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='files'}))
