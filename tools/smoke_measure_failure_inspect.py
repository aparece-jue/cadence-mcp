"""Inspect prior native-measure failures without restarting any analysis."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];old=repo/'.local/native-measure-mcp-v2-20261025';root=repo/'.local/measure-failure-inspect-20261025';root.mkdir(exist_ok=False)
records=[]
for path in (old/'work/isolated-jobs/pspice_measure_run').glob('plan-*/plan.json'):
 row=json.loads(path.read_text(encoding='utf-8'))
 if row['state']=='failed':records.append((path,row,sha256(path)))
assert len(records)==2
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(old/'work'),'--read-root',str(old/'sources'),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[]}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   assert len((await client.list_tools()).tools)==167
   for path,row,before in records:
    args={'planId':row['plan']['planId'],'planDigest':row['digest'],'kind':'measurement'}
    r=await client.call_tool('pspice_inspect_run_failure',args);assert not r.is_error,r.structured_content
    value=r.structured_content['data'];assert value['workerStoppedVerified'] and value['inputClosureMatchesPlan'] and not value['solverSuccessVerified'] and sha256(path)==before
    if row['error']['code']=='pspice_output_error':assert value['output']['hasErrorDiagnostics']
    else:assert row['error']['code']=='measurement_expectation_mismatch' and not value['output']['hasErrorDiagnostics']
    report['cases'].append(value)
  report['passed']=True
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error')}))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
