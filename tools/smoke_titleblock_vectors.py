"""Actual MCP acceptance of fixed native titleblock source and immutable guards."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];source_root=r/'.local/titleblock-vectors-v2-20261028'
p=argparse.ArgumentParser();p.add_argument('--workspace-root',type=Path,default=r/'.local/titleblock-vector-mcp-20261028');args=p.parse_args();root=args.workspace_root.resolve();assert root.is_relative_to(r/'.local');root.mkdir(exist_ok=False)
source=source_root/'design.dsn';oracle=source_root/'expected.json';before=sha256(source);oracle_before=sha256(oracle);expected=json.loads(oracle.read_text(encoding='utf-8'))
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source_root)],env=env)
async def main():
 report={'passed':False,'fullC05Accepted':False,'checks':{},'sourceBefore':before,'oracleBefore':oracle_before}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['tools']=len(tools)
   async def call(name,args,error=None):
    res=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(res.structured_content)
    if error:assert res.is_error and res.structured_content['error']['code']==error,(name,res.structured_content)
    else:assert not res.is_error,(name,res.structured_content)
    return res.structured_content['data']
   async def opened():return await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']})
   opening=await opened();sid=opening['sessionId'];pages=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'];names={p['objectId']:p['name'] for p in pages}
   titles=(await call('capture_query_graphics',{'sessionId':sid,'entity':'titleblock','limit':1000}))['items'];assert len(titles)==9
   outputs=[]
   for title in titles:
    attrs=title['attributes'];pose=next(p for p in expected['poses'] if p['page']==names[title['pageId']] and p['rotationCode']==attrs['rotationCode'] and p['mirrorCode']==attrs['mirrorCode']);assert attrs['location']==pose['location']
    key={'sessionId':sid,'titleblockId':title['objectId']};data=await call('capture_query_titleblock_vectors',{**key,'limit':1000});assert data['total']==3 and data['sourceSymbol']=='MCP_TITLE' and not data['renderedBoundsVerified'];rows=data['items'];assert all(x['titleblockId']==title['objectId'] and x['pageId']==title['pageId'] and x['nativeId'] is None for x in rows)
    line=next(x for x in rows if x['kind']=='line');text=next(x for x in rows if x['kind']=='text');box=next(x for x in rows if x['kind']=='box')
    assert line['localDescriptor']==['line',[-30,10],[140,90],0,0] and line['pageControlPoints']==pose['predictedLine']
    assert box['localDescriptor'][1]==[-30,10,140,90] and text['localDescriptor'][1]==expected['text'] and text['localDescriptor'][4][0]=='Arial' and text['localDescriptor'][4][1]==-10
    gathered=[];cursor=None
    while True:
     page=await call('capture_query_titleblock_vectors',{**key,'limit':1,**({'cursor':cursor} if cursor else {})});gathered+=page['items'];cursor=page['nextCursor']
     if cursor is None:break
    assert gathered==rows;outputs.append(data)
   report['cases']=outputs;report['checks'].update(nineNativeTitleblocks=True,eightPoses=True,localDescriptorsUnicodeAndLinePagePoints=True,orderedOneItemPaging=True,duplicateNamePageIsolation=True)
   empty=next(p for p in pages if p['name']=='EMPTY');assert (await call('capture_query_graphics',{'sessionId':sid,'entity':'titleblock','pageId':empty['objectId']}))['total']==0
   tid=titles[0]['objectId'];first=await call('capture_query_titleblock_vectors',{'sessionId':sid,'titleblockId':tid,'limit':1});cursor=first['nextCursor'];assert cursor
   for args in [{'titleblockId':titles[1]['objectId'],'limit':1},{'titleblockId':tid,'limit':2}]:await call('capture_query_titleblock_vectors',{'sessionId':sid,'cursor':cursor,**args},'stale_cursor')
   await call('capture_query_titleblock_vectors',{'sessionId':sid,'titleblockId':'schematic-999/page-999/titleblock-999'},'object_not_found')
   foreign=await opened();await call('capture_query_titleblock_vectors',{'sessionId':foreign['sessionId'],'titleblockId':tid,'limit':1,'cursor':cursor},'stale_cursor');await call('capture_close',{'sessionId':foreign['sessionId']})
   copied=root/'work'/opening['workspaceId']/'design.dsn';copied.write_bytes(copied.read_bytes()+b'owned cached-source negative');await call('capture_query_titleblock_vectors',{'sessionId':sid,'titleblockId':tid},'target_changed')
   await call('capture_close',{'sessionId':sid});await call('capture_query_titleblock_vectors',{'sessionId':sid,'titleblockId':tid},'session_lost');report['checks'].update(emptyPage=True,wrongTargetAndCursorGuards=True,cachedSourceTamperRefused=True,closedSessionRefused=True)
  report['passed']=True
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=sha256(oracle)==oracle_before;report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=True),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
