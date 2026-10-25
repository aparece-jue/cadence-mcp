"""Real MCP shared-pin rows/geometry against frozen before-write unit declarations."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','expected'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--explicit-power-nets',action='store_true')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);before=sha256(source);expected=json.loads(a.expected.read_text());env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'sourceBefore':before,'scope':'shared-pin definition/geometry and optionally declared power-net readings; native network identity needs separate evidence'}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   ts=(await client.list_tools()).tools;assert len(ts)==137;(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];parts=[p for p in parts if p['reference']=='U501'];assert len(parts)==len(expected['units']);geometries=[];declared_pins=[pin for unit in expected['units'] for pin in unit['pins']]
   pins=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'reference':'U501','limit':1000}))['items'];assert sorted((p['number'],p['name']) for p in pins)==sorted((p['number'],p['name']) for p in declared_pins) and all(p['connected']==(a.explicit_power_nets and p['name'] in expected['netPaths']) and p['net']==(p['name'] if a.explicit_power_nets and p['name'] in expected['netPaths'] else '') for p in pins)
   for part in parts:
    geo=await call('capture_get_part_geometry',{'sessionId':sid,'partId':part['objectId']});unit=next(u for u in expected['units'] if u['location']==geo['location']);assert len(geo['pins'])==len(unit['pins']);assert sorted(({k:p[k] for k in ('number','name','hotSpot')} for p in geo['pins']),key=lambda p:(p['number'],p['name']))==sorted(unit['pins'],key=lambda p:(p['number'],p['name']));geometries.append(geo)
   report.update(sharedPinRows=sum(p['number']=='8' for p in pins),unitCount=len(parts),pinDefinitionRows=len(pins),uniquePhysicalNumbers=len({p['number'] for p in pins}),geometryVerified=True,pins=pins,geometries=geometries);report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceAfter']=sha256(source);report['passed'] &= before==report['sourceAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)


