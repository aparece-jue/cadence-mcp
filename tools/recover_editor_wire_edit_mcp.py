"""Verify-only audit of the two completed tasks; never repeats native edits."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
r=Path(r'D:\workspace\git\cadence-mcp');base=r/'.local/editor-wire-edits-mcp-20261027';root=r/'.local/editor-wire-edits-audit-20261027';root.mkdir(exist_ok=False)
install=Path(r'D:\Program Files\Cadence\SPB_24.1');source=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.dsn'
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(install),'--workspace-root',str(base/'work'),'--read-root',str(source.parent),'--timeout-seconds','45'],env=env)
rows=[]
for file in sorted((base/'work/isolated-jobs/capture_wire_edit').glob('*/plan.json')):
 row=json.loads(file.read_text(encoding='utf-8'));assert row['state']=='verified';rows.append((file,row))
assert len(rows)==2
def files():return {p.relative_to(base/'work').as_posix():sha256(p) for p in (base/'work').rglob('*') if p.is_file()}
async def main():
 report={'passed':False,'noNativeReplay':True,'cases':[]};frozen=files()
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   for file,row in rows:
    p=row['plan'];op=p['payload']['operation'];key={'planId':p['planId'],'planDigest':row['digest']}
    for name,args in [('capture_apply_wire_edit',{**key,'idempotencyKey':op}),('capture_recover_wire_edit',key)]:
     result=await client.call_tool(name,args);assert not result.is_error,result.structured_content
    result=await client.call_tool('capture_open_edit_result',{**key,'kind':'wire_edit'});assert not result.is_error,result.structured_content
    target=file.parent/'design.dsn';cfg=Config(install,root/'work',(target.parent,),45)
    output=root/(op+'.json');run_tcl(cfg,'inspect_page_objects.tcl',[str(target),str(output),'connections'],root)
    actual=json.loads(output.read_text(encoding='utf-8'))['objects']
    prior=json.loads((r/'.local/placewire-junction-20261027/connections.json').read_text(encoding='utf-8'))['objects']
    def stable(items):return sorted((tuple(map(tuple,w['attributes']['points'])),w['attributes']['net']) for w in items if w['kind']=='wire')
    wanted=[w for w in prior if w['attributes']['points']!=[[100,100],[300,100]]]
    if op=='set_endpoints':wanted.append({'kind':'wire','attributes':{'points':[[100,120],[300,120]],'net':'N00001'}})
    assert stable(actual)==stable(wanted),'wire geometry/net identity changed'
    report['cases'].append({'operation':op,'allWireGeometryAndNetIdentityVerified':True,'freshServiceApplyRecoverOpenAccepted':True})
  report['taskFilesUnchanged']=files()==frozen;assert report['taskFilesUnchanged']
  report['passed']=True
 except BaseException as error:report['error']=traceback.format_exc()
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
asyncio.run(main())
