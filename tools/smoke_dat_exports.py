"""Actual MCP CSV/JSON export of complex imports and verified mixed analog run snapshots."""
import argparse,asyncio,csv,io,json,math,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256,write_json
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','complex-dat','mixed-run-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.complex_dat.resolve(strict=True);before=sha256(source)
mixed_root=a.mixed_run_root.resolve(strict=True);mixed=json.loads((mixed_root/'report.json').read_text(encoding='utf-8'));assert mixed['passed'];run_key={k:mixed['plan'][k] for k in ('planId','planDigest')}
expected={'complex0':[[0,10,0,10,-1],[1,20,0,20,-2],[2,30,0,30,-3]],'complex1range':[[1,20,0,120,-3],[2,30,0,130,-4]],'mixedCurrent':0.001,'absoluteTolerance':1e-6};write_json(root/'expected.json',expected);oracle=sha256(root/'expected.json')
def parameters(work,readroot):return StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(work),'--read-root',str(readroot),'--timeout-seconds','60'],env=os.environ.copy())
report={'passed':False,'cases':[],'checks':{}};keys=[]
async def group(label,params,work):
 async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
  tools=(await client.list_tools()).tools;assert len(tools)==160;schemas={t.name:t.output_schema for t in tools}
  async def call(name,args):
   result=await client.call_tool(name,args);assert not result.is_error,(name,result.structured_content)
   Draft202012Validator(schemas[name]).validate(result.structured_content);return result.structured_content['data']
  opened=await call('pspice_dat_open',{'sourceDat':str(source)}) if label=='imported' else await call('pspice_open_run_dat',run_key)
  ident=opened['datId']
  cases=[('complex0','csv',0,0,None),('complex1range','json',1,1,2)] if label=='imported' else [('mixed-csv','csv',0,0,None),('mixed-json','json',0,1,3)]
  planned=[]
  for name,format,block,offset,count in cases:
   trace='Gain' if label=='imported' else 'I(RLOAD)'
   plan=await call('pspice_plan_dat_export',{'datId':ident,'block':block,'traceName':trace,'format':format,'offset':offset,'count':count});key={k:plan[k] for k in ('planId','planDigest')};planned.append((name,format,plan,key))
  if label=='mixed':
   bad=await client.call_tool('pspice_plan_dat_export',{'datId':ident,'block':0,'traceName':'DIN'});assert bad.is_error and bad.structured_content['error']['code']=='capability_unavailable'
   report['checks']['digital_export_refused']=True
  bad=await client.call_tool('pspice_plan_dat_export',{'datId':ident,'block':0,'traceName':'Gain' if label=='imported' else 'I(RLOAD)','offset':100000,'count':1});assert bad.is_error
  # Durable plans must not need the original in-memory DAT session to remain open.
  await call('pspice_dat_close',{'datId':ident})
  for name,format,plan,key in planned:
   row={'case':name,'passed':False,'plan':plan};report['cases'].append(row)
   result=await call('pspice_apply_dat_export',{**key,'idempotencyKey':name});row['result']=result
   assert result['workerCompletionVerified'] and result['nativeReopenVerified'] and result['sampleIdentityVerified']
   directory=work/result['outputWorkspaceRelativePath'];manifest=json.loads((directory/'export-manifest.json').read_text(encoding='utf-8'));row['manifest']=manifest
   assert manifest['dataSha256']==sha256(directory/manifest['dataFile']) and not manifest['metadata']['exportedRowsNumericalOracleVerified']
   origin=manifest['metadata']['sourceProvenance'];assert origin['jobAssociationVerified']==(label=='mixed')
   if label=='mixed':assert origin['producedByPlan']==run_key['planId'] and origin['solverSuccessVerified'] and manifest['metadata']['valueUnits']=={'unit':'A','unitSource':'trace_name_convention'}
   else:assert not origin['solverSuccessVerified'] and manifest['metadata']['valueUnits']['unit'] is None
   if format=='csv':
    with (directory/manifest['dataFile']).open(newline='',encoding='utf-8') as stream:raw=list(csv.DictReader(stream))
    assert list(raw[0])==['index','axisReal','axisImaginary','real','imaginary']
    rows=[{'index':int(v['index']),**{k:None if v[k]=='' else float(v[k]) for k in ('axisReal','axisImaginary','real','imaginary')}} for v in raw]
   else:
    output=json.loads((directory/manifest['dataFile']).read_text(encoding='utf-8'));assert output['metadata']==manifest['metadata'];rows=output['samples']
   if label=='imported':assert [[v[k] for k in ('index','axisReal','axisImaginary','real','imaginary')] for v in rows]==expected[name]
   else:assert all(abs(v['real']-0.001)<=1e-6 and v['imaginary'] is None and v['axisImaginary'] is None for v in rows)
   assert len(rows)==manifest['metadata']['rowCount']==result['rowCount'];row.update(passed=True,rows=rows);keys.append((params,work,name,key))
   print(name,True,flush=True)
  jobs=await call('pspice_dat_export_jobs',{'offset':0,'limit':100});assert jobs['total']>=len(planned)

async def main():
 try:
  await group('imported',parameters(root/'work',source.parent),root/'work')
  await group('mixed',parameters(mixed_root/'work',mixed_root/'inputs'),mixed_root/'work')
  for params,work,name,key in keys:
   async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
    result=await fresh.call_tool('pspice_apply_dat_export',{**key,'idempotencyKey':name});assert not result.is_error and result.structured_content['data']['mutationReplayed'] is False
    recovered=await fresh.call_tool('pspice_recover_dat_export',key);assert not recovered.is_error
  report['checks']['fresh_lifecycle_no_replay']=True
  report['checks']['original_source_and_oracle_unchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
  report['passed']=len(keys)==4 and all(r['passed'] for r in report['cases']) and all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(keys),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
