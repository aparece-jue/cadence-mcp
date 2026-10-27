"""Original H03 graph audit: public reads plus independent native flat identity diagnostics."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
r=Path(__file__).resolve().parents[1];root=r/'.local/editor-hierarchy-audit-20261027';root.mkdir(exist_ok=False);prior=json.loads((r/'.local/editor-hierarchy-ports-20261027/report.json').read_text(encoding='utf-8'));assert prior['passed'];source=r/prior['dispatch']['jobDirectory']/'design.dsn';before=sha256(source)
oracle_path=r/'.local/hierarchy-fresh-ports-v2-20261023/expected.json';oracle_hash=sha256(oracle_path);expected=json.loads(oracle_path.read_text(encoding='utf-8'));(root/'original-expected.json').write_bytes(oracle_path.read_bytes());env=os.environ.copy();env['PYTHONPATH']=str(r/'src');install=Path(r'D:\Program Files\Cadence\SPB_24.1');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(install),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','30'],env=env)
report=dict(passed=False,publicGraphAccepted=False,fullH03Accepted=False,sourceBefore=before,originalOracleSha256=oracle_hash)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content or reply.content;return reply.structured_content['data']
   ws=await call('cadence_create_workspace',dict(sourceDesign=str(source)));opened=await call('capture_open',dict(workspaceId=ws['workspaceId']));sid=opened['sessionId'];assert opened['counts']==dict(schematic=2,page=2,part=1,pin=2)
   part=(await call('capture_query',dict(sessionId=sid,entity='part',scope=dict(kind='design'))))['items'][0];assert part['reference']==expected['block']
   geometry=await call('capture_get_part_geometry',dict(sessionId=sid,partId=part['objectId']));report['parentGeometry']=geometry;assert geometry['location']==expected['blockLocation'];assert {p['name']:p['hotSpot'] for p in geometry['pins']}==expected['parentPinHotspots']
   pages=(await call('capture_query',dict(sessionId=sid,entity='page',scope=dict(kind='design'))))['items'];child=next(p for p in pages if p['name']=='CHILD_PAGE')
   ports=(await call('capture_query_connections',dict(sessionId=sid,entity='port',pageId=child['objectId'],limit=100)))['items'];report['publicPorts']=ports;assert len(ports)==2
   assert {p['attributes']['name']:p['attributes']['hotSpot'] for p in ports}=={k:v['hotSpot'] for k,v in expected['childPorts'].items()}
   tree=await call('capture_get_hierarchy',dict(sessionId=sid,limit=100));report['tree']=tree;assert tree['total']==2 and any(p['reference']=='BLOCK_A' and p['instancePathSegments']==['BLOCK_A'] for p in tree['items'])
   report['publicGraphAccepted']=True
 except BaseException:report['publicError']=traceback.format_exc()
 cfg=Config(install,root/'read-work',(source.parent,),30)
 for mode,script in [('legacy','inspect_occurrence_nets.tcl'),('direct',str(r/'tools/inspect_occurrence_flat_direct.tcl'))]:
  output=root/(mode+'-flat.json');item=dict(passed=False);report[mode+'Flat']=item
  try:
   run_tcl(cfg,script,[str(source),str(output)],root);data=json.loads(output.read_text(encoding='utf-8'));item['data']=data;rows=data['pins'];assert len(rows)==2 and {p['name'] for p in rows}=={'IN','OUT'}
   assert all(p['instancePathSegments']==['BLOCK_A'] for p in rows);assert rows[0]['flatNetId'] is not None and rows[0]['flatNetId']==rows[1]['flatNetId'];item['passed']=True
  except BaseException:item['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=sha256(oracle_path)==oracle_hash;report['passed']=report['publicGraphAccepted'] and report['directFlat']['passed'] and report['sourceUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
asyncio.run(main())
