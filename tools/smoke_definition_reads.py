"""Native MCP definition-read regression, including unbound pins and owned fixtures."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
parser=argparse.ArgumentParser();parser.add_argument('--install-root',type=Path,required=True)
parser.add_argument('--workspace-root',type=Path,required=True);parser.add_argument('--placed-design',type=Path)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
install=args.install_root.resolve(strict=True);root=args.workspace_root.resolve();root.mkdir(exist_ok=False)
samples=install/'tools/capture/samples/Schematic'
sources=[(name,samples/name/(name+'.DSN')) for name in ('FULLADD','CMOSCPU','TUTOR2')]
read_roots=[samples]
if args.placed_design:
    args.placed_design=args.placed_design.resolve(strict=True)
    sources.append(('placed_fixture',args.placed_design));read_roots.append(args.placed_design.parent)
async def main():
    env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
    command=['-m','cadence_mcp.server','--install-root',str(install),'--workspace-root',str(root/'work'),'--timeout-seconds','60']
    for read_root in read_roots:command+=['--read-root',str(read_root)]
    params=StdioServerParameters(command=sys.executable,args=command,env=env)
    report={'passed':False,'createdAt':datetime.now(timezone.utc).isoformat(),'cases':[]}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
            report['toolCount']=len(tools)
            async def call(name,values):
                result=await client.call_tool(name,values);assert not result.is_error,result.content
                Draft202012Validator(schemas[name]).validate(result.structured_content)
                return result.structured_content['data']
            for name,path in sources:
                case={'sample':name,'passed':False,'sourceHashBefore':sha256(path)}
                try:
                    workspace=await call('cadence_create_workspace',{'sourceDesign':str(path)})
                    opened=await call('capture_open',{'workspaceId':workspace['workspaceId']});sid=opened['sessionId']
                    case['counts']=opened['counts']
                    if name=='FULLADD':assert opened['counts']=={'schematic':2,'page':2,'part':9,'pin':41}
                    if name=='placed_fixture':assert opened['counts']=={'schematic':2,'page':3,'part':11,'pin':45}
                    rows=[];cursor=None
                    while True:
                        page=await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'cursor':cursor,'limit':7})
                        rows+=page['items'];cursor=page['nextCursor']
                        if cursor is None:break
                    assert len(rows)==opened['counts']['pin'] and len({r['objectId'] for r in rows})==len(rows)
                    case['unboundPins']=sum(not p['connected'] for p in rows)
                    if name in ('CMOSCPU','TUTOR2'):assert case['unboundPins']>0
                    if name=='placed_fixture':
                        pins=[p for p in rows if p['reference'] in ('R101','R102')]
                        assert len(pins)==4 and all(not p['connected'] and p['net']=='' for p in pins)
                        assert {(p['reference'],p['number']) for p in pins}=={('R101','1'),('R101','2'),('R102','1'),('R102','2')}
                    await call('capture_close',{'sessionId':sid})
                    case['passed']=True
                finally:
                    case['sourceHashAfter']=sha256(path)
                    if case['sourceHashAfter']!=case['sourceHashBefore']:case['passed']=False
                    report['cases'].append(case)
            report['passed']=all(c['passed'] for c in report['cases'])
    except BaseException as error:report['error']=str(error);raise
    finally:(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'report':str(root/'report.json')}))
asyncio.run(main())
