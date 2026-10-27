import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser()
for name in ('workspace-root','fixture-root','install-root','old-engine-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);fixture=a.fixture_root.resolve(strict=True);old=a.old_engine_root.resolve(strict=True)
old_hashes={str(x):sha256(x) for x in (old/'work/isolated-jobs').rglob('*') if x.is_file()}
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(fixture)],env=env)
async def main():
 async with Client(params,mode='legacy',read_timeout_seconds=60) as client:
  async def call(name,args):
   reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content;return reply.structured_content['data']
  prepared=await call('pspice_prepare',{'sourceCircuit':str(fixture/'circuit.cir')})
  args={'simulationId':prepared['simulationId'],'analysis':'ac','expectedSamples':json.loads((fixture/'expected.json').read_text())['expectedSamples']}
  before=await call('pspice_run_jobs',{})
  rejected=await client.call_tool('pspice_plan_run',args);assert rejected.is_error and rejected.structured_content['error']['code']=='parameter_step_requires_cli'
  assert await call('pspice_run_jobs',{})==before and before['total']==0
  plan=await call('pspice_plan_cli_run',args);d=root/'work/isolated-jobs/pspice_cli_run'/('plan-'+plan['planId']);assert {x.name for x in d.iterdir()}=={'plan.json'}
  row=json.loads((d/'plan.json').read_text());assert row['state']=='planned' and not row.get('workerPid')
 assert {str(x):sha256(x) for x in (old/'work/isolated-jobs').rglob('*') if x.is_file()}==old_hashes
 report={'passed':True,'engineRefusedBeforeTaskCreation':True,'cliPlanAcceptedNoWorkerStarted':True,'oldEngineFailureBytesUnchanged':True,'cliPlan':plan}
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='cliPlan'}))
asyncio.run(main())
