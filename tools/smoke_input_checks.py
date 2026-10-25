"""Actual MCP native setup validation and nested parameter/model execution evidence."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];root=repo/'.local/input-checks-mcp-v2-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir();(sources/'models').mkdir()
(sources/'params.inc').write_text('.PARAM RBASE=1k\n',encoding='ascii')
(sources/'models/one.inc').write_text('.INCLUDE "../params.inc"\n.PARAM SCALE=2\n',encoding='ascii')
(sources/'models/diode.lib').write_text('.MODEL DMODEL D(IS=1n)\n',encoding='ascii')
(sources/'nested.cir').write_text('* independent nested parameter divider\n.INC "models/one.inc"\n.LIB "models/diode.lib"\nV1 IN 0 DC 5\nR1 IN OUT {SCALE*RBASE}\nR2 OUT 0 {RBASE}\n.DC V1 5 5 1\n.PROBE\n.END\n',encoding='ascii')
(sources/'model-op.cir').write_text('* independent explicit model OP setup\n.LIB "models/diode.lib"\nV1 N 0 DC 0.1\nD1 N 0 DMODEL\n.OP\n.PROBE\n.END\n',encoding='ascii')
for name in ('missing-ground','undefined-parameter','bad-analysis','undefined-model'):(sources/(name+'.cir')).write_bytes((repo/'.local/input-setup-probe-20261025'/name/'input.cir').read_bytes())
before={p.relative_to(sources).as_posix():sha256(p) for p in sources.rglob('*') if p.is_file()}
expected={'dividerVolts':5.0/3.0,'absoluteTolerance':1e-6,'nestedFileCount':4,'nativeBadCases':['missing-ground','undefined-parameter','bad-analysis','undefined-model']};(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'checks':{}};keys=[]
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==173;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content)
    Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
   for name in ('nested','model-op',*expected['nativeBadCases']):
    prepared=await call('pspice_prepare',{'sourceCircuit':str(sources/(name+'.cir'))})
    if name=='nested':assert prepared['fileCount']==expected['nestedFileCount']
    plan=await call('pspice_plan_input_check',{'simulationId':prepared['simulationId']});key={k:plan[k] for k in ('planId','planDigest')}
    assert not plan['preview']['analysisWillExecute'];await call('pspice_close_input',{'simulationId':prepared['simulationId']})
    row={'case':name,'prepared':prepared,'plan':plan};report['cases'].append(row)
    if name in ('nested','model-op'):
     result=await call('pspice_apply_input_check',{**key,'idempotencyKey':name});row['result']=result
     assert result['nativeParserSetupVerified'] and result['nativeReceiptVerified'] and not result['analysisExecuted'] and not result['solverSuccessVerified'] and not result['numericalAcceptanceVerified']
     inspection=await call('pspice_inspect_input_check',key);row['inspection']=inspection
     assert inspection['preparedManifestSha256']==plan['preview']['preparedManifestSha256'] and inspection['simulationId']==prepared['simulationId']
     assert not inspection['analysisExecuted'] and inspection['scope']=='native_parse_setup_only' and len(inspection['files'])>=prepared['fileCount']+2
     keys.append((name,key))
    else:
     r=await client.call_tool('pspice_apply_input_check',{**key,'idempotencyKey':name});assert r.is_error and r.structured_content['error']['code']=='pspice_output_error',r.structured_content;row['error']=r.structured_content['error']
     failure=await call('pspice_inspect_run_failure',{**key,'kind':'input_check'});row['failure']=failure
     assert failure['workerStoppedVerified'] and failure['inputClosureMatchesPlan'] and failure['output']['hasErrorDiagnostics'] and not failure['solverSuccessVerified']
     r=await client.call_tool('pspice_inspect_input_check',key);assert r.is_error and r.structured_content['error']['code']=='output_unverified'
     r=await client.call_tool('pspice_apply_input_check',{**key,'idempotencyKey':name});assert r.is_error and r.structured_content['error']['code']=='write_not_replayed'
    print(name,'passed',flush=True)
   jobs=await call('pspice_input_check_jobs',{'offset':0,'limit':100});assert jobs['total']==6
   # Input setup does not stand in for numerical parameter evaluation: run a separate checked solve.
   prepared=await call('pspice_prepare',{'sourceCircuit':str(sources/'nested.cir')})
   run=await call('pspice_plan_run',{'simulationId':prepared['simulationId'],'analysis':'dc','expectedSamples':[{'block':0,'row':0,'traceName':'V(OUT)','real':expected['dividerVolts'],'imaginary':None,'absoluteTolerance':expected['absoluteTolerance'],'relativeTolerance':0.0}]});runkey={k:run[k] for k in ('planId','planDigest')}
   solved=await call('pspice_apply_run',{**runkey,'idempotencyKey':'nested-parameter-oracle'});assert solved['numericalAcceptanceVerified'] and solved['nativeCompletionVerified'];report['parameterSolve']={'plan':run,'result':solved}
   report['checks']['separate_fresh_solve_matches_independent_parameter_oracle']=True
  async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
   for name,key in keys:
    for tool,args in [('pspice_apply_input_check',{**key,'idempotencyKey':name}),('pspice_recover_input_check',key),('pspice_inspect_input_check',key)]:
     r=await fresh.call_tool(tool,args);assert not r.is_error,r.structured_content
     if tool=='pspice_apply_input_check':assert not r.structured_content['data']['mutationReplayed']
  report['checks']['plans_survive_input_close_and_fresh_server_no_replay']=True
  report['checks']['source_oracle_unchanged']=before=={p.relative_to(sources).as_posix():sha256(p) for p in sources.rglob('*') if p.is_file()} and sha256(root/'expected.json')==oracle
  report['passed']=len(report['cases'])==6 and all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
