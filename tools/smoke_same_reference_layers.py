"""C02 same-page shared reference: each native unit keeps its own property target."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];old=repo/'.local/shared-pin-reads-mcp-v2-20261024';source=next((old/'work').glob('ws-*/design.dsn'));oldreport=json.loads((old/'report.json').read_text());assert oldreport['passed'] and sha256(source)==oldreport['sourceBefore']
expectedfile=repo/'.local/multiunit-group-suffix-20261024/shared_dual-unbound/expected.json';expected=json.loads(expectedfile.read_text())['units'];assert len(expected)==2
root=repo/'.local/same-reference-property-layers-20261025';root.mkdir(exist_ok=False);hashes={'source':sha256(source),'expected':sha256(expectedfile)}
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'originalExpectedPath':str(expectedfile),'before':hashes}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content);return r.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId'];parts=(await call('capture_query',{'sessionId':sid,'entity':'part','reference':'U501','scope':{'kind':'design'}}))['items']
   assert len(parts)==2 and len({p['pageId'] for p in parts})==1
   positions=[]
   for p in parts:
    args={'sessionId':sid,'partId':p['objectId']};layers=await call('capture_get_property_layers',args);values={r['name']:r['value'] for r in layers['effective']};position=[int(values['Location X-Coordinate']),int(values['Location Y-Coordinate'])];positions.append(position)
    assert position in [u['location'] for u in expected];plain=await call('capture_get_part_properties',args);assert plain['items']==layers['effective'];report['cases'].append(layers)
   assert sorted(positions)==sorted(u['location'] for u in expected)
   await call('capture_close',{'sessionId':sid})
  report['after']={'source':sha256(source),'expected':sha256(expectedfile)};assert report['before']==report['after'];report['passed']=True
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error')}))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
