"""Real MCP reads of saved NC add/remove fixtures, without changing originals."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);fixture=a.fixture_root.resolve(strict=True)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(fixture),'--timeout-seconds','60'],env=env)
expected=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':ref,'pinNumber':num,'connected':(ref,num) in {('R101','2'),('R102','1')},'net':'MCP_MIDDLE' if (ref,num) in {('R101','2'),('R102','1')} else None} for ref in ('R101','R102') for num in ('1','2')]
async def main():
 report={'passed':False,'cases':[]}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   ts=(await client.list_tools()).tools;assert len(ts)==116;schemas={t.name:t.output_schema for t in ts};report['toolCount']=len(ts)
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;Draft202012Validator(schemas[name]).validate(v.structured_content);return v.structured_content['data']
   for name,count in [('add',1),('remove',0)]:
    source=fixture/name/'design.dsn';before=sha256(source);ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
    data=await call('capture_query_connections',{'sessionId':sid,'entity':'nc','limit':1});assert data['total']==count and data['nextCursor'] is None
    if count:
     attrs=data['items'][0]['attributes'];assert attrs['reference']=='R101' and attrs['number']=='1' and attrs['hotSpot']==[290,310]
    compared=await call('capture_compare_connections',{'sessionId':sid,'expectedRevision':opened['revision'],'expectations':expected,'expectationSource':'nc-series-resistor-fixture@1'});assert compared['comparisonStatus']=='pass' and compared['designPassed'] is None
    assert (await client.call_tool('capture_query_connections',{'sessionId':sid,'entity':'nc','limit':True})).is_error
    report['cases'].append({'case':name,'passed':True,'sourceBefore':before,'sourceAfter':sha256(source),'nc':data,'comparison':compared});assert before==sha256(source)
    await call('capture_close',{'sessionId':sid});assert (await client.call_tool('capture_query_connections',{'sessionId':sid,'entity':'nc'})).is_error
  report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}))
asyncio.run(main())
