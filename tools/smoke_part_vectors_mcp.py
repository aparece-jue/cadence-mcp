"""Actual read-only MCP eight-pose vector and lifecycle acceptance."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];sources=r/'.local/noncentered-pose-rectangle-a-20261026'
root=r/'.local/part-vectors-mcp-20261027';root.mkdir(exist_ok=False)
lines=[[[0,0],[40,20]],[[40,20],[0,40]],[[0,40],[0,0]]]
cases=[]
for mirror in (0,1):
 for rotation in range(4):
  def transform(point):
   x,y=point;w,h=80,40
   if mirror:x=w-x
   for _ in range(rotation):x,y=y,w-x;w,h=h,w
   return [600+x,400+y]
  cases.append({'rotation':rotation,'mirror':mirror,'localLines':lines,'pageLines':[[transform(p) for p in line] for line in lines]})
(root/'expected.json').write_text(json.dumps({'model':'fixed local triangle; declared width80/height40 compensation, mirror before clockwise quarter turns; frozen before current native reads','cases':cases},indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
before={f'r{c["rotation"]}-m{c["mirror"]}/design.dsn':sha256(sources/f'r{c["rotation"]}-m{c["mirror"]}/design.dsn') for c in cases}
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[],'sourceBefore':before,'fullV02Accepted':False,'renderedClearanceAccepted':False}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools);assert len(tools)==222
   async def call(name,args,error=None):
    value=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(value.structured_content)
    if error:assert value.is_error and value.structured_content['error']['code']==error,value
    else:assert not value.is_error,value
    return value.structured_content.get('data')
   first_cursor=None
   for case in cases:
    path=sources/f'r{case["rotation"]}-m{case["mirror"]}/design.dsn'
    ws=await call('cadence_create_workspace',{'sourceDesign':str(path)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
    args={'sessionId':sid,'partId':'schematic-1/page-1/part-1','limit':1};rows=[];cursor=None
    while True:
     result=await call('capture_query_part_vectors',{**args,'cursor':cursor});rows+=result['items'];cursor=result['nextCursor']
     if first_cursor is None and cursor is not None:first_cursor=cursor
     if cursor is None:break
    assert result['total']==3 and result['unsupportedCount']==0 and result['supportedGeometryComplete'] and not result['renderedBoundsVerified']
    assert [v['localDescriptor'] for v in rows]==[['line',*line,0,0] for line in case['localLines']]
    assert [v['pageControlPoints'] for v in rows]==case['pageLines'],(case,rows)
    assert all(v['nativeId'] is None and v['rotationCode']==case['rotation'] and v['mirrorCode']==case['mirror'] and v['partId']==args['partId'] for v in rows)
    assert [v['objectId'] for v in rows]==[args['partId']+'/vector-'+str(i) for i in range(1,4)]
    if len(report['cases']):await call('capture_query_part_vectors',{**args,'cursor':first_cursor},'stale_cursor')
    else:await call('capture_query_part_vectors',{**args,'limit':2,'cursor':first_cursor},'stale_cursor')
    await call('capture_query_part_vectors',{'sessionId':sid,'partId':'schematic-1/page-1/part-999'},'object_not_found')
    report['cases'].append({'rotation':case['rotation'],'mirror':case['mirror'],'items':rows,'passed':True})
    if case==cases[-1]:
     (root/'work'/ws['workspaceId']/'design.dsn').write_bytes(b'owned immutable-session tamper negative')
     await call('capture_query_part_vectors',args,'target_changed')
    await call('capture_close',{'sessionId':sid});await call('capture_query_part_vectors',args,'session_lost')
   report.update(passed=True,nativeEightPoseMatrixAccepted=True,paginationAndCursorIsolationAccepted=True,sourceTamperRejected=True,closedSessionRejected=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=all(sha256(sources/p)==h for p,h in before.items());report['oracleUnchanged']=sha256(root/'expected.json')==oracle
 report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','toolCount','error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
