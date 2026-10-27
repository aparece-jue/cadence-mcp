import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser(description='Actual MCP native profile/CIR tasks, artifact preparation and CLI numeric acceptance; consumes a verified NET/ALS job.')
for name in ('workspace-root','netlist-root','library','install-root','oracle','global-ini'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--input-budget',choices=('standard','extended'),default='standard')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);old=a.netlist_root.resolve(strict=True);net=json.loads((old/'report.json').read_text());assert net['passed']
source=a.library.resolve(strict=True);before={str(x):sha256(x) for x in source.parent.rglob('*') if x.is_file()};global_hash=sha256(a.global_ini)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(old/'work'),'--read-root',str(source.parent),'--timeout-seconds','30'],env=env)
report={'passed':False,'fullV04Accepted':False,'fullP05Accepted':False}
args={'netlistPlanId':net['plan']['planId'],'netlistPlanDigest':net['plan']['planDigest'],'libraryPaths':[str(source)],'includeAliases':True,'inputBudget':a.input_budget,
      'expectedDirectives':['.AC LIN 100 0.1 200','.OPTIONS ADVCONV','.PROBE64 V(alias(*)) I(alias(*)) W(alias(*)) D(alias(*)) NOISE(alias(*))']}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,arguments):
    reply=await client.call_tool(name,arguments);assert not reply.is_error,(name,reply.structured_content);return reply.structured_content['data']
   names={x.name for x in (await client.list_tools()).tools};report['toolCount']=len(names);assert {'pspice_plan_profile_circuit','pspice_apply_profile_circuit','pspice_profile_circuit_jobs','pspice_cancel_profile_circuit','pspice_recover_profile_circuit','pspice_prepare_profile_circuit'}<=names
   cancelled=await call('pspice_plan_profile_circuit',args);assert (await call('pspice_cancel_profile_circuit',{k:cancelled[k] for k in ('planId','planDigest')}))['state']=='cancelled';report['pendingCancelAccepted']=True
   plan=await call('pspice_plan_profile_circuit',args);key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
   (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   result=await call('pspice_apply_profile_circuit',{**key,'idempotencyKey':'mcp-profile-'+key['planId']});report['result']=result
   assert result['nativeCompletionVerified'] and result['explicitConfigurationVerified'] and not result['solverRun']
   opened=await call('pspice_prepare_profile_circuit',key);assert opened['inputBudget']==a.input_budget and opened['fileCount']==5 and opened['producedByProfilePlan']==key['planId'];report['prepared']=opened
   samples=json.loads(a.oracle.read_text(encoding='utf-8'))['cases']['after']
   cli=await call('pspice_plan_cli_run',{'simulationId':opened['simulationId'],'analysis':'ac','expectedSamples':samples});cli_key={k:cli[k] for k in ('planId','planDigest')}
   solved=await call('pspice_apply_cli_run',{**cli_key,'idempotencyKey':'mcp-profile-nested-cli-'+cli_key['planId']});assert solved['numericalAcceptanceVerified'];report['solver']=solved
   jobs=await call('pspice_profile_circuit_jobs',{});assert any(x['planId']==key['planId'] and x['state']=='verified' for x in jobs['jobs'])
   directory=old/'work'/result['outputWorkspaceRelativePath'];frozen={str(x.relative_to(directory)):sha256(x) for x in directory.rglob('*') if x.is_file()}
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   for name,arguments in [('pspice_apply_profile_circuit',{**key,'idempotencyKey':'mcp-profile-'+key['planId']}),('pspice_recover_profile_circuit',key)]:
    reply=await client.call_tool(name,arguments);assert not reply.is_error,reply.structured_content;assert reply.structured_content['data']==result
   assert {str(x.relative_to(directory)):sha256(x) for x in directory.rglob('*') if x.is_file()}==frozen
   reopened=await client.call_tool('pspice_prepare_profile_circuit',key);assert not reopened.is_error and reopened.structured_content['data']['fileCount']==5
  report.update(passed=True,nestedModelMcpCliNumericsAccepted=True,freshServerIdempotenceAndRecovery=True,freshServerArtifactPreparation=True)
 except Exception as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:
  report['modelsAndGlobalIniUnchanged']=all(sha256(Path(path))==digest for path,digest in before.items()) and sha256(a.global_ini)==global_hash
  report['passed']=report['passed'] and report['modelsAndGlobalIniUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
  print(json.dumps({k:report.get(k) for k in ('passed','error','toolCount','nestedModelMcpCliNumericsAccepted','freshServerIdempotenceAndRecovery','modelsAndGlobalIniUnchanged')}))
asyncio.run(main())
if not report['passed']:raise SystemExit(1)
