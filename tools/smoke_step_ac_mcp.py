import argparse,asyncio,csv,io,json,math,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser(description='Actual MCP parameter-swept complex DAT block and export acceptance against a frozen RC formula.')
for name in ('workspace-root','fixture-root','install-root'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--backend',choices=('cli','engine'),default='cli')
a=p.parse_args();plan_tool='pspice_plan_cli_run' if a.backend=='cli' else 'pspice_plan_run';apply_tool='pspice_apply_cli_run' if a.backend=='cli' else 'pspice_apply_run';root=a.workspace_root.resolve();root.mkdir(exist_ok=False);fixture=a.fixture_root.resolve(strict=True);oracle=json.loads((fixture/'expected.json').read_text(encoding='utf-8'));source_hashes={str(x):sha256(x) for x in fixture.iterdir() if x.is_file()}
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(fixture),'--read-root',str(root),'--timeout-seconds','60'],env=env)
report={'passed':False,'fullP04Accepted':False,'backend':a.backend,'originalDat10WriterFixed':False,'cases':[]}
def key(plan):return {k:plan[k] for k in ('planId','planDigest')}
def close(actual,expected):assert abs(actual-expected)<=1e-6+1e-4*abs(expected),(actual,expected)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,(name,reply.structured_content);return reply.structured_content['data']
   prepared=await call('pspice_prepare',{'sourceCircuit':str(fixture/'circuit.cir')});report['prepared']=prepared
   plan=await call(plan_tool,{'simulationId':prepared['simulationId'],'analysis':'ac','expectedSamples':oracle['expectedSamples']});report['plan']=plan
   (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   result=await call(apply_tool,{**key(plan),'idempotencyKey':'step-ac-'+a.backend});assert result['numericalAcceptanceVerified'];report['result']=result
   dat=await call('pspice_open_run_dat',{**key(plan),'backend':a.backend});ident=dat['datId'];assert dat['jobAssociationVerified'] and dat['blockCount']==2;report['dat']=dat
   blocks=await call('pspice_dat_query',{'datId':ident,'entity':'block','limit':1});assert blocks['total']==2 and blocks['nextOffset']==1
   second=await call('pspice_dat_query',{'datId':ident,'entity':'block','offset':1,'limit':1});assert second['complete'];ordered=blocks['items']+second['items'];report['blocks']=ordered
   exports=[]
   for want in oracle['blocks']:
    block=want['index'];assert ordered[block]['complex'] and ordered[block]['rowCount']==3
    values=await call('pspice_dat_samples',{'datId':ident,'block':block,'traceName':'V(OUT)','limit':2});assert values['total']==3 and values['nextOffset']==2
    tail=await call('pspice_dat_samples',{'datId':ident,'block':block,'traceName':'V(OUT)','offset':2,'limit':1});assert tail['complete']
    rows=values['items']+tail['items'];frequency=await call('pspice_dat_samples',{'datId':ident,'block':block,'traceName':'Frequency'})
    for actual,axis,expected in zip(rows,frequency['items'],want['rows']):
     close(actual['real'],expected['real']);close(actual['imaginary'],expected['imaginary']);assert axis['real']==expected['frequency'] and axis['imaginary']==0
    empty=await call('pspice_dat_samples',{'datId':ident,'block':block,'traceName':'V(OUT)','offset':3,'limit':1});assert empty['items']==[] and empty['complete']
    for bad,code in [({'block':block,'traceName':'V(OUT)','offset':4},'invalid_query'),({'block':2,'traceName':'V(OUT)'},'invalid_block'),({'block':block,'traceName':'V(MISSING)'},'trace_not_found')]:
     rejected=await client.call_tool('pspice_dat_samples',{'datId':ident,**bad});assert rejected.is_error and rejected.structured_content['error']['code']==code
    export=await call('pspice_plan_dat_export',{'datId':ident,'block':block,'traceName':'V(OUT)','format':'csv' if block==0 else 'json','offset':0,'count':3});exports.append(export)
    report['cases'].append({'block':block,'samples':rows,'frequency':frequency['items'],'exportPlan':export})
   await call('pspice_dat_close',{'datId':ident});report['closedSourceSessionBeforeExport']=True
   for entry,export in zip(report['cases'],exports):
    exported=await call('pspice_apply_dat_export',{**key(export),'idempotencyKey':'step-export-'+str(entry['block'])});entry['exportResult']=exported;assert exported['nativeReopenVerified'] and exported['sourceProvenance']['jobAssociationVerified']
    folder=root/'work'/exported['outputWorkspaceRelativePath'];text=(folder/('samples.'+exported['format'])).read_text(encoding='utf-8')
    rows=list(csv.DictReader(io.StringIO(text))) if exported['format']=='csv' else json.loads(text)['samples']
    for actual,expected in zip(rows,oracle['blocks'][entry['block']]['rows']):
     close(float(actual['real']),expected['real']);close(float(actual['imaginary']),expected['imaginary']);assert float(actual['axisReal'])==expected['frequency']
    metadata=json.loads((folder/'export-manifest.json').read_text())['metadata'];assert metadata['axisUnits']['unit']=='Hz' and metadata['valueUnits']['unit']=='V';assert not metadata['exportedRowsNumericalOracleVerified']
  frozen={str(x):sha256(x) for x in (root/'work/isolated-jobs').rglob('*') if x.is_file()}
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   repeat=await client.call_tool(apply_tool,{**key(plan),'idempotencyKey':'step-ac-'+a.backend});assert not repeat.is_error and repeat.structured_content['data']==result
   for entry in report['cases']:
    for name,args in [('pspice_apply_dat_export',{**key(entry['exportPlan']),'idempotencyKey':'step-export-'+str(entry['block'])}),('pspice_recover_dat_export',key(entry['exportPlan']))]:
     repeat=await client.call_tool(name,args);assert not repeat.is_error and repeat.structured_content['data']==entry['exportResult']
   assert {str(x):sha256(x) for x in (root/'work/isolated-jobs').rglob('*') if x.is_file()}==frozen
  report.update(passed=True,twoNativeComplexBlocksAccepted=True,bothBlocksMatchIndependentOracle=True,csvAndJsonNativeReopenAccepted=True,freshServerNoReplayAndFilesUnchanged=True)
 except Exception as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:
  report['sourceAndOracleUnchanged']=all(sha256(Path(path))==digest for path,digest in source_hashes.items());report['passed']=report['passed'] and report['sourceAndOracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
  print(json.dumps({k:report.get(k) for k in ('passed','error','twoNativeComplexBlocksAccepted','csvAndJsonNativeReopenAccepted','freshServerNoReplayAndFilesUnchanged','sourceAndOracleUnchanged')}))
asyncio.run(main())
if not report['passed']:raise SystemExit(1)
