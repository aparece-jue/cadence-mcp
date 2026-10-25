"""Verify creation lifecycle independently of the failed downstream wire check."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','prior-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);prior=a.prior_root.resolve()
old=json.loads((prior/'report.json').read_text(encoding='utf-8'));plan=old['plan'];key={k:plan[k] for k in ('planId','planDigest')}
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(prior/'work'),'--read-root',str(prior),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'checks':{},'originalPlan':plan,'downstreamWireAccepted':False}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
            for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,args,error=None):
                result=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(result.structured_content)
                if error:assert result.is_error and result.structured_content['error']['code']==error,result
                else:assert not result.is_error,result
                return result.structured_content['data']
            result=await call('capture_apply_design_create',{**key,'idempotencyKey':'new-core'});report['result']=result
            assert result['artifact']['sha256']==old['result']['artifact']['sha256'] and result['artifact']['sourceKind']=='new_design_spec'
            opened=await call('capture_open_edit_result',{**key,'kind':'design_create'});assert opened['counts']=={'schematic':1,'page':1,'part':0,'pin':0}
            for entity,expected in [('schematic','CORE'),('page','MAIN')]:
                rows=(await call('capture_query',{'sessionId':opened['sessionId'],'entity':entity,'scope':{'kind':'design'}}))['items'];assert len(rows)==1 and rows[0]['name']==expected
            await call('capture_apply_design_create',{**key,'idempotencyKey':'different-key'},'idempotency_conflict')
            recovered=await call('capture_recover_design_create',key);assert recovered['artifact']['sha256']==result['artifact']['sha256']
            await call('capture_plan_design_create',{'rootName':'根图','pageName':'PAGE'},'unsupported_design_encoding')
            await call('capture_plan_design_create',{'rootName':'../bad','pageName':'PAGE'},'invalid_document_name')
            assert (await client.call_tool('capture_plan_design_create',{'rootName':'ROOT','pageName':'PAGE','eval':'x'})).is_error
            pending=await call('capture_plan_design_create',{'rootName':'PENDING','pageName':'PAGE'});pk={k:pending[k] for k in ('planId','planDigest')}
            await call('capture_cancel_design_create',pk);await call('capture_apply_design_create',{**pk,'idempotencyKey':'new-pending'},'write_not_replayed')
            tamper=await call('capture_plan_design_create',{'rootName':'TAMPER','pageName':'PAGE'});tk={k:tamper[k] for k in ('planId','planDigest')}
            tr=await call('capture_apply_design_create',{**tk,'idempotencyKey':'new-tamper'});target=prior/'work'/tr['outputWorkspaceRelativePath']/'design.dsn'
            target.write_bytes(target.read_bytes()+b'owned new-design tamper negative')
            await call('capture_open_edit_result',{**tk,'kind':'design_create'},'target_changed')
            jobs=await call('capture_design_create_jobs',{});assert len(jobs['jobs'])>=4
            report.update(toolCount=len(tools),tamperPlan=tamper,pendingPlan=pending)
            report['checks'].update(strict_schemas=True,cached_creation_reopen=True,fresh_server_no_replay=True,
                source_kind_digest=True,root_page_names=True,invalid_names_and_extra_refused=True,
                pending_cancel=True,idempotency_conflict=True,verified_recover=True,tamper_refused=True,jobs=True)
        report['passed']=True
    except BaseException as error:report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','toolCount','checks','error')}));return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
