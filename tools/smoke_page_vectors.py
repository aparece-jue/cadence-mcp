import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();fixture=a.fixture_root.resolve();source=fixture/'design.dsn';root.mkdir(exist_ok=False);expected=json.loads((fixture/'expected.json').read_text(encoding='utf-8'));env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(fixture),'--timeout-seconds','60'],env=env)
report={'passed':False,'readContractPassed':False,'textPlacementAccepted':False,'sourceHashBefore':sha256(source),'expectedHashBefore':sha256(fixture/'expected.json'),'checks':{}}
def dump():(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['tools']=len(tools);assert next(t for t in tools if t.name=='capture_query_page_vectors').model_dump(mode='json',by_alias=True)['annotations']['readOnlyHint']
   async def call(name,args,error=None):
    response=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content)
    else:assert not response.is_error,(name,response.structured_content)
    return response.structured_content['data']
   async def opened():
    workspace=await call('cadence_create_workspace',{'sourceDesign':str(source)});return workspace,await call('capture_open',{'workspaceId':workspace['workspaceId']})
   ws,session=await opened();sid=session['sessionId'];pages=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'];page=next(p for p in pages if p['name']=='MCP_PLACE');empty=next(p for p in pages if p['name']=='HALFADD');first=await call('capture_query_page_vectors',{'sessionId':sid,'pageId':page['objectId'],'limit':1});items=list(first['items']);cursor=first['nextCursor'];assert first['total']==32 and first['supportedGeometryComplete']
   while cursor:
    result=await call('capture_query_page_vectors',{'sessionId':sid,'pageId':page['objectId'],'limit':1,'cursor':cursor});items.extend(result['items']);cursor=result['nextCursor']
   assert [r['index'] for r in items]==list(range(32));assert len({r['objectId'] for r in items})==32;report['items']=items;report['placementDifferences']=[]
   for wanted,row in zip(expected,items):
    assert row['kind']==wanted['kind'] and row['rotationCode']==wanted['rotationCode'] and row['mirrorCode']==wanted['mirrorCode'] and row['localDescriptor']==wanted['localDescriptor']
    if row['location']!=wanted['location']:report['placementDifferences'].append({'objectId':row['objectId'],'kind':row['kind'],'expected':wanted['location'],'actual':row['location']})
   assert len(report['placementDifferences'])==4 and all(row['kind']=='text' for row in report['placementDifferences'])
   generic=(await call('capture_query_graphics',{'sessionId':sid,'entity':'graphic','pageId':page['objectId'],'limit':1000}))['items'];assert len(generic)==32
   for row in items:
    other=next(r for r in generic if r['objectId']==row['objectId']);assert other['nativeId']==row['nativeId'] and other['attributes']['location']==row['location'] and other['attributes']['rotationCode']==row['rotationCode'] and other['attributes']['mirrorCode']==row['mirrorCode']
   assert (await call('capture_query_page_vectors',{'sessionId':sid,'pageId':empty['objectId']}))['total']==0
   await call('capture_query_page_vectors',{'sessionId':sid,'pageId':empty['objectId'],'limit':1,'cursor':first['nextCursor']},'stale_cursor');await call('capture_query_page_vectors',{'sessionId':sid,'pageId':page['objectId'],'limit':2,'cursor':first['nextCursor']},'stale_cursor');await call('capture_query_page_vectors',{'sessionId':sid,'pageId':'schematic-999/page-999'},'invalid_scope');_,foreign=await opened();await call('capture_query_page_vectors',{'sessionId':foreign['sessionId'],'pageId':page['objectId'],'limit':1,'cursor':first['nextCursor']},'stale_cursor');await call('capture_close',{'sessionId':foreign['sessionId']})
   report['checks'].update(all_32_typed_definitions=True,all_28_nontext_declared_locations=True,all_text_literals_fonts_and_pose_codes=True,native_order_and_pagination=True,legacy_inventory_identity_consistency=True,empty_page=True,cursor_scope_limits=True);dump()
   for i in range(6):
    _,again=await opened();assert (await call('capture_query_page_vectors',{'sessionId':again['sessionId'],'pageId':page['objectId'],'limit':1000}))['total']==32;await call('capture_close',{'sessionId':again['sessionId']})
   target=root/'work'/ws['workspaceId']/'design.dsn';target.write_bytes(target.read_bytes()+b'owned cache-stale negative');await call('capture_query_page_vectors',{'sessionId':sid,'pageId':page['objectId'],'limit':1,'cursor':first['nextCursor']},'target_changed');await call('capture_close',{'sessionId':sid});await call('capture_query_page_vectors',{'sessionId':sid,'pageId':page['objectId']},'session_lost');report['checks'].update(six_extra_open_read_close=True,cached_input_hash_rechecked=True,closed_session_refused=True)
  report['readContractPassed']=True
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceHashAfter']=sha256(source);report['expectedHashAfter']=sha256(fixture/'expected.json');report['readContractPassed']=report['readContractPassed'] and report['sourceHashBefore']==report['sourceHashAfter'] and report['expectedHashBefore']==report['expectedHashAfter'];dump();print(json.dumps({'readContractPassed':report['readContractPassed'],'textPlacementAccepted':False,'checks':report['checks'],'error':report.get('error')}))
 if not report['readContractPassed']:raise SystemExit(1)
asyncio.run(main())
