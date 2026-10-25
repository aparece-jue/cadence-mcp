"""Actual model/temperature property edits with a predeclared full property preservation oracle."""
import argparse,asyncio,copy,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture_edit import read_design_properties

p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
cases=[{'reference':'D1','field':'Implementation','value':'D1N4002'},
 {'reference':'R1','field':'TC1','value':'0.001'}, {'reference':'R1','field':'TC2','value':'-2e-6'},
 {'reference':'R1','field':'Value','value':'2k'}, {'reference':'D1','field':'PCB Footprint','value':'MCP_MODEL_FP'}]
(root/'declarations.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
config=Config(a.install_root,root/'oracle',(a.source.parent,),60)
before=read_design_properties(config,a.source,root);env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.source.parent),'--timeout-seconds','60'],env=env)
report={'passed':False,'sourceHashBefore':sha256(a.source),'cases':[],'checks':{}}
def dump(): (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args,error=None):
    r=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(r.structured_content)
    if error:assert r.is_error and r.structured_content['error']['code']==error,r.structured_content
    else:assert not r.is_error,r.structured_content
    return r.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(a.source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
   parts=(await call('capture_query',{'sessionId':sid,'entity':'part','limit':1000,'scope':{'kind':'design'}}))['items']
   ss=(await call('capture_query',{'sessionId':sid,'entity':'schematic','limit':1000,'scope':{'kind':'design'}}))['items'];names={s['objectId']:s['name'] for s in ss}
   for i,case in enumerate(cases):
    target=next(p for p in parts if names[p['schematicId']]=='ROOT' and p['reference']==case['reference'])
    expected=copy.deepcopy(before);row=next(r for r in expected if r['scope']==['ROOT','SAME_PAGE',case['reference']]);prop=next(p for p in row['properties'] if p['name']==case['field']);old=prop['value'];prop['value']=case['value']
    expected.sort(key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False));file=root/f'expected-{i}.json';file.write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf-8');expected_hash=sha256(file)
    plan=await call('capture_plan_property',{'sessionId':sid,'partId':target['objectId'],'propertyName':case['field'],'value':case['value']});key={k:plan[k] for k in ('planId','planDigest')};assert plan['preview']['oldValue']==old
    row={'case':case,'plan':plan};report['cases'].append(row);dump()
    result=await call('capture_apply_property',{**key,'idempotencyKey':f'model-{i}'});row['result']=result
    assert result['expectedValue']==result['observedValue']==case['value'] and result['electricalBehaviorVerified'] is False
    if case['field'] in ('Implementation','TC1','TC2'):assert result['effectivePropertyMultisetPreserved']
    output=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn';actual=read_design_properties(config,output,root)
    (root/f'actual-{i}.json').write_text(json.dumps(actual,ensure_ascii=False,indent=2),encoding='utf-8')
    assert actual==expected,(i,'full property graph differs');assert sha256(file)==expected_hash
    out=await call('capture_open_edit_result',{**key,'kind':'property'});await call('capture_close',{'sessionId':out['sessionId']})
    row['outputHash']=sha256(output);row['expectedHash']=expected_hash;dump();print(json.dumps({'case':i,'passed':True}),flush=True)
   r1=next(p for p in parts if names[p['schematicId']]=='ROOT' and p['reference']=='R1')
   await call('capture_plan_property',{'sessionId':sid,'partId':r1['objectId'],'propertyName':'Implementation','value':'TEST'},'model_type_required')
   for field,value in [('TC1','NaN'),('TC2','1e999'),('TC1','1k'),('Implementation','bad model')]:
    assert (await client.call_tool('capture_plan_property',{'sessionId':sid,'partId':r1['objectId'],'propertyName':field,'value':value})).is_error
   assert (await client.call_tool('capture_plan_property',{'sessionId':sid,'partId':r1['objectId'],'propertyName':'PSpiceTemplate','value':'bad'})).is_error
   pending=await call('capture_plan_property',{'sessionId':sid,'partId':r1['objectId'],'propertyName':'TC1','value':'0.01'});pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_property',pk);await call('capture_apply_property',{**pk,'idempotencyKey':'pending'},'write_not_replayed')
   await call('capture_close',{'sessionId':sid});report['checks'].update(strict_schema_and_model_type=True,pending_cancel=True,scope_and_all_effective_properties_preserved=True)
   report['toolCount']=len(tools)
  async with Client(params,mode='legacy',read_timeout_seconds=120) as fresh:
   for i,row in enumerate(report['cases']):
    key={k:row['plan'][k] for k in ('planId','planDigest')}
    result=await fresh.call_tool('capture_apply_property',{**key,'idempotencyKey':f'model-{i}'});assert not result.is_error,result.structured_content
    assert result.structured_content['data']['artifact']['sha256']==row['outputHash']
    result=await fresh.call_tool('capture_recover_property',key);assert not result.is_error,result.structured_content
  report['checks']['fresh_no_replay']=True;report['passed']=True
 except BaseException as error:report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
 finally:
  report['sourceHashAfter']=sha256(a.source)
  if report['sourceHashAfter']!=report['sourceHashBefore']:report['passed']=False
  dump()
 print(json.dumps({k:report.get(k) for k in ('passed','toolCount','checks','error')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
