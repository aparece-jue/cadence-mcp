"""Real stdio package mapping over a declared cross-page fixture with literal display overrides."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();fixture=a.fixture_root.resolve();root.mkdir(exist_ok=False);source=fixture/'fixture.dsn'
assert json.loads((fixture/'report.json').read_text(encoding='utf-8'))['passed']
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(fixture),'--timeout-seconds','60'],env=env)
report={'passed':False,'sourceHashBefore':sha256(source),'fixtureReportHashBefore':sha256(fixture/'report.json'),'cases':[]}
def dump():(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;report['toolCount']=len(tools);schemas={t.name:t.output_schema for t in tools}
   async def call(name,args,error=None):
    result=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(result.structured_content)
    if error:assert result.is_error and result.structured_content['error']['code']==error,(name,result.structured_content)
    else:assert not result.is_error,(name,result.structured_content)
    return result.structured_content['data']
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId']
   parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];group=[p for p in parts if p['reference']=='U501'];assert len(group)==2 and len({p['pageId'] for p in group})==2
   await call('capture_plan_package_reference_map',{'sessionId':sid,'mappings':[{'partId':group[0]['objectId'],'newReference':'U601'},{'partId':group[1]['objectId'],'newReference':'U602'}]},'duplicate_package_mapping')
   collision=next(p['reference'] for p in parts if p['reference'].startswith('U') and p['reference']!='U501')
   await call('capture_plan_package_reference_map',{'sessionId':sid,'mappings':[{'partId':group[0]['objectId'],'newReference':collision}]},'reference_conflict')
   for index,representative in enumerate(group):
    destination=('U601','U701')[index];plan=await call('capture_plan_package_reference_map',{'sessionId':sid,'mappings':[{'partId':representative['objectId'],'newReference':destination}]});key={k:plan[k] for k in ('planId','planDigest')};row={'plan':plan,'representative':representative,'passed':False};report['cases'].append(row);dump()
    assert {c['newFullReference'] for c in plan['preview']['changes']}=={destination+'A',destination+'B'}
    result=await call('capture_apply_reference_map',{**key,'idempotencyKey':f'crosspage-{index}'});row['result']=result;out=(await call('capture_open_edit_result',{**key,'kind':'reference'}))['sessionId']
    output_parts=(await call('capture_query',{'sessionId':out,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];changed=[p for p in output_parts if p['reference']==destination];assert len(changed)==2 and len({p['pageId'] for p in changed})==2
    for part in changed:
     layers=await call('capture_get_property_layers',{'sessionId':out,'partId':part['objectId']});full=next(p['value'] for p in layers['effective'] if p['name']=='Part Reference');suffix=full[-1];assert full in {destination+'A',destination+'B'}
     assert next(p['value'] for p in layers['user'] if p['name']=='MCP_NOTE')==f'位号 U501 / U501{suffix} / U5010 [x]$;'
     for name,location,rotation,dtype in [('Part Reference',[17,23],2,1),('Reference',[19,31],1,2),('MCP_NOTE',[29,37],3,1)]:
      display=next(p for p in layers['display'] if p['name']==name);assert display['location']==location and display['rotationCode']==rotation and display['displayTypeCode']==dtype and display['colorCode']==3
    await call('capture_close',{'sessionId':out});row['passed']=True;dump();print(json.dumps({'case':index,'passed':True}),flush=True)
   pending=await call('capture_plan_package_reference_map',{'sessionId':sid,'mappings':[{'partId':group[0]['objectId'],'newReference':'U801'}]});pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_reference_map',pk);await call('capture_apply_reference_map',{**pk,'idempotencyKey':'pending'},'write_not_replayed');await call('capture_close',{'sessionId':sid});report['pendingCancel']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for index,row in enumerate(report['cases']):
    key={k:row['plan'][k] for k in ('planId','planDigest')};response=await fresh.call_tool('capture_apply_reference_map',{**key,'idempotencyKey':f'crosspage-{index}'});assert not response.is_error and not response.structured_content['data']['mutationReplayed']
   row=report['cases'][1];key={k:row['plan'][k] for k in ('planId','planDigest')};target=root/'work'/row['result']['outputWorkspaceRelativePath']/'design.dsn';(target.parent/'design.pre-tamper.dsn').write_bytes(target.read_bytes());target.write_bytes(target.read_bytes()+b'owned output tamper')
   for name,args in [('capture_open_edit_result',{**key,'kind':'reference'}),('capture_recover_reference_map',key)]:
    response=await fresh.call_tool(name,args);assert response.is_error and response.structured_content['error']['code']=='target_changed'
  report.update(freshNoReplay=True,terminalOutputTamperRefused=True,passed=True)
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceHashAfter']=sha256(source);report['fixtureReportHashAfter']=sha256(fixture/'report.json');report['passed']=report['passed'] and report['sourceHashBefore']==report['sourceHashAfter'] and report['fixtureReportHashBefore']==report['fixtureReportHashAfter'];dump();print(json.dumps({'passed':report['passed'],'error':report.get('error')},ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
