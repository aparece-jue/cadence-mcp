import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser(description='MCP acceptance of native-checked original INI library selection; encrypted-library execution must still refuse.')
for name in ('workspace-root','cycle-root','install-root','source-ini','oracle'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cycle=a.cycle_root.resolve(strict=True);old=json.loads((cycle/'report.json').read_text());assert old['passed'];net=old['cases']['before']['netlistPlan'];ini=a.source_ini.resolve(strict=True);ini_hash=sha256(ini);library=(a.install_root/'tools/pspice/library').resolve(strict=True)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(cycle/'work'),'--read-root',str(ini.parent),'--read-root',str(library),'--timeout-seconds','60'],env=env)
report={'passed':False,'inheritedGenerationAccepted':False,'defaultNominalSolverAccepted':False,'fullV04Accepted':False,'fullP05Accepted':False}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,(name,reply.structured_content);return reply.structured_content['data']
   report['toolCount']=len((await client.list_tools()).tools)
   plan=await call('pspice_plan_profile_circuit',{'netlistPlanId':net['planId'],'netlistPlanDigest':net['planDigest'],'libraryPaths':[],
       'configurationIni':str(ini),'includeAliases':True,'inputBudget':'extended','expectedDirectives':['.AC LIN 100 0.1 200','.OPTIONS ADVCONV','.PROBE64 V(alias(*)) I(alias(*)) W(alias(*)) D(alias(*)) NOISE(alias(*))']})
   key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan;(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   result=await call('pspice_apply_profile_circuit',{**key,'idempotencyKey':'inherited-native-'+plan['planId']});report['result']=result
   assert result['nativeCheckedIniSelection'] and result['configurationMode']=='inherited_global_library_selection'
   prepared=await call('pspice_prepare_profile_circuit',key);report['prepared']=prepared;assert prepared['fileCount']==216 and prepared['inputBudget']=='extended'
   before=await call('pspice_cli_run_jobs',{'limit':100})
   refused=await client.call_tool('pspice_plan_cli_run',{'simulationId':prepared['simulationId'],'analysis':'ac','expectedSamples':json.loads(a.oracle.read_text(encoding='utf-8'))['cases']['before']})
   assert refused.is_error and refused.structured_content['error']['code']=='unsupported_embedded_reference'
   report['retainedDefaultModelRefusal']=refused.structured_content['error']['code'];assert await call('pspice_cli_run_jobs',{'limit':100})==before;report['solverNotStarted']=True
   directory=cycle/'work'/result['outputWorkspaceRelativePath'];snapshot={str(x.relative_to(directory)):sha256(x) for x in directory.rglob('*') if x.is_file()}
   origin=json.loads((directory/'configuration-origin/configuration-proof.json').read_text());assert origin['selectedLibraries']==[str(library/'nom.lib')]
   assert sha256(directory/'configuration-origin/selected.ini')==ini_hash;report['sourceIniCopiedByteForByte']=True
   durable=json.loads((directory/'plan.json').read_text());models=Path(durable['plan']['payload']['models']['directory']);manifest=json.loads((models/'input-manifest.json').read_text())
   report['frozenModelFileCount']=len(manifest['files'])-1;report['frozenModelOriginalBytes']=sum((models/f['originalRelativePath']).stat().st_size for f in manifest['files'][1:])
   assert report['frozenModelFileCount']==213 and report['frozenModelOriginalBytes']==34548882
   assert all(sha256(Path(f['sourcePath']))==f['sourceSha256'] for f in manifest['files'][1:]);report['originalLibrarySourcesUnchanged']=True
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   for name,args in [('pspice_apply_profile_circuit',{**key,'idempotencyKey':'inherited-native-'+plan['planId']}),('pspice_recover_profile_circuit',key)]:
    reply=await client.call_tool(name,args);assert not reply.is_error and reply.structured_content['data']==result
   assert {str(x.relative_to(directory)):sha256(x) for x in directory.rglob('*') if x.is_file()}==snapshot
  report.update(passed=True,inheritedGenerationAccepted=True,freshServerIdempotenceAndRecoveryNoReplay=True,allTaskFilesUnchanged=True)
 except Exception as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:
  report['sourceIniUnchanged']=sha256(ini)==ini_hash;report['passed']=report['passed'] and report['sourceIniUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
  print(json.dumps({k:report.get(k) for k in ('passed','error','inheritedGenerationAccepted','frozenModelFileCount','retainedDefaultModelRefusal','solverNotStarted','freshServerIdempotenceAndRecoveryNoReplay')}))
asyncio.run(main())
if not report['passed']:raise SystemExit(1)
