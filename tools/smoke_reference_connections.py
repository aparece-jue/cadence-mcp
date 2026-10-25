"""Independent fixed expectations for original FULLADD ports and owned shared-pin NC."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();source=a.source.resolve();root.mkdir(exist_ok=False);env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
expect={'HALFADD':['CARRY','SUM','X','Y'],'FULLADD':['CARRY_IN','CARRY_OUT','SUM','X','Y'],'MCP_PLACE':[]};(root/'expected.json').write_text(json.dumps({'ports':expect,'nc':{'count':1,'reference':'U501','number':'8','hotSpot':[1000,680]},'directPort':{'page':'FULLADD','name':'CARRY_OUT','reference':'U1','number':'3','hotSpot':[560,320]}},indent=2),encoding='utf-8');report={'passed':False,'sourceHashBefore':sha256(source),'expectedHashBefore':sha256(root/'expected.json'),'checks':{}}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['tools']=len(tools)
   async def call(name,args,error=None):
    response=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content)
    else:assert not response.is_error,(name,response.structured_content)
    return response.structured_content['data']
   async def opened():
    workspace=await call('cadence_create_workspace',{'sourceDesign':str(source)});return workspace,await call('capture_open',{'workspaceId':workspace['workspaceId']})
   ws,session=await opened();sid=session['sessionId'];pages=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'];names={p['objectId']:p['name'] for p in pages};first=await call('capture_query_connections',{'sessionId':sid,'entity':'port','limit':1});rows=list(first['items']);cursor=first['nextCursor'];assert first['total']==9
   while cursor:
    page=await call('capture_query_connections',{'sessionId':sid,'entity':'port','limit':1,'cursor':cursor});rows.extend(page['items']);cursor=page['nextCursor']
   report['ports']=rows
   assert len(rows)==9 and len({r['objectId'] for r in rows})==9 and len({(r['pageId'],r['nativeId']) for r in rows})==9
   for page in pages:
    result=await call('capture_query_connections',{'sessionId':sid,'entity':'port','pageId':page['objectId'],'limit':1000});assert result['items']==[r for r in rows if r['pageId']==page['objectId']];assert sorted(r['attributes']['name'] for r in result['items'])==expect[page['name']]
   wires=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','limit':1000}))['items'];report['wires']=wires
   report['checks'].update(nine_port_count_names=True,one_item_pagination=True,page_scoped_duplicate_names=True,empty_port_page=True)
   def on_segment(point,start,end):return (point[0]-start[0])*(end[1]-start[1])==(point[1]-start[1])*(end[0]-start[0]) and min(start[0],end[0])<=point[0]<=max(start[0],end[0]) and min(start[1],end[1])<=point[1]<=max(start[1],end[1])
   parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];direct=next(p for p in parts if p['reference']=='U1' and names[p['pageId']]=='FULLADD');geometry=await call('capture_get_part_geometry',{'sessionId':sid,'partId':direct['objectId']});direct_pin=next(p for p in geometry['pins'] if p['number']=='3');assert direct_pin['hotSpot']==[560,320];report['directPortGeometry']=geometry
   for port in rows:
    on_wire=any(w['pageId']==port['pageId'] and any(on_segment(port['attributes']['hotSpot'],a,b) for a,b in zip(w['attributes']['points'],w['attributes']['points'][1:])) for w in wires)
    direct_match=port['pageId']==direct['pageId'] and port['attributes']['name']=='CARRY_OUT' and port['attributes']['hotSpot']==direct_pin['hotSpot']
    assert on_wire or direct_match,port
   report['checks']['native_port_wire_or_declared_direct_pin_consistency']=True
   nc=(await call('capture_query_connections',{'sessionId':sid,'entity':'nc','limit':1000}))['items'];assert len(nc)==1;attr=nc[0]['attributes'];assert attr['reference']=='U501' and attr['number']=='8' and attr['hotSpot']==[1000,680];pins=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];pin=next(p for p in pins if p['objectId']==attr['pinId']);assert pin['partId']==attr['partId'] and pin['number']=='8';report['nc']=nc;report['checks']['shared_nc_owner_and_coordinates']=True
   await call('capture_query_connections',{'sessionId':sid,'entity':'port','limit':2,'cursor':first['nextCursor']},'stale_cursor');await call('capture_query_connections',{'sessionId':sid,'entity':'port','pageId':'schematic-999/page-999'},'invalid_scope');_,other=await opened();await call('capture_query_connections',{'sessionId':other['sessionId'],'entity':'port','limit':1,'cursor':first['nextCursor']},'stale_cursor');await call('capture_close',{'sessionId':other['sessionId']});report['checks']['cursor_and_scope_rejections']=True
   for i in range(6):
    _,again=await opened();assert (await call('capture_query_connections',{'sessionId':again['sessionId'],'entity':'port','limit':1000}))['total']==9;await call('capture_close',{'sessionId':again['sessionId']})
   report['checks']['six_additional_open_read_close']=True
   changed=root/'work'/ws['workspaceId']/'design.dsn';assert changed.is_file();changed.write_bytes(changed.read_bytes()+b'owned stale query input');await call('capture_query_connections',{'sessionId':sid,'entity':'port','limit':1,'cursor':first['nextCursor']},'target_changed');report['checks']['cached_query_revalidates_source']=True;await call('capture_close',{'sessionId':sid});await call('capture_query_connections',{'sessionId':sid,'entity':'nc'},'session_lost');report['checks']['closed_session_refused']=True
  report['passed']=True
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceHashAfter']=sha256(source);report['expectedHashAfter']=sha256(root/'expected.json');report['passed']=report['passed'] and report['sourceHashBefore']==report['sourceHashAfter'] and report['expectedHashBefore']==report['expectedHashAfter'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')},ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
