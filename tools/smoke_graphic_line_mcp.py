"""Real stdio decorative-line lifecycle; checks do not infer electrical connections from geometry."""
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
async def main():
    report={'passed':False,'phase':'open','sourceHashBefore':sha256(source),'checks':{}}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;assert len(tools)==75
            schemas={t.name:t.output_schema for t in tools}
            for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,values):
                r=await client.call_tool(name,values);assert not r.is_error,r.content
                Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
            ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
            page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE')
            base={'sessionId':sid,'pageId':page['objectId'],'start':[330,310],'end':[490,310]}
            for change in [{'end':[330,310]},{'eval':'unsafe'}]:assert (await client.call_tool('capture_plan_graphic_line_add',{**base,**change})).is_error
            report['checks']['degenerate_and_extra_parameters_rejected']=True;report['phase']='apply'
            plan=await call('capture_plan_graphic_line_add',base);key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
            result=await call('capture_apply_graphic_line_add',{**key,'idempotencyKey':'graphic-happy'});report['result']=result
            assert result['independentReopenVerified'] and result['definitionAndConnectionBaselinePreserved'] and result['designPassed'] is None
            output=await call('capture_open_edit_result',{**key,'kind':'graphic_line'});assert output['producedByPlan']==key['planId']
            report['checks']['save_reopen_output']=True
            pending=await call('capture_plan_graphic_line_add',base);pending_key={k:pending[k] for k in ('planId','planDigest')}
            await call('capture_cancel_graphic_line_add',pending_key)
            assert (await client.call_tool('capture_apply_graphic_line_add',{**pending_key,'idempotencyKey':'cancel'})).is_error
            report['checks']['pending_cancel']=True
            report['jobs']=await call('capture_graphic_line_jobs',{'offset':0,'limit':1})
            # A second saved artifact exercises success recheck on a fresh server.
            recovery=await call('capture_plan_graphic_line_add',{**base,'start':[330,410],'end':[490,410]});recover_key={k:recovery[k] for k in ('planId','planDigest')};report['recoveryPlan']=recovery
            recover_result=await call('capture_apply_graphic_line_add',{**recover_key,'idempotencyKey':'graphic-recover'});report['initialRecoveryResult']=recover_result
        report['phase']='fresh_server'
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            r=await fresh.call_tool('capture_apply_graphic_line_add',{**key,'idempotencyKey':'graphic-happy'});assert not r.is_error
            reused=r.structured_content['data'];assert reused['artifact']['sha256']==result['artifact']['sha256'] and reused['mutationReplayed'] is False
            assert not (await fresh.call_tool('capture_open_edit_result',{**key,'kind':'graphic_line'})).is_error
            # Recovery after persisted success checks artifact again, without deleting a success receipt or replaying.
            r=await fresh.call_tool('capture_recover_graphic_line_add',recover_key);assert not r.is_error,r.content
            recovered=r.structured_content['data'];report['recovered']=recovered
            assert recovered['artifact']['sha256']==recover_result['artifact']['sha256']
            assert not (await fresh.call_tool('capture_open_edit_result',{**recover_key,'kind':'graphic_line'})).is_error
            report['checks']['fresh_server_idempotency_and_success_recheck']=True
        report.update(passed=True,toolCount=75)
    except BaseException as error:
        import traceback
        report['error']=str(error);report['traceback']=traceback.format_exc()
    finally:
        report['sourceHashAfter']=sha256(source)
        if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'phase':report['phase'],'error':report.get('error'),'report':str(root/'report.json')}))
asyncio.run(main())
