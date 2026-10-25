"""Original four-pin topology acceptance: correct, disconnected and shorted copies."""
import argparse,asyncio,json,os,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser();p.add_argument('--install-root',type=Path,required=True)
p.add_argument('--workspace-root',type=Path,required=True);p.add_argument('--placed-design',type=Path,required=True)
p.add_argument('--connected-design',type=Path,required=True);args=p.parse_args()
repo=Path(__file__).resolve().parents[1];install=args.install_root.resolve(strict=True)
root=args.workspace_root.resolve();root.mkdir(exist_ok=False)
placed=args.placed_design.resolve(strict=True);connected=args.connected_design.resolve(strict=True)
expected=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':ref,'pinNumber':pin,
    'connected':(ref,pin) in {('R101','2'),('R102','1')},
    'net':'MCP_MIDDLE' if (ref,pin) in {('R101','2'),('R102','1')} else None}
    for ref in ('R101','R102') for pin in ('1','2')]
(root/'expected.json').write_text(json.dumps(expected,indent=2))
short=root/'shorted';short.mkdir();shutil.copyfile(connected,short/'design.dsn')
config=Config(install,root/'native',(),60)
report={'passed':False,'createdAt':datetime.now(timezone.utc).isoformat(),'cases':[],
        'scope':'four independently specified pin definitions; not whole-design DRC',
        'originalHashesBefore':{str(f):sha256(f) for f in (placed,connected)}}
process=run_owned_process([install/'tcltk/bin/tclsh.exe',repo/'tools/fixture_short_resistors.tcl',install,
    short/'design.dsn',short/'receipt.json',repo/'src/cadence_mcp/adapters/json.tcl'],short,process_env(config),60)
report['shortFixtureProcess']=process
async def main():
    try:
        assert process['state']=='exited' and process['returnCode']==0
        env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
        command=['-m','cadence_mcp.server','--install-root',str(install),'--workspace-root',str(root/'work'),'--timeout-seconds','60']
        for parent in {placed.parent,connected.parent,short}:command+=['--read-root',str(parent)]
        async with Client(StdioServerParameters(command=sys.executable,args=command,env=env),mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
            report['toolCount']=len(tools)
            async def call(name,values):
                response=await client.call_tool(name,values);assert not response.is_error,response.content
                Draft202012Validator(schemas[name]).validate(response.structured_content)
                return response.structured_content['data']
            for name,path,verdict,failures in [('correct',connected,'pass',0),('disconnected',placed,'fail',2),('shorted',short/'design.dsn','fail',2)]:
                ws=await call('cadence_create_workspace',{'sourceDesign':str(path)})
                opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
                result=await call('capture_compare_connections',{'sessionId':sid,'expectedRevision':opened['revision'],
                    'expectations':expected,'expectationSource':'original-series-resistor-four-pin-spec@1'})
                assert result['comparisonStatus']==verdict and result['countsByStatus'].get('fail',0)==failures,result
                assert result['matchedPinCount']==4 and result['uncheckedObservedPinCount']==41 and result['designPassed'] is None
                report['cases'].append({'case':name,'passed':True,'result':result})
                await call('capture_close',{'sessionId':sid})
            report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        report['originalHashesAfter']={str(f):sha256(f) for f in (placed,connected)}
        if report['originalHashesAfter']!=report['originalHashesBefore']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'report':str(root/'report.json')}))
asyncio.run(main())
