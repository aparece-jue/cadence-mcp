"""Actual MCP alternate-view creation and independent source-bound OLB lifecycle."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','native-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);a.native_root=a.native_root.resolve(strict=True);cases={case:json.loads((a.native_root/case/'spec.json').read_text()) for case in ('single','shared_dual','heterogeneous_power')};(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');expected_sha=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(root),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'scope':'declared alternate view creation; no DSN unit integration','cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   ts=(await client.list_tools()).tools;assert len(ts)==137;(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   for name,spec in cases.items():
    plan=await call('capture_plan_library_create',{'spec':spec});key={k:plan[k] for k in ('planId','planDigest')};keys.append((name,key));result=await call('capture_apply_library_create',{**key,'idempotencyKey':name});opened=await call('capture_open_created_library',key);lid=opened['libraryId'];parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'];pins=(await call('capture_library_query',{'libraryId':lid,'entity':'pin','limit':1000}))['items'];units=len(spec['devices']);view_rows=sum(sum(s['cellName']==dev['cellName'] for s in spec['symbols']) for dev in spec['devices']);physical=len({m['number'] for dev in spec['devices'] for m in dev['mapping']});assert len(parts)==view_rows and result['uniquePhysicalPadCount']==physical and result['declaredGraphVerified'];report['cases'].append({'case':name,'plan':plan,'result':result,'logicalUnitCount':units,'partViewRows':len(parts),'pinViewRows':len(pins),'physicalPads':physical});await call('capture_library_close',{'libraryId':lid})
   bad=copy.deepcopy(cases['single']);bad['symbols'][-1]['pins'][0]['name']='WRONG';assert (await client.call_tool('capture_plan_library_create',{'spec':bad})).is_error;report['incompatibleViewRefused']=True
   bad=copy.deepcopy(cases['single']);bad['expectedHomogeneous']=False;plan=await call('capture_plan_library_create',{'spec':bad});bk={k:plan[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_library_create',{**bk,'idempotencyKey':'wrong-homogeneity'});assert v.is_error;assert (await client.call_tool('capture_open_created_library',bk)).is_error;v=await client.call_tool('capture_apply_library_create',{**bk,'idempotencyKey':'wrong-homogeneity'});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed';report['wrongOracleSavedButRefusedWithoutReplay']=True
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   for name,key in keys:
    v=await client.call_tool('capture_apply_library_create',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_library_create',key)).is_error;assert not (await client.call_tool('capture_open_created_library',key)).is_error
   name,key=keys[-1];target=root/'work/isolated-jobs/capture_library_create'/('plan-'+key['planId'])/'library.olb'
   with target.open('ab') as f:f.write(b'controlled-variant-tamper-negative')
   v=await client.call_tool('capture_open_created_library',key);assert v.is_error and v.structured_content['error']['code']=='target_changed';report['freshLifecycleAndLastOutputTamperRefusal']=True
  report['passed']=sha256(root/'expected.json')==expected_sha
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
