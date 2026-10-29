import argparse,asyncio,copy,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','native-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);case=next(c for c in json.loads((a.native_root/'expected.json').read_text(encoding='utf-8')) if c['case']=='B-cross');source=Path(case['source']);assert sha256(source)==case['sourceBefore'];env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env);report={'passed':False,'cases':[],'checks':{},'sourceBefore':sha256(source)}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=300) as c:
   schemas={t.name:t.output_schema for t in (await c.list_tools()).tools};report['tools']=len(schemas)
   async def call(name,args,error=None):
    response=await c.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content);return
    assert not response.is_error,(name,response.structured_content);return response.structured_content['data']
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId'];parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];owner=next(p for p in parts if p['reference']=='U501');pages=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'];target=next(p for p in pages if p['name']=='HALFADD' and p['schematicId']==owner['schematicId']);foreign=next(p for p in pages if p['schematicId']!=owner['schematicId']);pins=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];existing=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in pins if p['pageId']==target['objectId']];cache=(await call('capture_query_cache',{'sessionId':sid,'entity':'part','limit':1000}))['items'];devices=(await call('capture_query_cache',{'sessionId':sid,'entity':'device','limit':1000}))['items'];device=next(d for d in devices if d['designator']=='B' and any(p['deviceId']==d['objectId'] and p['name']==case['request']['partName'] for p in cache));cached=next(p for p in cache if p['deviceId']==device['objectId'] and p['name']==case['request']['partName']);args={'sessionId':sid,'ownerPartId':owner['objectId'],'cachePartId':cached['objectId'],'location':case['request']['location'],'rotationCode':case['request']['rotation'],'mirrorCode':case['request']['mirror'],'expectedPins':case['expectedPins'],'expectedExistingConnections':existing,'targetPageId':target['objectId']};(root/'expected.json').write_text(json.dumps(args,ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
   await call('capture_plan_cached_unit_add',{**args,'targetPageId':foreign['objectId']},'unsupported_unit_scope');await call('capture_plan_cached_unit_add',{**args,'targetPageId':'foreign-revision-page'},'object_not_found');await call('capture_plan_cached_unit_add',{**args,'expectedExistingConnections':existing[:-1]},'incomplete_expectations');report['checks']['foreign_schematic_stale_page_and_incomplete_target_baseline_refused']=True
   plan=await call('capture_plan_cached_unit_add',args);key={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_multiunit_placement',{**key,'idempotencyKey':'cross-B'});assert result['crossPageUnitAssignmentVerified'] and result['allOriginalModeledInstanceStateVerified'];opened=await call('capture_open_edit_result',{**key,'kind':'multiunit_placement'});outparts=(await call('capture_query',{'sessionId':opened['sessionId'],'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];outpages=(await call('capture_query',{'sessionId':opened['sessionId'],'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'];group=[p for p in outparts if p['reference']=='U501'];assert len(group)==2;names={p['objectId']:p['name'] for p in outpages};assert {names[p['pageId']] for p in group}=={'MCP_PLACE','HALFADD'};new=next(p for p in group if names[p['pageId']]=='HALFADD');geometry=await call('capture_get_part_geometry',{'sessionId':opened['sessionId'],'partId':new['objectId']});assert geometry['location']==case['request']['location'];report['cases'].append({'plan':plan,'result':result,'opened':opened,'targetGeometry':geometry});report['checks']['real_cross_page_unit_source_state_and_reopen']=True
   for part in group:
    props=(await call('capture_get_part_properties',{'sessionId':opened['sessionId'],'partId':part['objectId']}))['items']
    actual={p['name']:p['value'] for p in props}
    assert {k:actual[k] for k in case['overrides']}==case['overrides']
   report['inheritedOverrides']=case['overrides'];report['checks']['nondefaultValueAndFootprintOnBothUnits']=True
   report['checks']['oracle_unchanged']=oracle==sha256(root/'expected.json')
  async with Client(params,mode='legacy',read_timeout_seconds=300) as fresh:
   response=await fresh.call_tool('capture_apply_multiunit_placement',{**key,'idempotencyKey':'cross-B'});assert not response.is_error and not response.structured_content['data']['mutationReplayed'];assert not (await fresh.call_tool('capture_recover_multiunit_placement',key)).is_error;assert not (await fresh.call_tool('capture_open_edit_result',{**key,'kind':'multiunit_placement'})).is_error;report['checks']['fresh_server_recover_and_no_replay']=True
   targetfile=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn';(root/'valid-output.dsn').write_bytes(targetfile.read_bytes());targetfile.write_bytes(targetfile.read_bytes()+b'owned cross page terminal tamper')
   for name,arguments in [('capture_apply_multiunit_placement',{**key,'idempotencyKey':'cross-B'}),('capture_recover_multiunit_placement',key),('capture_open_edit_result',{**key,'kind':'multiunit_placement'})]:
    response=await fresh.call_tool(name,arguments);assert response.is_error and response.structured_content['error']['code']=='target_changed'
   report['checks']['terminal_hash_mutation_refused']=True
  report['sourceAfter']=sha256(source);report['passed']=all(report['checks'].values()) and report['sourceBefore']==report['sourceAfter']
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')},ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
