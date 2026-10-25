import argparse,asyncio,copy,json,os,shutil,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','library-root','oracle-path'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--operation',choices=('update','delete'),default='update')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.library_root/'library.olb';before=sha256(source);copy_path=root/'library.olb';shutil.copyfile(source,copy_path)
cfg=Config(a.install_root,root/'work',(root,),60)
report={'passed':False}
replacement={'kind':'polygon','points':[[-10,8],[-3,-9],[4,-10],[10,8]],'style':3,'width':1,'fill':2,'hatch':4}
expected=json.loads(a.oracle_path.read_text(encoding='utf-8'));normal=next(k for k in expected if k.endswith('.Normal'))
index=next(i for i,v in enumerate(expected[normal]) if v[0]=='polygon')
if a.operation=='update':expected[normal][index]=['polygon',[[-10,8],[-3,-9],[4,-10],[10,8]],3,1,2,4]
else:expected[normal].pop(index)
(root/'expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
async def main():
 try:
  process=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_second_package.tcl'),str(cfg.install_root),str(copy_path),str(a.library_root/'spec.json'),str(root/'fixture-receipt.json')],root,process_env(cfg),60)
  report['fixtureProcess']=process;assert process['returnCode']==0 and process['remainingOwnedProcesses']==0;fixture_hash=sha256(copy_path)
  env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
  params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(cfg.workspace_root),'--read-root',str(root),'--timeout-seconds','60'],env=env)
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.content);return r.structured_content['data']
   lid=(await call('capture_library_open',{'sourceLibrary':str(copy_path)}))['libraryId']
   packages=(await call('capture_library_query',{'libraryId':lid,'entity':'package','limit':1000}))['items'];assert len(packages)==2
   parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'];assert len(parts)==8
   part=next(p for p in parts if p['name']==normal)
   items=(await call('capture_query_library_vectors',{'libraryId':lid,'partId':part['objectId'],'limit':1000}))['items']
   target=next(v for v in items if v['kind']=='polygon')
   plan=await call('capture_plan_library_vector_edit',{'libraryId':lid,'partId':part['objectId'],'vectorId':target['objectId'],'operation':a.operation,'replacement':replacement if a.operation=='update' else None});report['plan']=plan
   assert len(plan['preview']['affectedScopes'])==4
   key={k:plan[k] for k in ('planId','planDigest')};report['result']=await call('capture_apply_library_vector_edit',{**key,'idempotencyKey':'cross-package'})
   opened=await call('capture_open_edited_library',{**key,'kind':'vector'});report['opened']=opened
   saved_packages=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'package','limit':1000}))['items']
   assert sorted((p['name'],p['footprint']) for p in packages)==sorted((p['name'],p['footprint']) for p in saved_packages)
   saved_parts=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'part','limit':1000}))['items'];assert len(saved_parts)==8
   for p in saved_parts:
    rows=(await call('capture_query_library_vectors',{'libraryId':opened['libraryId'],'partId':p['objectId'],'limit':1000}))['items']
    actual=[v['descriptor'][:-1] if v['kind']=='text' else v['descriptor'] for v in rows];assert actual==expected[p['name']]
   report['allEightViewsVerified']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   r=await fresh.call_tool('capture_apply_library_vector_edit',{**key,'idempotencyKey':'cross-package'});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
   assert not (await fresh.call_tool('capture_recover_library_vector_edit',key)).is_error
   assert not (await fresh.call_tool('capture_open_edited_library',{**key,'kind':'vector'})).is_error
  report['sourceAndOracleUnchanged']=sha256(source)==before and sha256(copy_path)==fixture_hash and sha256(root/'expected.json')==oracle
  report['passed']=report['sourceAndOracleUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
