"""Dispatch only the original still-planned negative case with a distinct key."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
from cadence_mcp.native_host_fence import read_fence
r=Path(r'D:\workspace\git\cadence-mcp');base=r/'.local/editor-repeated-refusals-20261027';root=r/'.local/editor-refusal-final-audit-20261027';root.mkdir(exist_ok=False)
pending=[]
for path in (base/'work/isolated-jobs/capture_wire_add').glob('*/plan.json'):
 row=json.loads(path.read_text(encoding='utf-8'))
 if row['state']=='planned':pending.append((path,row))
assert len(pending)==1;path,row=pending[0];p=row['plan']['payload'];assert p['editorOccurrence']=='missing_instance' and not (path.parent/'entered.txt').exists()
key={'planId':row['plan']['planId'],'planDigest':row['digest']};source=Path(p['sourceDesign']);before=sha256(source);project=Path(p['editorHost']['hostProject']);bindings=r/'.local/editor-wire-fresh-binding-20261027'
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(base/'work'),'--read-root',str(project.parent),'--gui-bridge-root',str(bindings),'--timeout-seconds','30'],env=env)
async def main():
 report={'passed':False,'noPreviousNativeDispatch':True,'originalNegativeCaseOnly':True,'plan':key}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   reply=await client.call_tool('capture_apply_wire_add',{**key,'idempotencyKey':'refuse-invalid-occurrence'});assert reply.is_error and reply.structured_content['error']['code']=='native_write_failed',reply.structured_content or reply.content
   receipt=json.loads((path.parent/'native-result.json').read_text(encoding='utf-8'));report['receipt']=receipt
   assert receipt['error']=='invalid_editor_occurrence' and receipt['phase']=='open_page' and receipt['saved'] is False and receipt['hostRestored'] is True
   assert sha256(path.parent/'design.dsn')==before and not (path.parent/'design.dsnlck').exists();assert read_fence(Path(p['editorHost']['bindingPath'])) is None
   assert (await client.call_tool('capture_open_edit_result',{**key,'kind':'wire_add'})).is_error
   repeat=await client.call_tool('capture_apply_wire_add',{**key,'idempotencyKey':'refuse-invalid-occurrence'});assert repeat.is_error and repeat.structured_content['error']['code']=='write_not_replayed'
   report.update(passed=True,sourceCopyUnchanged=True,hostRestored=True,outputClosed=True,fenceReleasedOnKnownRefusal=True,noReplay=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
asyncio.run(main())
