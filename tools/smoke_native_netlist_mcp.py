import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser(description='Actual MCP acceptance of fixed native Capture NET/ALS tasks.')
for key in ('workspace-root','source-root','binding','install-root','expected-netlist','expected-aliases'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source_root.resolve(strict=True)
repo=Path(__file__).resolve().parents[1];env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(source),'--gui-bridge-config',str(a.binding.resolve(strict=True)),'--timeout-seconds','30'],env=env)
report={'passed':False,'fullV04Accepted':False,'fullP05Accepted':False}
before={str(p):sha256(p) for p in source.rglob('*') if p.is_file()}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args)
    assert not reply.is_error,(name,reply.structured_content)
    return reply.structured_content['data']
   names={x.name for x in (await client.list_tools()).tools};report['toolCount']=len(names);assert {'capture_plan_pspice_netlist','capture_apply_pspice_netlist','capture_pspice_netlist_jobs','capture_cancel_pspice_netlist','capture_recover_pspice_netlist'}<=names
   instances=(await call('capture_gui_instances',{}))['instances'];pid=json.loads(a.binding.read_text())['expectedPid'];instance=next(x for x in instances if x['pid']==pid)
   gsid=(await call('capture_gui_attach',{'instanceId':instance['instanceId']}))['sessionId']
   workspace=await call('cadence_create_workspace',{'sourceDesign':str(source/'lowpassfilters.dsn')})
   sid=(await call('capture_open',{'workspaceId':workspace['workspaceId']}))['sessionId']
   args={'sessionId':sid,'guiSessionId':gsid,'sourceProject':str(source/'LowPassFilters.opj'),'sourceProfile':str(source/'LowPassFilters-PSpiceFiles/LPFilters/AC.sim')}
   cancelled=await call('capture_plan_pspice_netlist',args)
   assert (await call('capture_cancel_pspice_netlist',{k:cancelled[k] for k in ('planId','planDigest')}))['state']=='cancelled'
   report['pendingCancellationAccepted']=True
   plan=await call('capture_plan_pspice_netlist',args);key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
   (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   result=await call('capture_apply_pspice_netlist',{**key,'idempotencyKey':'mcp-native-netlist-once'});report['result']=result
   directory=root/'work'/result['outputWorkspaceRelativePath']
   assert sha256(directory/result['netlistRelativePath'])==sha256(a.expected_netlist)
   assert sha256(directory/result['aliasesRelativePath'])==sha256(a.expected_aliases)
   assert result['nativeCompletionVerified'] and result['hostContextPreserved'] and not result['modelDependenciesVerified'] and not result['solverRun']
   jobs=await call('capture_pspice_netlist_jobs',{});assert jobs['total']==2 and {x['state'] for x in jobs['jobs']}=={'cancelled','verified'}
   await call('capture_close',{'sessionId':sid});await call('capture_gui_detach',{'sessionId':gsid})
  frozen={str(p.relative_to(directory)):sha256(p) for p in directory.rglob('*') if p.is_file()}
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   for name,arguments in [('capture_apply_pspice_netlist',{**key,'idempotencyKey':'mcp-native-netlist-once'}),('capture_recover_pspice_netlist',key)]:
    reply=await client.call_tool(name,arguments);assert not reply.is_error,(name,reply.structured_content)
    assert reply.structured_content['data']==result
   assert {str(p.relative_to(directory)):sha256(p) for p in directory.rglob('*') if p.is_file()}==frozen
  assert {str(p):sha256(p) for p in source.rglob('*') if p.is_file()}==before
  report.update(passed=True,nativeArtifactsMatchOracle=True,freshServerIdempotenceAndRecoveryNoReplay=True,sourceTreeUnchanged=True)
 except Exception as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
  print(json.dumps({k:report.get(k) for k in ('passed','error','toolCount','nativeArtifactsMatchOracle','freshServerIdempotenceAndRecoveryNoReplay')}))
asyncio.run(main())
if not report['passed']:raise SystemExit(1)
