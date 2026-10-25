"""Real current, trigger-delay, unknown-expression units and immutable old-job projection."""
import argparse,asyncio,json,math,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];root=a.workspace_root.resolve();root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir();old=repo/'.local/native-measure-20261023'
text=(old/'dc/input.cir').read_text(encoding='ascii').replace('.END','.MEASURE DC supply_avg AVG I(V1)\n.MEASURE DC ratio PARAM {1+2}\n.END');(sources/'dc.cir').write_text(text,encoding='ascii')
text=(old/'transient/input.cir').read_text(encoding='ascii').replace('.END','.MEASURE TRAN delay TRIG V(2) VAL=0.2 RISE=1 TARG V(2) VAL=0.8 RISE=1\n.END');(sources/'transient.cir').write_text(text,encoding='ascii')
before={p.name:sha256(p) for p in sources.iterdir()};expected={'supply_avg':-.00125,'ratio':3.,'delay':.001*math.log(4)};(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
def params(work,read):return StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(work),'--read-root',str(read),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'legacy':[]}
async def main():
 try:
  async with Client(params(root/'work',sources),mode='legacy',read_timeout_seconds=240) as client:
   async def call(name,args):
    response=await client.call_tool(name,args);assert not response.is_error,(name,response.structured_content);return response.structured_content['data']
   for analysis,names in [('dc',('supply_avg','ratio')),('transient',('delay',))]:
    row={'analysis':analysis,'passed':False};report['cases'].append(row)
    try:
     prepared=await call('pspice_prepare',{'sourceCircuit':str(sources/(analysis+'.cir'))});checks=[{'name':name,'field':'value','expected':expected[name],'absoluteTolerance':1e-8 if name!='delay' else 1e-5,'relativeTolerance':0.0} for name in names];plan=await call('pspice_plan_measure_run',{'simulationId':prepared['simulationId'],'analysis':analysis,'expectedMeasurements':checks});row['plan']=plan;key={k:plan[k] for k in ('planId','planDigest')};row['result']=await call('pspice_apply_measure_run',{**key,'idempotencyKey':analysis});inspection=await call('pspice_inspect_run_measurements',key);row['inspection']=inspection;rows={m['name']:m for m in inspection['nativeMeasurements']}
     if analysis=='dc':assert rows['supply_avg']['fieldUnits']['value']['unit']=='A' and rows['supply_avg']['fieldUnits']['from']['unit']=='V' and rows['ratio']['fieldUnits']['value']['unit'] is None
     else:assert rows['delay']['fieldUnits']['value']['unit']=='s' and all(unit['unit']=='s' for unit in rows['delay']['fieldUnits'].values())
     row['passed']=True
    except BaseException as e:row.update(error=str(e),traceback=traceback.format_exc())
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'analysis':analysis,'passed':row['passed'],'error':row.get('error')}),flush=True)
  legacy=repo/'.local/native-measure-mcp-v2-20261025';old_report=json.loads((legacy/'report.json').read_text(encoding='utf-8'))
  paths=[legacy/'report.json']
  for case in old_report['cases']:paths.append(legacy/'work/isolated-jobs/pspice_measure_run'/('plan-'+case['plan']['planId'])/'run-artifacts.json')
  hashes={str(path):sha256(path) for path in paths}
  async with Client(params(legacy/'work',legacy/'sources'),mode='legacy',read_timeout_seconds=240) as fresh:
   for case in old_report['cases']:
    key={k:case['plan'][k] for k in ('planId','planDigest')};response=await fresh.call_tool('pspice_inspect_run_measurements',key);assert not response.is_error,response.structured_content;value=response.structured_content['data'];assert value['measurementUnits']['unknownUnitFieldCount']==0;assert [{k:v for k,v in m.items() if k!='fieldUnits'} for m in value['nativeMeasurements']]==case['inspection']['nativeMeasurements'];report['legacy'].append({'analysis':case['case'],'units':value['measurementUnits'],'numericAndRawEvidenceUnchanged':True})
  assert hashes=={str(path):sha256(path) for path in paths};report['legacyOriginalHashesBefore']=hashes;report['legacyOriginalHashesAfter']={str(path):sha256(path) for path in paths};report['sourceHashesBefore']=before;report['sourceHashesAfter']={p.name:sha256(p) for p in sources.iterdir()};assert before==report['sourceHashesAfter'] and sha256(root/'expected.json')==oracle;report['passed']=all(row['passed'] for row in report['cases']) and len(report['legacy'])==3
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
