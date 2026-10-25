"""Fresh actual stdio native run and task-bound OUT read acceptance."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=root/'source';source.mkdir()
for name in ('dc','ac','transient'):(source/(name+'.cir')).write_bytes((a.fixture_root/name/'input.cir').read_bytes())
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[],'sourceBefore':{f.name:sha256(f) for f in source.iterdir()}};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==111;schemas={t.name:t.output_schema for t in tools}
   for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,r.content
    Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
   for name in ('dc','transient','ac'):
    prep=await call('pspice_prepare',{'sourceCircuit':str(source/(name+'.cir'))})
    plan=await call('pspice_plan_run',{'simulationId':prep['simulationId'],'analysis':name});key={k:plan[k] for k in ('planId','planDigest')}
    if name=='ac':
     r=await client.call_tool('pspice_apply_run',{**key,'idempotencyKey':name});assert r.is_error and r.structured_content['error']['code']=='pspice_output_error'
     r=await client.call_tool('pspice_inspect_run_output',key);assert r.is_error and r.structured_content['error']['code']=='output_unverified'
     report['failedNativeMeasureRunRejected']=True;continue
    result=await call('pspice_apply_run',{**key,'idempotencyKey':name})
    out=await call('pspice_inspect_run_output',key);assert out['solverSuccessVerified'] and out['jobAssociationVerified'] and out['producedByPlan']==key['planId']
    assert not out['numericalAcceptanceVerified'] and 'measurements' in out['notChecked'] and out['designPassed'] is None
    assert (await client.call_tool('pspice_inspect_run_output',{**key,'planDigest':'wrong'})).is_error
    assert (await client.call_tool('pspice_inspect_run_output',{**key,'eval':'unsafe'})).is_error
    report['cases'].append({'analysis':name,'plan':plan,'run':result,'out':out});keys.append((name,key))
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   for name,key in keys:
    r=await client.call_tool('pspice_inspect_run_output',key);assert not r.is_error
    d=root/'work/isolated-jobs/pspice_engine_run'/('plan-'+key['planId']);path=d/'result.out';before=sha256(path)
    r=await client.call_tool('pspice_apply_run',{**key,'idempotencyKey':name});assert not r.is_error and not r.structured_content['data']['mutationReplayed'];assert sha256(path)==before
   # Only this new owned DC artifact is intentionally invalidated.
   name,key=keys[0];d=root/'work/isolated-jobs/pspice_engine_run'/('plan-'+key['planId'])
   with (d/'result.dat').open('ab') as f:f.write(b'controlled-hash-negative')
   r=await client.call_tool('pspice_inspect_run_output',key);assert r.is_error and r.structured_content['error']['code']=='target_changed'
   report['freshServerNoReplayAndDatTamperRejected']=True
  report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourceAfter']={f.name:sha256(f) for f in source.iterdir()};report['passed'] &= report['sourceBefore']==report['sourceAfter']
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'cases':len(report['cases'])}))
asyncio.run(main())
