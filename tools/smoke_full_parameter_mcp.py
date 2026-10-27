import argparse,asyncio,json,os,shutil,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser(description='Full fixed LowPassFilters resistor iteration using public MCP tools for every business stage.')
for name in ('workspace-root','source-root','library','binding','install-root','oracle','baseline-netlist','modified-netlist','aliases','global-ini'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source_root.resolve(strict=True);library=a.library.resolve(strict=True);oracle_path=a.oracle.resolve(strict=True)
oracle=json.loads(oracle_path.read_text(encoding='utf-8'));oracle_hash=sha256(oracle_path);global_hash=sha256(a.global_ini)
before={str(x):sha256(x) for directory in (source,library.parent) for x in directory.rglob('*') if x.is_file()}
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(source),'--read-root',str(library.parent),'--gui-bridge-config',str(a.binding.resolve(strict=True)),'--timeout-seconds','60'],env=env)
report={'passed':False,'fullP05Accepted':False,'allBusinessStagesUseMcp':True,'cases':{}};replays=[]
def key(plan):return {k:plan[k] for k in ('planId','planDigest')}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,(name,reply.structured_content);return reply.structured_content['data']
   names={x.name for x in (await client.list_tools()).tools};report['toolCount']=len(names);assert {'capture_apply_property','capture_apply_pspice_netlist','pspice_apply_profile_circuit','pspice_prepare_profile_circuit','pspice_apply_cli_run','pspice_dat_samples'}<=names
   instance=next(x for x in (await call('capture_gui_instances',{}))['instances'] if x['pid']==json.loads(a.binding.read_text())['expectedPid'])
   gsid=(await call('capture_gui_attach',{'instanceId':instance['instanceId']}))['sessionId']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source/'lowpassfilters.dsn')});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   parts=(await call('capture_query',{'sessionId':sid,'entity':'part','reference':'R1','scope':{'kind':'design'}}))['items'];assert len(parts)==1
   props=await call('capture_get_part_properties',{'sessionId':sid,'partId':parts[0]['objectId']});assert next(x['value'] for x in props['items'] if x['name']=='Value')=='500'
   property_plan=await call('capture_plan_property',{'sessionId':sid,'partId':parts[0]['objectId'],'propertyName':'Value','value':'1k'})
   property_result=await call('capture_apply_property',{**key(property_plan),'idempotencyKey':'full-cycle-resistor-once'})
   assert property_result['independentReopenVerified'] and property_result['definitionBaselinePreserved'] and property_result['observedValue']=='1k'
   report['propertyPlan']=property_plan;report['propertyResult']=property_result;replays.append(('capture_apply_property',{**key(property_plan),'idempotencyKey':'full-cycle-resistor-once'},property_result))
   after_sid=(await call('capture_open_edit_result',{**key(property_plan),'kind':'property'}))['sessionId']
   prior_dat=None
   for label,definition in [('before',sid),('after',after_sid)]:
    entry={};report['cases'][label]=entry
    net=await call('capture_plan_pspice_netlist',{'sessionId':definition,'guiSessionId':gsid,'sourceProject':str(source/'LowPassFilters.opj'),'sourceProfile':str(source/'LowPassFilters-PSpiceFiles/LPFilters/AC.sim')});entry['netlistPlan']=net
    net_result=await call('capture_apply_pspice_netlist',{**key(net),'idempotencyKey':'full-cycle-net-'+label});entry['netlistResult']=net_result
    nd=root/'work'/net_result['outputWorkspaceRelativePath'];assert sha256(nd/net_result['netlistRelativePath'])==sha256(a.baseline_netlist if label=='before' else a.modified_netlist);assert sha256(nd/net_result['aliasesRelativePath'])==sha256(a.aliases)
    profile=await call('pspice_plan_profile_circuit',{'netlistPlanId':net['planId'],'netlistPlanDigest':net['planDigest'],'libraryPaths':[str(library)],'includeAliases':True,'expectedDirectives':['.AC LIN 100 0.1 200','.OPTIONS ADVCONV','.PROBE64 V(alias(*)) I(alias(*)) W(alias(*)) D(alias(*)) NOISE(alias(*))']});entry['profilePlan']=profile
    generated=await call('pspice_apply_profile_circuit',{**key(profile),'idempotencyKey':'full-cycle-profile-'+label});entry['profileResult']=generated
    prepared=await call('pspice_prepare_profile_circuit',key(profile));assert prepared['fileCount']==5;entry['prepared']=prepared
    assert prepared['sourceDesignRevision']==net_result['sourceDesignRevision']
    solve_args={'simulationId':prepared['simulationId'],'analysis':'ac','expectedSamples':oracle['cases'][label]}
    if label=='after':
     stale=await call('pspice_plan_cli_run',solve_args);sd=root/'work/isolated-jobs/pspice_cli_run'/('plan-'+stale['planId']);shutil.copyfile(prior_dat,sd/'input.dat');stale_hash=sha256(sd/'input.dat')
     rejected=await client.call_tool('pspice_apply_cli_run',{**key(stale),'idempotencyKey':'full-cycle-stale-dat'})
     assert rejected.is_error and rejected.structured_content['error']['code']=='preexisting_cli_output'
     row=json.loads((sd/'plan.json').read_text());assert not row.get('workerPid') and not (sd/'input.cir').exists() and sha256(sd/'input.dat')==stale_hash;report['oldDatRejectedBeforeWorker']=True
    cli=await call('pspice_plan_cli_run',solve_args);entry['cliPlan']=cli
    solved=await call('pspice_apply_cli_run',{**key(cli),'idempotencyKey':'full-cycle-cli-'+label});assert solved['numericalAcceptanceVerified'];entry['cliResult']=solved
    dat=await call('pspice_open_run_dat',{**key(cli),'backend':'cli'});assert dat['jobAssociationVerified'];entry['firstSample']=(await call('pspice_dat_samples',{'datId':dat['datId'],'block':0,'traceName':'V(N00509)','offset':0,'limit':1}))['items'][0];await call('pspice_dat_close',{'datId':dat['datId']})
    prior_dat=root/'work/isolated-jobs/pspice_cli_run'/('plan-'+cli['planId'])/'input.dat'
    replays.extend([('capture_apply_pspice_netlist',{**key(net),'idempotencyKey':'full-cycle-net-'+label},net_result),('pspice_apply_profile_circuit',{**key(profile),'idempotencyKey':'full-cycle-profile-'+label},generated),('pspice_apply_cli_run',{**key(cli),'idempotencyKey':'full-cycle-cli-'+label},solved)])
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   assert report['cases']['before']['firstSample']['real']-report['cases']['after']['firstSample']['real']>.16
   assert report['cases']['before']['netlistResult']['sourceDesignRevision']!=report['cases']['after']['netlistResult']['sourceDesignRevision'];report['voltageChangeAccepted']=True
   for definition in (sid,after_sid):await call('capture_close',{'sessionId':definition})
   await call('capture_gui_detach',{'sessionId':gsid})
  frozen={str(x):sha256(x) for x in (root/'work/isolated-jobs').rglob('*') if x.is_file()}
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   for name,args,expected in replays:
    reply=await client.call_tool(name,args);assert not reply.is_error and reply.structured_content['data']==expected,(name,reply.structured_content)
   assert {str(x):sha256(x) for x in (root/'work/isolated-jobs').rglob('*') if x.is_file()}==frozen
  report.update(passed=True,freshServerAllSevenBusinessWritesIdempotent=True,allPriorTaskFilesUnchanged=True)
 except Exception as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:
  report['sourceLibraryOracleAndGlobalIniUnchanged']=all(sha256(Path(path))==digest for path,digest in before.items()) and sha256(oracle_path)==oracle_hash and sha256(a.global_ini)==global_hash
  report['passed']=report['passed'] and report['sourceLibraryOracleAndGlobalIniUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
  print(json.dumps({k:report.get(k) for k in ('passed','error','allBusinessStagesUseMcp','oldDatRejectedBeforeWorker','voltageChangeAccepted','freshServerAllSevenBusinessWritesIdempotent','sourceLibraryOracleAndGlobalIniUnchanged')}))
asyncio.run(main())
if not report['passed']:raise SystemExit(1)
