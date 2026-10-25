"""Reuse accepted homogeneous job; new legal heterogeneous fixture and preflight bounds."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','previous-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);previous=a.previous_root.resolve(strict=True);old_path=previous/'report.json';old_sha=sha256(old_path);old=json.loads(old_path.read_text());specs=json.loads((previous/'expected.json').read_text());hom=next(c for c in old['cases'] if c['name']=='homogeneous');assert hom['passed'] and not old['passed'];het=copy.deepcopy(specs['heterogeneous']);het['devices'][1]['mapping'][0]['swapId']=102;het['devices'][1]['mapping'][1]['swapId']=102
(root/'expected-heterogeneous.json').write_text(json.dumps(het,indent=2),encoding='utf-8');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(previous/'work'),'--read-root',str(root),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'originalReportStillFailed':True,'originalReportSha256':old_sha,'scope':'multiunit shared/positive swapId metadata and legal-range preflight; no actual pin-swap operation or DSN package-instance integration'}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   tools=(await client.list_tools()).tools;assert len(tools)==137;(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
   key={k:hom['plan'][k] for k in ('planId','planDigest')};r=await call('capture_apply_library_create',{**key,'idempotencyKey':'homogeneous'});assert not r['mutationReplayed'];await call('capture_recover_library_create',key);opened=await call('capture_open_created_library',key);pins=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'pin','limit':1000}))['items'];assert len(pins)==8 and len({p['number'] for p in pins})==7;report['homogeneousExistingJobReopenedWithoutReplay']=True
   for value in (127,202,4095):
    bad=copy.deepcopy(specs['homogeneous']);bad['devices'][0]['mapping'][0]['swapId']=value;assert (await client.call_tool('capture_plan_library_create',{'spec':bad})).is_error
   report['outOfRangeSchemaRefused']=[127,202,4095]
   bad=copy.deepcopy(het);bad['devices'][2]['mapping'][0]['swapId']=1;assert (await client.call_tool('capture_plan_library_create',{'spec':bad})).is_error;report['inRangeConflictingSharedSwapRefused']=True
   plan=await call('capture_plan_library_create',{'spec':het});hk={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_library_create',{**hk,'idempotencyKey':'heterogeneous-legal-101-102'});opened=await call('capture_open_created_library',hk);pins=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'pin','limit':1000}))['items'];assert result['declaredGraphVerified'] and len(pins)==12 and result['uniquePhysicalPadCount']==8;report['heterogeneous']={'plan':plan,'result':result,'pins':pins};assert {p['swapId'] for p in pins}=={0,101,102}
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   v=await client.call_tool('capture_apply_library_create',{**hk,'idempotencyKey':'heterogeneous-legal-101-102'});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_library_create',hk)).is_error;assert not (await client.call_tool('capture_open_created_library',hk)).is_error;report['heterogeneousFreshApplyRecoverOpenWithoutReplay']=True
  report['passed']=sha256(old_path)==old_sha
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
