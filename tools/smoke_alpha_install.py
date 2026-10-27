"""Verify the installed wheel in a clean environment, with no source PYTHONPATH."""
import argparse,asyncio,json,os,shutil,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
import cadence_mcp
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','capture-source','circuit-source','contract'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--backend',choices=['cli','engine'],default='cli')
p.add_argument('--expected-version',default='0.1.0a1');p.add_argument('--expected-tool-count',type=int,default=193)
p.add_argument('--server-module',default='cadence_mcp.server')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);inputs=root/'inputs';inputs.mkdir();dsn=inputs/'sample.dsn';cir=inputs/'divider.cir';shutil.copy2(a.capture_source,dsn);shutil.copy2(a.circuit_source,cir);before={str(p):sha256(p) for p in (a.capture_source,a.circuit_source,dsn,cir)};env=os.environ.copy();env.pop('PYTHONPATH',None);params=StdioServerParameters(command=sys.executable,args=['-m',a.server_module,'--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'workspaces'),'--read-root',str(inputs),'--timeout-seconds','60'],env=env);report={'passed':False,'version':cadence_mcp.__version__,'importPath':cadence_mcp.__file__,'checks':{}}
async def main():
 try:
  assert report['version']==a.expected_version and 'site-packages' in report['importPath']
  async with Client(params,mode='legacy',read_timeout_seconds=240) as c:
   tools=(await c.list_tools()).tools;actual=[t.model_dump(mode='json',by_alias=True) for t in tools];expected=json.loads(a.contract.read_text(encoding='utf-8'));assert sorted(actual,key=lambda t:t['name'])==sorted(expected,key=lambda t:t['name']);report['toolCount']=len(tools);assert len(tools)==a.expected_tool_count;report['checks']['installed_tools_match_release_contract']=True;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    response=await c.call_tool(name,args);assert not response.is_error,(name,response.structured_content);Draft202012Validator(schemas[name]).validate(response.structured_content);return response.structured_content['data']
   report['environment']=await call('cadence_get_environment',{'probeLevel':'runtime'});report['checks']['installed_native_environment_probe']=True
   opened=await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(dsn)}))['workspaceId']});sid=opened['sessionId'];parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];assert len(parts)==opened['counts']['part'] and parts;props=await call('capture_get_part_properties',{'sessionId':sid,'partId':parts[0]['objectId']});assert props['items'];report['captureCounts']=opened['counts'];await call('capture_close',{'sessionId':sid});report['checks']['installed_native_capture_copy_query_and_properties']=True
   prepared=await call('pspice_prepare',{'sourceCircuit':str(cir)});sample={'block':0,'row':5,'traceName':'V(OUT)','real':2.5,'absoluteTolerance':1e-6,'relativeTolerance':0.0}
   plan=await call('pspice_plan_cli_run' if a.backend=='cli' else 'pspice_plan_run',{'simulationId':prepared['simulationId'],'analysis':'dc','expectedSamples':[sample]});key={k:plan[k] for k in ('planId','planDigest')};result=await call('pspice_apply_cli_run' if a.backend=='cli' else 'pspice_apply_run',{**key,'idempotencyKey':'installed-alpha-divider'});assert result['numericalAcceptanceVerified'] and result['jobAssociationVerified'];report['pspice']={'plan':plan,'result':result};report['checks']['installed_'+a.backend+'_fresh_dc_2_5V']=True
   dat=await call('pspice_open_run_dat',{**key,'backend':a.backend});values=await call('pspice_dat_samples',{'datId':dat['datId'],'block':0,'traceName':'V(OUT)','offset':5,'limit':1});assert abs(values['items'][0]['real']-2.5)<=1e-6;report['dcSample']=values['items'][0];await call('pspice_dat_close',{'datId':dat['datId']});report['checks']['installed_native_dat_read']=True
  report['checks']['sources_and_copies_unchanged']=all(sha256(Path(p))==h for p,h in before.items());report['passed']=all(report['checks'].values())
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceHashes']=before;(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')},ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
