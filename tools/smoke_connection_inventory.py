import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root','nc-source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();fixture=a.fixture_root.resolve();nc=a.nc_source.resolve();source=fixture/'design.dsn';root.mkdir(exist_ok=False);expected=json.loads((fixture/'expected.json').read_text(encoding='utf-8'));env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(fixture),'--read-root',str(nc.parent),'--timeout-seconds','60'],env=env)
report={'passed':False,'sourceHashesBefore':{'matrix':sha256(source),'nc':sha256(nc),'expected':sha256(fixture/'expected.json')},'checks':{},'differences':[]}
def dump():(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;report['tools']=len(tools);schemas={t.name:t.output_schema for t in tools}
   async def call(name,args,error=None):
    response=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content)
    else:assert not response.is_error,(name,response.structured_content)
    return response.structured_content['data']
   async def open_source(path):return await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(path)}))['workspaceId']})
   opened=await open_source(source);sid=opened['sessionId'];pages=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'];assert sorted(p['name'] for p in pages)==sorted(expected['pages']);ids={p['name']:p['objectId'] for p in pages};all_objects=[];cursor=None
   for kind in ('global','offpage','wire','alias','port','nc'):
    first=await call('capture_query_connections',{'sessionId':sid,'entity':kind,'limit':1});rows=list(first['items']);next_cursor=first['nextCursor']
    if kind=='global':cursor=next_cursor;await call('capture_query_connections',{'sessionId':sid,'entity':'offpage','limit':1,'cursor':cursor},'stale_cursor')
    while next_cursor:
     page=await call('capture_query_connections',{'sessionId':sid,'entity':kind,'limit':1,'cursor':next_cursor});rows.extend(page['items']);next_cursor=page['nextCursor']
    assert len(rows)==first['total'];assert len({r['objectId'] for r in rows})==len(rows);all_objects.extend(rows)
    for page_name,page_id in ids.items():
     scoped=await call('capture_query_connections',{'sessionId':sid,'entity':kind,'pageId':page_id,'limit':1000});assert scoped['items']==[r for r in rows if r['pageId']==page_id]
     wanted=[r for r in expected['objects'] if r['kind']==kind and r['pageName']==page_name];actual=scoped['items'];assert len(actual)==len(wanted),(kind,page_name,len(actual),len(wanted))
     if kind in ('global','offpage'):
      for declaration in wanted:
       attr=declaration['attributes'];item=next(r for r in actual if r['attributes']['location']==attr['location']);different={k:{'expected':v,'actual':item['attributes'][k]} for k,v in attr.items() if item['attributes'][k]!=v}
       if different:report['differences'].append({'page':page_name,'kind':kind,'rotation':attr['rotationCode'],'mirror':attr['mirrorCode'],'differences':different})
     elif kind in ('wire','alias'):
      for declaration in wanted:assert any(all(r['attributes'].get(k)==v for k,v in declaration['attributes'].items()) for r in actual),(kind,page_name,declaration,actual)
   report['matrixObjects']=all_objects;report['checks'].update(counts=True,all_pose_locations_and_names=True,page_isolation=True,pagination=True,empty_page=True)
   by_id={r['objectId']:r for r in all_objects}
   for alias in (r for r in all_objects if r['kind']=='alias'):assert by_id[alias['attributes']['wireId']]['pageId']==alias['pageId']
   await call('capture_query_connections',{'sessionId':sid,'entity':'wire','pageId':'schematic-999/page-999'},'invalid_scope')
   foreign=await open_source(source);await call('capture_query_connections',{'sessionId':foreign['sessionId'],'entity':'global','limit':1,'cursor':cursor},'stale_cursor');await call('capture_close',{'sessionId':foreign['sessionId']})
   nopen=await open_source(nc);nsid=nopen['sessionId'];nrows=(await call('capture_query_connections',{'sessionId':nsid,'entity':'nc','limit':1000}))['items'];assert len(nrows)==1;attr=nrows[0]['attributes'];assert attr['reference']=='U501' and attr['number']=='8' and attr['hotSpot']==[1000,680];pins=(await call('capture_query',{'sessionId':nsid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];pin=next(p for p in pins if p['objectId']==attr['pinId']);assert pin['partId']==attr['partId'] and pin['number']=='8'
   npages=(await call('capture_query',{'sessionId':nsid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'];names={p['objectId']:p['name'] for p in npages};ports=(await call('capture_query_connections',{'sessionId':nsid,'entity':'port','limit':1000}))['items'];assert len(ports)==9
   assert sorted((names[p['pageId']],p['attributes']['name']) for p in ports)==sorted([('HALFADD',n) for n in ('X','Y','SUM','CARRY')]+[('FULLADD',n) for n in ('X','Y','CARRY_IN','SUM','CARRY_OUT')])
   wires=(await call('capture_query_connections',{'sessionId':nsid,'entity':'wire','limit':1000}))['items']
   for port in ports:assert any(w['pageId']==port['pageId'] and port['attributes']['hotSpot'] in w['attributes']['points'] for w in wires),port
   report['nc']=nrows;report['ports']=ports;report['checks'].update(shared_nc_owner=True,all_nine_original_ports=True,port_hotspot_wire_endpoint_consistency=True,alias_wire_parent=True,foreign_scope_and_cursor=True);await call('capture_close',{'sessionId':nsid});dump()
   for i in range(6):
    opened_again=await open_source(source);data=await call('capture_query_connections',{'sessionId':opened_again['sessionId'],'entity':'global','limit':1000});assert data['total']==16;await call('capture_close',{'sessionId':opened_again['sessionId']})
   report['checks']['six_additional_open_read_close']=True
   changed=root/'work'/opened['workspaceId']/'design.dsn';assert changed.is_file();changed.write_bytes(changed.read_bytes()+b'owned readonly stale-source negative');await call('capture_query_connections',{'sessionId':sid,'entity':'global','limit':1,'cursor':cursor},'target_changed');report['checks']['cached_query_rechecks_source']=True
   await call('capture_close',{'sessionId':sid});await call('capture_query_connections',{'sessionId':sid,'entity':'wire'},'session_lost');report['checks']['closed_session_refused']=True
  report['passed']=not report['differences']
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceHashesAfter']={'matrix':sha256(source),'nc':sha256(nc),'expected':sha256(fixture/'expected.json')};report['passed']=report['passed'] and report['sourceHashesBefore']==report['sourceHashesAfter'];dump();print(json.dumps({'passed':report['passed'],'checks':report['checks'],'differences':report['differences'],'error':report.get('error')},ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
