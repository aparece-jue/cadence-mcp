"""Observe the original late task once; no second native business dispatch."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
r=Path(r'D:\workspace\git\cadence-mcp');base=r/'.local/editor-interior-short-20261027';root=r/'.local/editor-short-late-audit-20261027';root.mkdir(exist_ok=False)
report=json.loads((base/'report.json').read_text(encoding='utf-8'));key={k:report['plan'][k] for k in ('planId','planDigest')};d=base/'work/isolated-jobs/capture_wire_add'/('plan-'+key['planId']);row=json.loads((d/'plan.json').read_text(encoding='utf-8'));source=Path(row['plan']['payload']['sourceDesign']);before=sha256(d/'design.dsn')
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(base/'work'),'--read-root',str(source.parent),'--read-root',str(r/'.local/placewire-resume-v2-20261027'),'--gui-bridge-root',str(r/'.local/editor-wire-fresh-binding-20261027'),'--timeout-seconds','30'],env=env)
async def main():
 audit={'nativeMutationReplayed':False,'outputBefore':before,'lateReceipt':json.loads((d/'native-result.json').read_text(encoding='utf-8'))}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   result=await client.call_tool('capture_recover_wire_add',key);audit['recoveryError']=result.is_error;audit['recovery']=result.structured_content
  cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(d,),30)
  for adapter,name,args in [('inspect.tcl','definitions.json',['100000']),('inspect_page_objects.tcl','connections.json',['connections'])]:run_tcl(cfg,adapter,[str(d/'design.dsn'),str(root/name),*args],root)
 except BaseException:audit['error']=traceback.format_exc()
 audit['outputUnchanged']=sha256(d/'design.dsn')==before
 (root/'report.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit),flush=True)
asyncio.run(main())
