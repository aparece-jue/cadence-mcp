"""Create an intentional four-pin short in a copy, then reject the normal oracle."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);repo=Path(__file__).resolve().parents[1]
normal=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':r,'pinNumber':n,
    'connected':(r,n) in {('R101','2'),('R102','1')},'net':'MCP_MIDDLE' if (r,n) in {('R101','2'),('R102','1')} else None}
    for r in ('R101','R102') for n in ('1','2')]
short=[{**row,'connected':True,'net':'MCP_MIDDLE'} for row in normal]
(root/'expected.json').write_text(json.dumps({'intentionally_created':short,'intended_design':normal},indent=2))
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'sourceHashBefore':sha256(source),'phase':'open'}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            async def call(name,values):
                row=await client.call_tool(name,values);assert not row.is_error,row.content
                return row.structured_content['data']
            ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
            page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE')
            wire=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','pageId':page['objectId']}))['items'][0]
            alias=(await call('capture_query_connections',{'sessionId':sid,'entity':'alias','pageId':page['objectId']}))['items'][0]
            report['phase']='plan_short'
            plan=await call('capture_plan_wire_edit',{'sessionId':sid,'wireId':wire['objectId'],'operation':'set_endpoints',
                'start':[290,310],'end':[530,310],'aliasLocations':[{'aliasId':alias['objectId'],'location':[330,310]}],'expectedConnections':short})
            report['plan']=plan;keys={k:plan[k] for k in ('planId','planDigest')};report['phase']='create_short'
            report['result']=await call('capture_apply_wire_edit',{**keys,'idempotencyKey':'intentional-short'})
            report['phase']='compare_correct_design'
            opened=await call('capture_open_edit_result',{**keys,'kind':'wire_edit'})
            comparison=await call('capture_compare_connections',{'sessionId':opened['sessionId'],'expectedRevision':opened['revision'],
                'expectations':normal,'expectationSource':'original-series-resistor-four-pin-spec@1'})
            report['comparison']=comparison
            assert comparison['comparisonStatus']=='fail' and comparison['countsByStatus'].get('fail')==2 and comparison['designPassed'] is None
            report['passed']=True
    except BaseException as error:report['error']=str(error)
    finally:
        report['sourceHashAfter']=sha256(source)
        if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'phase':report['phase'],'error':report.get('error'),'report':str(root/'report.json')}))
asyncio.run(main())
