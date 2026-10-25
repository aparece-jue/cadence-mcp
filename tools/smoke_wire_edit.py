"""Native MCP endpoint/delete acceptance on the predeclared resistor fixture."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);repo=Path(__file__).resolve().parents[1]
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
expected=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':r,'pinNumber':n,'connected':False,'net':None} for r in ('R101','R102') for n in ('1','2')]
async def main():
    report={'passed':False,'sourceHashBefore':sha256(source),'checks':{},'cases':[]};keys=[]
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
            for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,values):
                r=await client.call_tool(name,values);assert not r.is_error,r.content
                Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
            ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
            page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE')
            wire=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','pageId':page['objectId']}))['items'][0]
            alias=(await call('capture_query_connections',{'sessionId':sid,'entity':'alias','pageId':page['objectId']}))['items'][0]
            base={'sessionId':sid,'wireId':wire['objectId'],'expectedConnections':expected}
            assert (await client.call_tool('capture_plan_wire_edit',{**base,'operation':'delete'})).is_error
            for operation in ('set_endpoints','delete'):
                values={**base,'operation':operation}
                if operation=='delete':values['removeAttachedAliases']=True
                else:values.update(start=[330,410],end=[490,410],aliasLocations=[{'aliasId':alias['objectId'],'location':[330,410]}])
                plan=await call('capture_plan_wire_edit',values);key={k:plan[k] for k in ('planId','planDigest')};keys.append(key)
                result=await call('capture_apply_wire_edit',{**key,'idempotencyKey':operation})
                opened=await call('capture_open_edit_result',{**key,'kind':'wire_edit'})
                result_page=next(p for p in (await call('capture_query',{'sessionId':opened['sessionId'],'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE')
                for entity in ('wire','alias'):
                    rows=await call('capture_query_connections',{'sessionId':opened['sessionId'],'entity':entity,'pageId':result_page['objectId']})
                    assert rows['total']==(0 if operation=='delete' else 1)
                report['cases'].append({'operation':operation,'plan':plan,'result':result})
            report['checks']['native_endpoints_and_delete_save_reopen']=True
            original=[{**p,'connected':(p['reference'],p['pinNumber']) in {('R101','2'),('R102','1')},'net':'MCP_MIDDLE' if (p['reference'],p['pinNumber']) in {('R101','2'),('R102','1')} else None} for p in expected]
            bad=await call('capture_plan_wire_edit',{**base,'operation':'delete','removeAttachedAliases':True,'expectedConnections':original});bad_key={k:bad[k] for k in ('planId','planDigest')}
            rejected=await client.call_tool('capture_apply_wire_edit',{**bad_key,'idempotencyKey':'wrong-oracle'})
            assert rejected.is_error and rejected.structured_content['error']['code']=='wire_edit_net_mismatch',rejected.content
            assert (await client.call_tool('capture_open_edit_result',{**bad_key,'kind':'wire_edit'})).is_error
            replay=await client.call_tool('capture_apply_wire_edit',{**bad_key,'idempotencyKey':'wrong-oracle'})
            assert replay.is_error and replay.structured_content['error']['code']=='write_not_replayed'
            pending=await call('capture_plan_wire_edit',{**base,'operation':'delete','removeAttachedAliases':True});pending_key={k:pending[k] for k in ('planId','planDigest')}
            await call('capture_cancel_wire_edit',pending_key)
            assert (await client.call_tool('capture_apply_wire_edit',{**pending_key,'idempotencyKey':'cancelled'})).is_error
            assert (await client.call_tool('capture_plan_wire_edit',{**base,'operation':'delete','removeAttachedAliases':True,'eval':'bad'})).is_error
            rows=[];offset=0
            while True:
                jobs=await call('capture_wire_edit_jobs',{'offset':offset,'limit':1});rows+=jobs['jobs'];offset=jobs['nextOffset']
                if offset is None:break
            assert sorted(j['state'] for j in rows)==['cancelled','failed','verified','verified']
            report['checks']['alias_ack_wrong_oracle_no_replay_cancel_jobs_strict_args']=True
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            for key,operation in zip(keys,('set_endpoints','delete')):
                result=await fresh.call_tool('capture_apply_wire_edit',{**key,'idempotencyKey':operation});assert not result.is_error and not result.structured_content['data']['mutationReplayed']
                assert not (await fresh.call_tool('capture_open_edit_result',{**key,'kind':'wire_edit'})).is_error
            report['checks']['fresh_server_verified_results_no_replay']=True
        report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        report['sourceHashAfter']=sha256(source)
        if report['sourceHashAfter']!=report['sourceHashBefore']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'tools':report['toolCount'],'checks':report['checks'],'report':str(root/'report.json')}))
asyncio.run(main())
