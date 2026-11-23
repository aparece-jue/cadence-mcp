"""Accept the original folded and ordinary LIB fixtures through actual MCP engine tasks."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

async def accept(a,root,report):
 for index,fixture in enumerate(a.fixture_root):
  oracle=fixture/'expected.json';expected=json.loads(oracle.read_text());inputs=fixture/'inputs';source=inputs/'divider.cir';before={p:sha256(p) for p in [oracle,*inputs.iterdir()] if p.is_file()};work=root/str(index)/'work'
  params=StdioServerParameters(command=sys.executable,args=['-B','-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(work),'--read-root',str(inputs),'--timeout-seconds','60'],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
  case={'fixture':fixture.name,'passed':False};report['cases'].append(case)
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    result=await client.call_tool(name,args);assert not result.is_error,result.structured_content;return result.structured_content['data']
   prepared=await call('pspice_prepare',{'sourceCircuit':str(source),'inputEncoding':'preserve-bytes'});assert prepared['fileCount']==expected['files']
   sample=expected['sample'];plan=await call('pspice_plan_run',{'simulationId':prepared['simulationId'],'analysis':'dc','expectedSamples':[{'block':0,'row':sample['row'],'traceName':sample['trace'],'real':sample['real'],'absoluteTolerance':sample['absoluteTolerance'],'relativeTolerance':0.0}]});key={k:plan[k] for k in ('planId','planDigest')};result=await call('pspice_apply_run',{**key,'idempotencyKey':'original-nested-lib'})
   assert result['numericalAcceptanceVerified'] and result['jobAssociationVerified'];case.update(plan=key,result=result)
   await call('pspice_open_run_dat',key)
  outputs=list(work.glob('isolated-jobs/pspice_engine_run/plan-*'));job,=outputs;hashes={p:sha256(p) for p in job.rglob('*') if p.is_file() and p.suffix.lower() in ('.cir','.lib','.out','.dat')}
  for p in job.rglob('*'):
   if p.is_file() and p.suffix.lower() in ('.cir','.lib'):
    for line in p.read_bytes().splitlines():
     if line.lstrip().upper().startswith(b'.LIB '):assert line.startswith(b'.LIB "deps/file-'),line
  async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
   for name,args in [('pspice_apply_run',{**key,'idempotencyKey':'original-nested-lib'}),('pspice_recover_run',key)]:
    result=await fresh.call_tool(name,args);assert not result.is_error,result.structured_content
    if name=='pspice_apply_run':assert not result.structured_content['data']['mutationReplayed']
  assert all(sha256(p)==h for p,h in hashes.items());assert all(sha256(p)==h for p,h in before.items());case.update(passed=True,originalInputsUnchanged=True,freshRecoveryNoReplay=True,terminalNativeHashesUnchanged=True,originalNumericalOracle=sample,inputSha256={str(p.relative_to(fixture)):h for p,h in before.items()});print(json.dumps({'fixture':fixture.name,'passed':True}),flush=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install-root',type=Path,required=True);p.add_argument('--fixture-root',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.fixture_root=[p.resolve() for p in a.fixture_root];a.install_root=a.install_root.resolve();root=a.output.resolve();root.mkdir(exist_ok=False);report={'passed':False,'fullP02Accepted':False,'cases':[]}
 try:asyncio.run(accept(a,root,report));report['passed']=True
 finally:(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
