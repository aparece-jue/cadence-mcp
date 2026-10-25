"""Native stdio wire-add acceptance using the predeclared two-resistor fixture."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
source=a.source.resolve(strict=True)
expected=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':ref,'pinNumber':pin,
    'connected':(ref,pin) in {('R101','2'),('R102','1')},
    'net':'MCP_MIDDLE' if (ref,pin) in {('R101','2'),('R102','1')} else None}
    for ref in ('R101','R102') for pin in ('1','2')]
(root/'expected.json').write_text(json.dumps(expected,indent=2))
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),
    '--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'createdAt':datetime.now(timezone.utc).isoformat(),'checks':{},'sourceHashBefore':sha256(source)}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
            for tool in tools:
                Draft202012Validator.check_schema(tool.input_schema);Draft202012Validator.check_schema(tool.output_schema)
            report['toolCount']=len(tools)
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,values):
                response=await client.call_tool(name,values);assert not response.is_error,response.content
                Draft202012Validator(schemas[name]).validate(response.structured_content)
                return response.structured_content['data']
            ws=await call('cadence_create_workspace',{'sourceDesign':str(source)})
            opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
            page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE')
            args={'sessionId':sid,'pageId':page['objectId'],'start':[330,310],'end':[490,310],
                  'netName':'MCP_MIDDLE','expectedConnections':expected}
            plan=await call('capture_plan_wire_add',args);keys={k:plan[k] for k in ('planId','planDigest')}
            result=await call('capture_apply_wire_add',{**keys,'idempotencyKey':'wire-add-happy'})
            assert result['independentReopenVerified'] and result['expectedDefinitionsVerified'] and result['expectedConnectionObjectsVerified']
            assert result['addedAliasOwnerNetVerified'] and result['observedAliasOwnerNet']=='MCP_MIDDLE'
            output=await call('capture_open_edit_result',{**keys,'kind':'wire_add'})
            check=await call('capture_compare_connections',{'sessionId':output['sessionId'],'expectedRevision':output['revision'],
                'expectations':expected,'expectationSource':'original-series-resistor-four-pin-spec@1'})
            assert check['comparisonStatus']=='pass' and check['matchedPinCount']==4
            report['happy']={'plan':plan,'result':result,'comparison':check};report['checks']['native_mcp_save_reopen']=True
            cancelled=await call('capture_plan_wire_add',args);cancel_keys={k:cancelled[k] for k in ('planId','planDigest')}
            await call('capture_cancel_wire_add',cancel_keys)
            assert (await client.call_tool('capture_apply_wire_add',{**cancel_keys,'idempotencyKey':'cancelled-wire'})).is_error
            report['checks']['pending_cancel_no_apply']=True
            wrong=[{**p,'connected':False,'net':None} for p in expected]
            bad=await call('capture_plan_wire_add',{**args,'expectedConnections':wrong});bad_keys={k:bad[k] for k in ('planId','planDigest')}
            failed=await client.call_tool('capture_apply_wire_add',{**bad_keys,'idempotencyKey':'wrong-topology'})
            assert failed.is_error and failed.structured_content['error']['code']=='unexpected_connectivity_change',failed.content
            assert (await client.call_tool('capture_open_edit_result',{**bad_keys,'kind':'wire_add'})).is_error
            replay=await client.call_tool('capture_apply_wire_add',{**bad_keys,'idempotencyKey':'wrong-topology'})
            assert replay.is_error and replay.structured_content['error']['code']=='write_not_replayed'
            report['checks']['wrong_expected_topology_refused_after_save_no_replay']=True
            jobs=[];offset=0
            while True:
                row=await call('capture_wire_add_jobs',{'offset':offset,'limit':1});jobs+=row['jobs'];offset=row['nextOffset']
                if offset is None:break
            assert sorted(j['state'] for j in jobs)==['cancelled','failed','verified']
            assert (await client.call_tool('capture_plan_wire_add',{**args,'eval':'bad'})).is_error
            report['checks']['durable_job_pagination_and_strict_args']=True
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            replay=await fresh.call_tool('capture_apply_wire_add',{**keys,'idempotencyKey':'wire-add-happy'})
            assert not replay.is_error and replay.structured_content['data']['mutationReplayed'] is False
            output=await fresh.call_tool('capture_open_edit_result',{**keys,'kind':'wire_add'})
            assert not output.is_error
            report['checks']['fresh_server_idempotence_and_open_output']=True
        report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        report['sourceHashAfter']=sha256(source)
        if report['sourceHashAfter']!=report['sourceHashBefore']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'tools':report['toolCount'],'checks':report['checks'],'report':str(root/'report.json')}))
asyncio.run(main())
