"""Separate declared-circuit electrical oracles using independently reopened Capture property values.

This is explicit manual parameter transfer, never Capture-generated netlisting or P05 acceptance.
"""
import argparse,asyncio,json,math,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture_edit import read_design_properties
p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','property-evidence'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
prior=json.loads((a.property_evidence/'report.json').read_text(encoding='utf-8'));assert prior['passed']
config=Config(a.install_root,root/'oracle',(root,),60)
expected={'baseline':2.5,'tc1':5/(2+0.001*100),'tc2':5/(2-2e-6*10000),'absoluteTolerance':1e-6,
 'model_a':1e-12*math.expm1(0.3/(8.617333262145e-5*300.15)),'model_b':1e-9*math.expm1(0.3/(8.617333262145e-5*300.15)),
 'modelRelativeTolerance':0.001,'transferScope':'explicit_manual_parameters_not_native_capture_netlist'}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle_hash=sha256(root/'expected.json')
cases={};transfers=[]
for name,index,field in [('tc1',1,'TC1'),('tc2',2,'TC2')]:
 row=prior['cases'][index];dsn=a.property_evidence/'work'/row['result']['outputWorkspaceRelativePath']/'design.dsn'
 assert sha256(dsn)==row['outputHash']
 g=read_design_properties(config,dsn,root);part=next(r for r in g if r['scope']==['ROOT','SAME_PAGE','R1']);v=next(p['value'] for p in part['properties'] if p['name']==field)
 assert v==row['case']['value'];cases[name]=(v if field=='TC1' else '0',v if field=='TC2' else '0')
 transfers.append({'case':name,'sourceDsn':str(dsn),'sourceDsnSha256':sha256(dsn),'scope':part['scope'],'property':field,'observedValue':v,'nativeCaptureNetlist':False})
cases['baseline']=('0','0')
for name,(tc1,tc2) in cases.items():
 (sources/(name+'.cir')).write_text(f'Original temperature divider\nVIN 1 0 DC 5\nR1 1 2 1k TC={tc1},{tc2}\nR2 2 0 1k\n.OPTIONS TNOM=27\n.TEMP 127\n.DC VIN 5 5 1\n.PRINT DC V(2)\n.PROBE V(2)\n.END\n',encoding='ascii')
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(sources),'--read-root',str(a.property_evidence.parent/'model-property-fixture-20261025'),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'transfers':transfers,'nativeCaptureNetlist':False,'captureElectricalBehaviorCertified':False}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content);return r.structured_content['data']
   fixture=a.property_evidence.parent/'model-property-fixture-20261025/source.dsn'
   ws=await call('cadence_create_workspace',{'sourceDesign':str(fixture)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];ss=(await call('capture_query',{'sessionId':sid,'entity':'schematic','scope':{'kind':'design'},'limit':1000}))['items'];names={s['objectId']:s['name'] for s in ss};target=next(p for p in parts if names[p['schematicId']]=='ROOT' and p['reference']=='D1')
   for name,model in [('model_a','MCP_D_A'),('model_b','MCP_D_B')]:
    plan=await call('capture_plan_property',{'sessionId':sid,'partId':target['objectId'],'propertyName':'Implementation','value':model});key={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_property',{**key,'idempotencyKey':name})
    dsn=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn';g=read_design_properties(config,dsn,root);row=next(r for r in g if r['scope']==['ROOT','SAME_PAGE','D1']);observed=next(p['value'] for p in row['properties'] if p['name']=='Implementation');assert observed==model
    report['transfers'].append({'case':name,'sourceDsn':str(dsn),'sourceDsnSha256':sha256(dsn),'scope':row['scope'],'property':'Implementation','observedValue':observed,'nativeCaptureNetlist':False,'plan':plan,'result':result})
    (sources/(name+'.cir')).write_text(f'Original declared diode model circuit\nVIN 1 0 DC 0.3\nD1 1 0 {observed}\n.MODEL MCP_D_A D(IS=1e-12 N=1 RS=0 CJO=0)\n.MODEL MCP_D_B D(IS=1e-9 N=1 RS=0 CJO=0)\n.OPTIONS TNOM=27 GMIN=1e-15\n.TEMP 27\n.DC VIN 0.3 0.3 1\n.PRINT DC I(D1)\n.PROBE I(D1)\n.END\n',encoding='ascii')
   hashes={f.name:sha256(f) for f in sources.iterdir()};report['inputHashesBefore']=hashes
   for name in ('baseline','tc1','tc2','model_a','model_b'):
    trace='I(D1)' if name.startswith('model') else 'V(2)';prepared=await call('pspice_prepare',{'sourceCircuit':str(sources/(name+'.cir'))})
    sample={'block':0,'row':0,'traceName':trace,'real':expected[name],'absoluteTolerance':1e-11 if name.startswith('model') else 1e-6,'relativeTolerance':0.001 if name.startswith('model') else 0.0}
    plan=await call('pspice_plan_cli_run',{'simulationId':prepared['simulationId'],'analysis':'dc','expectedSamples':[sample]});key={k:plan[k] for k in ('planId','planDigest')};result=await call('pspice_apply_cli_run',{**key,'idempotencyKey':name})
    assert result['numericalAcceptanceVerified'];report['cases'].append({'name':name,'sample':sample,'plan':plan,'result':result});print(name,'declared numerical oracle passed',flush=True)
   report['inputHashesAfter']={f.name:sha256(f) for f in sources.iterdir()};assert hashes==report['inputHashesAfter'];assert sha256(root/'expected.json')==oracle_hash
  report['passed']=True
 except BaseException as error:report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
