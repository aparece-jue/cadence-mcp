"""Actual MCP explicit input closure boundaries, including native Windows junction escape."""
import asyncio,json,os,sys,_winapi
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];root=repo/'.local/input-boundaries-mcp-20261025';root.mkdir(exist_ok=False)
sources=root/'sources';sources.mkdir();outside=root/'outside';outside.mkdir();one=root/'lookup1';two=root/'lookup2';one.mkdir();two.mkdir()
(outside/'outside.inc').write_text('.PARAM OUTSIDE=1\n',encoding='ascii')
for lookup in (one,two):(lookup/'common.inc').write_text('.PARAM COMMON=1\n',encoding='ascii')
_winapi.CreateJunction(str(outside),str(sources/'escape'))
(sources/'loop.inc').write_text('.INC "cycle.cir"\n',encoding='ascii');(sources/'binary.inc').write_bytes(b'\x00not text')
cases={
 'missing':('.INC "not_here.inc"','missing_or_ambiguous_reference'),
 'cycle':('.INC "loop.inc"','reference_cycle'),
 'outside':('.INC "'+(outside/'outside.inc').as_posix()+'"','path_denied'),
 'junction':('.INC "escape/outside.inc"','path_denied'),
 'ambiguous':('.INC "common.inc"','missing_or_ambiguous_reference'),
 'wildcard':('.LIB "*.lib"','unsupported_reference'),
 'dynamic':('.INC "{MODEL}.lib"','unsupported_reference'),
 'library-section':('.LIB "model.lib" SECTION','unsupported_reference'),
 'binary':('.INC "binary.inc"','unsupported_input'),
 'external-write':('.SAVEBIAS "outside.txt"','unsupported_reference')}
for name,(directive,code) in cases.items():(sources/(name+'.cir')).write_text('* independent boundary fixture\n'+directive+'\n.OP\n.END\n',encoding='ascii')
(sources/'no-end.cir').write_text('* no end\n.OP\n',encoding='ascii');(sources/'no-analysis.cir').write_text('* no analysis\n.END\n',encoding='ascii')
(sources/'control.cir').write_text('* unsupported control\n.CONTROL\n.ENDC\n.OP\n.END\n',encoding='ascii')
(sources/'embedded.cir').write_text('* unsupported embedded lookup\n.OPTIONS LIBPATH=other\n.OP\n.END\n',encoding='ascii')
folder=sources/'models folder';folder.mkdir();(folder/'deep').mkdir();(folder/'deep/model.lib').write_text('.MODEL DTEST D(IS=1n)\n',encoding='ascii');(folder/'level.lib').write_text('.LIB "deep/model.lib"\n.INCLUDE "../values.inc"\n',encoding='ascii');(sources/'values.inc').write_text('.PARAM RVAL=1k\n',encoding='ascii')
(sources/'nested-spaces.cir').write_text('* original nested LIB and INCLUDE with spaces\n.INC "models folder/level.lib"\nV1 N 0 DC 0.1\nR1 N 0 {RVAL}\nD1 N 0 DTEST\n.OP\n.PROBE\n.END\n',encoding='ascii')
tracked=[p for p in sources.rglob('*') if p.is_file()]+[outside/'outside.inc',one/'common.inc',two/'common.inc'];before={str(p):sha256(p) for p in tracked}
expected={'prepareErrors':{name:code for name,(_,code) in cases.items()},'invalidEntries':{'no-end':'invalid_circuit','no-analysis':'invalid_circuit'},'planErrors':{'control':'unsupported_execution_directive','embedded':'unsupported_embedded_reference'},'nestedFileCount':4}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--timeout-seconds','60']
for p in (sources,one,two):args+=['--read-root',str(p)]
params=StdioServerParameters(command=sys.executable,args=args,env=env);report={'passed':False,'cases':[],'checks':{}}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   assert len((await client.list_tools()).tools)==173
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content);return r.structured_content['data']
   for name,code in {**expected['prepareErrors'],**expected['invalidEntries']}.items():
    r=await client.call_tool('pspice_prepare',{'sourceCircuit':str(sources/(name+'.cir'))});assert r.is_error and r.structured_content['error']['code']==code,(name,r.structured_content);report['cases'].append({'case':name,'error':code})
   for name,code in expected['planErrors'].items():
    prepared=await call('pspice_prepare',{'sourceCircuit':str(sources/(name+'.cir'))});r=await client.call_tool('pspice_plan_input_check',{'simulationId':prepared['simulationId']});assert r.is_error and r.structured_content['error']['code']==code,(name,r.structured_content);await call('pspice_close_input',{'simulationId':prepared['simulationId']});report['cases'].append({'case':name,'error':code})
   assert (await call('pspice_input_check_jobs',{}))['total']==0
   prepared=await call('pspice_prepare',{'sourceCircuit':str(sources/'nested-spaces.cir')});assert prepared['fileCount']==4
   plan=await call('pspice_plan_input_check',{'simulationId':prepared['simulationId']});key={k:plan[k] for k in ('planId','planDigest')}
   result=await call('pspice_apply_input_check',{**key,'idempotencyKey':'nested-library-with-spaces'});assert result['nativeParserSetupVerified'] and not result['solverSuccessVerified'];report['positive']={'prepared':prepared,'plan':plan,'result':result}
   await call('pspice_close_input',{'simulationId':prepared['simulationId']});r=await client.call_tool('pspice_get_input',{'simulationId':prepared['simulationId']});assert r.is_error and r.structured_content['error']['code']=='simulation_not_found'
  report['checks']={'all_14_negative_boundaries_refused_before_native_worker':len(report['cases'])==14,'junction_escape_native_windows_tested':True,'nested_include_lib_relative_spaces_native_checked':True,'closed_prepared_input_rejected':True,'sources_and_oracle_unchanged':before=={str(p):sha256(p) for p in tracked} and sha256(root/'expected.json')==oracle}
  report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
