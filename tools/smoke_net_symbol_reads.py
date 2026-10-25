"""Actual MCP query/oracle checks on symbol-bound connected saved fixtures."""
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
cases=[('global','global','MCP_SUPPLY',[230,300],0,0),('offpage','offpage','MCP_LINK',[240,300],0,0),('global90','global','MCP_GROUND',[240,300],1,1),('offpage90','offpage','MCP_LINK',[230,310],1,1)]
async def main():
 report={'passed':False,'cases':[]}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   ts=(await client.list_tools()).tools;assert len(ts)==126;schemas={t.name:t.output_schema for t in ts};report['toolCount']=len(ts)
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;Draft202012Validator(schemas[name]).validate(v.structured_content);return v.structured_content['data']
   for case,kind,name,loc,rot,mirror in cases:
    source=fixture/case/'design.dsn';before=sha256(source);ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId'];query=await call('capture_query_connections',{'sessionId':sid,'entity':kind,'limit':1});assert query['total']==1 and query['nextCursor'] is None
    attrs=query['items'][0]['attributes'];assert attrs=={'name':name,'sourceSymbol':'MCP_NETSYM','location':loc,'hotSpot':[240,310],'rotationCode':rot,'mirrorCode':mirror,'isBus':False}
    expected=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':ref,'pinNumber':num,'connected':(ref,num)!=('R102','2'),'net':name if (ref,num)==('R101','1') else 'MCP_MIDDLE' if (ref,num) in {('R101','2'),('R102','1')} else None} for ref in ('R101','R102') for num in ('1','2')]
    compared=await call('capture_compare_connections',{'sessionId':sid,'expectedRevision':opened['revision'],'expectations':expected,'expectationSource':'capsym-wire-lead-fixture@1'});assert compared['comparisonStatus']=='pass' and compared['designPassed'] is None
    await call('capture_close',{'sessionId':sid});assert (await client.call_tool('capture_query_connections',{'sessionId':sid,'entity':kind})).is_error
    assert before==sha256(source);report['cases'].append({'case':case,'passed':True,'beforeSha256':before,'afterSha256':sha256(source),'query':query,'comparison':compared})
  report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}))
asyncio.run(main())
