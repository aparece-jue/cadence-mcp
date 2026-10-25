"""Read existing original topology fixtures through MCP; does not create them."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','placed-design','connected-design'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--shorted-design',type=Path)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
expected=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':ref,'pinNumber':pin,
    'connected':(ref,pin) in {('R101','2'),('R102','1')},
    'net':'MCP_MIDDLE' if (ref,pin) in {('R101','2'),('R102','1')} else None}
    for ref in ('R101','R102') for pin in ('1','2')]
(root/'expected.json').write_text(json.dumps(expected,indent=2))
sources=[('correct',a.connected_design.resolve(strict=True),'pass',0),('disconnected',a.placed_design.resolve(strict=True),'fail',2)]
if a.shorted_design:sources.append(('shorted',a.shorted_design.resolve(strict=True),'fail',2))
async def main():
    report={'passed':False,'createdAt':datetime.now(timezone.utc).isoformat(),'cases':[],
        'scope':'requested fixture reads / four selected pin definitions, not whole-design acceptance',
        'shortedFixtureProvided':a.shorted_design is not None}
    env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
    command=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),
        '--workspace-root',str(root/'work'),'--timeout-seconds','60']
    for parent in {path.parent for _,path,_,_ in sources}:command+=['--read-root',str(parent)]
    try:
        async with Client(StdioServerParameters(command=sys.executable,args=command,env=env),mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
            async def call(name,values):
                response=await client.call_tool(name,values);assert not response.is_error,response.content
                Draft202012Validator(schemas[name]).validate(response.structured_content)
                return response.structured_content['data']
            for name,path,verdict,failures in sources:
                case={'case':name,'passed':False,'sourceHashBefore':sha256(path)}
                try:
                    ws=await call('cadence_create_workspace',{'sourceDesign':str(path)})
                    opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
                    result=await call('capture_compare_connections',{'sessionId':sid,'expectedRevision':opened['revision'],
                        'expectations':expected,'expectationSource':'original-series-resistor-four-pin-spec@1'})
                    assert result['comparisonStatus']==verdict and result['countsByStatus'].get('fail',0)==failures,result
                    assert result['matchedPinCount']==4 and result['uncheckedObservedPinCount']==41 and result['designPassed'] is None
                    case.update(passed=True,result=result)
                    await call('capture_close',{'sessionId':sid})
                except Exception as error:case['error']=str(error)
                finally:
                    case['sourceHashAfter']=sha256(path)
                    if case['sourceHashAfter']!=case['sourceHashBefore']:case['passed']=False
                    report['cases'].append(case)
            report['passed']=all(c['passed'] for c in report['cases'])
    finally:(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'report':str(root/'report.json')}))
asyncio.run(main())
