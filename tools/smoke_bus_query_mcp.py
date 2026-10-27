"""Actual public bus inventory: original native8bit oracle, pagination and guards."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
from cadence_mcp.capture_wire import geometry_union
r=Path(r'D:\workspace\git\cadence-mcp');base=r/'.local/editor-eight-bit-bus-20261027';root=r/'.local/bus-query-mcp-20261027';root.mkdir(exist_ok=False);dispatch=json.loads((base/'dispatch-report.json').read_text(encoding='utf-8'));source=r/dispatch['jobDirectory']/'design.dsn';before=sha256(source);expected=json.loads((base/'expected.json').read_text(encoding='utf-8'));oracle_hash=sha256(base/'expected.json');empty=r/'.local/editor-session-wire-20261026/before.dsn';empty_before=sha256(empty)
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(empty.parent),'--timeout-seconds','30'],env=env)
async def main():
 report={'passed':False,'checks':{},'sourceBefore':before,'oracleSha256':oracle_hash}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
   async def call(name,args):
    res=await client.call_tool(name,args);assert not res.is_error,res.structured_content or res.content;Draft202012Validator(schemas[name]).validate(res.structured_content);return res.structured_content['data']
   async def opened(path):
    ws=await call('cadence_create_workspace',{'sourceDesign':str(path)});op=await call('capture_open',{'workspaceId':ws['workspaceId']});return ws,op
   ws,op=await opened(source);sid=op['sessionId'];all_rows={};first_cursor=None
   for kind in ('bus','scalar','entry'):
    rows=[];cursor=None
    while True:
     page=await call('capture_query_bus',{'sessionId':sid,'entity':kind,'limit':1,'cursor':cursor});rows+=page['items'];cursor=page['nextCursor']
     if kind=='bus' and first_cursor is None:first_cursor=cursor
     if cursor is None:break
    assert len(rows)==page['total'];all_rows[kind]=rows
   buses=all_rows['bus'];scalar=all_rows['scalar'];entries=all_rows['entry'];assert len(buses)==9 and len(scalar)==8 and len(entries)==8
   assert all(b['width']==8 and not b['isBundle'] and b['name']==expected['busName'] and [m['name'] for m in b['members']]==expected['memberNames'] for b in buses)
   assert geometry_union([b['points'] for b in buses])==geometry_union([expected['busPoints']]);assert sorted(w['name'] for w in scalar)==sorted(expected['scalarNames'])
   wires={w['wireId']:w for w in buses+scalar}
   for i,point in enumerate(expected['entryPoints']):
    entry=next(e for e in entries if e['entryPoint']==point);assert entry['endPoint']==expected['endPoints'][i]
    a=wires[entry['entryWireId']];b=wires[entry['endWireId']];assert a['isBus'] and not b['isBus'] and b['name']=='DATA'+str(i);assert point in a['points'] and entry['endPoint'] in b['points']
   report['checks'].update(originalEightBitOrderAndGeometry=True,allEightMemberNames=True,nativeEntryBothWireLinks=True,oneItemPagination=True);report['rows']=all_rows
   for args in ({'entity':'entry','limit':1,'cursor':first_cursor},{'entity':'bus','limit':2,'cursor':first_cursor},{'entity':'bus','pageId':'outside'}):assert (await client.call_tool('capture_query_bus',{'sessionId':sid,**args})).is_error
   _,foreign=await opened(source);assert (await client.call_tool('capture_query_bus',{'sessionId':foreign['sessionId'],'entity':'bus','limit':1,'cursor':first_cursor})).is_error
   await call('capture_close',{'sessionId':foreign['sessionId']});_,blank=await opened(empty)
   for kind in ('bus','scalar','entry'):assert (await call('capture_query_bus',{'sessionId':blank['sessionId'],'entity':kind}))['total']==0
   await call('capture_close',{'sessionId':blank['sessionId']})
   for _ in range(3):
    _,again=await opened(source);assert (await call('capture_query_bus',{'sessionId':again['sessionId'],'entity':'entry'}))['total']==8;await call('capture_close',{'sessionId':again['sessionId']})
   staged=root/'work'/ws['workspaceId']/'design.dsn';staged.write_bytes(staged.read_bytes()+b'owned snapshot stale-read negative');res=await client.call_tool('capture_query_bus',{'sessionId':sid,'entity':'bus'});assert res.is_error and res.structured_content['error']['code']=='target_changed'
   await call('capture_close',{'sessionId':sid});assert (await client.call_tool('capture_query_bus',{'sessionId':sid,'entity':'entry'})).is_error
   report['checks'].update(cursorScopeAndPageAndSessionGuards=True,emptyPage=True,threeMoreOpenReadClose=True,cachedSourceMutationRefused=True,closedSessionRefused=True);report['passed']=True
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=sha256(base/'expected.json')==oracle_hash;report['emptySourceUnchanged']=sha256(empty)==empty_before;report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged'] and report['emptySourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='rows'}),flush=True)
asyncio.run(main())
