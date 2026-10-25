"""Actual MCP package mapping checked against original independently declared unit pin tables."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();a.install_root=a.install_root.resolve();a.fixture_root=a.fixture_root.resolve();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);prior=json.loads((a.fixture_root/'report.json').read_text(encoding='utf-8'))
cases=[]
for old in prior['cases']:
 cases.append({'case':old['case'],'source':a.fixture_root/'work'/old['result']['outputWorkspaceRelativePath']/'design.dsn','units':old['plan']['preview']['units'],'maps':{'U501':'U601'}})
second=prior['secondGroupPreservesRepeatedReferences']
cases.append({'case':'whole-package-swap','source':a.fixture_root/'work'/second['result']['outputWorkspaceRelativePath']/'design.dsn','units':prior['cases'][0]['plan']['preview']['units'],'maps':{'U501':'U502','U502':'U501'}})
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.fixture_root),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'originalExpectedTablesSha256':sha256(a.fixture_root/'report.json')}
def dump():(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
 async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
  tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
  for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
  async def call(name,args,error=None):
   r=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(r.structured_content)
   if error:assert r.is_error and r.structured_content['error']['code']==error,(name,r.structured_content)
   else:assert not r.is_error,(name,r.structured_content)
   return r.structured_content['data']
  for index,case in enumerate(cases):
   row={'case':case['case'],'source':str(case['source']),'sourceHashBefore':sha256(case['source']),'passed':False};report['cases'].append(row);dump()
   try:
    sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(case['source'])}))['workspaceId']}))['sessionId']
    parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items']
    mappings=[{'partId':next(p['objectId'] for p in parts if p['reference']==old),'newReference':new} for old,new in case['maps'].items()]
    plan=await call('capture_plan_package_reference_map',{'sessionId':sid,'mappings':mappings});row['plan']=plan;dump()
    changes=plan['preview']['changes'];assert len(changes)==len(case['units'])*len(mappings)
    for old,new in case['maps'].items():
     expected=sorted((old+unit['deviceDesignator'],new+unit['deviceDesignator'],pin['number'],pin['name'],pin['connected'],pin['net'] if pin['connected'] else None) for unit in case['units'] for pin in unit['expectedPins'])
     actual=sorted((p['oldFullReference'],p['newFullReference'],p['number'],p['name'],p['connected'],p['net']) for p in plan['preview']['pinNodeMap'] if p['oldFullReference'].startswith(old) and p['oldFullReference'] in {old+u['deviceDesignator'] for u in case['units']})
     assert actual==expected,('independent original node oracle',old,actual,expected)
    key={k:plan[k] for k in ('planId','planDigest')}
    await call('capture_close',{'sessionId':sid})
    result=await call('capture_apply_reference_map',{**key,'idempotencyKey':f'package-{index}'});row['result']=result
    for flag in ('packageOwnershipVerified','modeledAllInstanceStateVerified','cacheMetadataPreserved','ncOwnershipPreserved','oldNewNodeTableVerified','independentReopenVerified'):assert result[flag],flag
    opened=await call('capture_open_edit_result',{**key,'kind':'reference'});await call('capture_close',{'sessionId':opened['sessionId']})
    row['passed']=True
   except BaseException as e:row.update(error=str(e),traceback=traceback.format_exc())
   row['sourceHashAfter']=sha256(case['source']);row['passed']=row['passed'] and row['sourceHashAfter']==row['sourceHashBefore'];dump();print(json.dumps({'case':row['case'],'passed':row['passed'],'error':row.get('error')}),flush=True)
 async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
  for index,row in enumerate(report['cases']):
   if not row['passed']:continue
   key={k:row['plan'][k] for k in ('planId','planDigest')}
   r=await fresh.call_tool('capture_apply_reference_map',{**key,'idempotencyKey':f'package-{index}'});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
   r=await fresh.call_tool('capture_recover_reference_map',key);assert not r.is_error
 report['originalExpectedTablesSha256After']=sha256(a.fixture_root/'report.json');assert report['originalExpectedTablesSha256']==report['originalExpectedTablesSha256After']
 report['freshNoReplay']=True;report['passed']=all(c['passed'] for c in report['cases']);dump()
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
