"""Fixed original manually declared hierarchy-block geometry, no hierarchy pass claim."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];root=r/'.local/c03-drawn-geometry-20261028';root.mkdir(exist_ok=False)
source=r/'.local/editor-hierarchy-scaffold-20261027/design.dsn';source_hash=sha256(source)
expected={'partId':'schematic-1/page-1/part-1','reference':'BLOCK_A','location':[400,300],'rotationCode':0,'mirrorCode':0,'pins':[{'name':'IN','hotSpot':[400,320]},{'name':'OUT','hotSpot':[500,320]}],'scope':'C03 geometry only; original hierarchy flat-net/port-direction/cycle gates remain separate and unaccepted'}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'fullH03Accepted':False}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    value=await client.call_tool(name,args);assert not value.is_error,value;return value.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
   data=await call('capture_get_part_geometry',{'sessionId':sid,'partId':expected['partId']});report['actual']=data
   for key in ('partId','reference','location','rotationCode','mirrorCode'):assert data[key]==expected[key]
   assert sorted((p['name'],p['hotSpot']) for p in data['pins'])==sorted((p['name'],p['hotSpot']) for p in expected['pins'])
   assert not data['electricalConnectivityVerified'];await call('capture_close',{'sessionId':sid});report['passed']=True
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==source_hash;report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
