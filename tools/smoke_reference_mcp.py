"""Actual MCP connected two-resistor swap, conflict and durable lifecycle checks."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.source.parent),'--timeout-seconds','60'],env=env)
(root/'expected.json').write_text(json.dumps({'map':{'R101':'R102','R102':'R101'},'boundAfter':[['R102','2'],['R101','1']],'net':'MCP_MIDDLE','locationAfter':{'R102':[300,300],'R101':[500,300]}},indent=2),encoding='utf-8')
async def main():
    report={'passed':False,'sourceHashBefore':sha256(a.source),'checks':{}}
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
            ws=await call('cadence_create_workspace',{'sourceDesign':str(a.source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
            parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];ids={p['reference']:p['objectId'] for p in parts}
            await call('capture_plan_reference_map',{'sessionId':sid,'mappings':[{'partId':ids['R101'],'newReference':'R102'}]},'reference_conflict')
            repeated=next(p for p in parts if sum(q['reference']==p['reference'] for q in parts)>1)
            await call('capture_plan_reference_map',{'sessionId':sid,'mappings':[{'partId':repeated['objectId'],'newReference':repeated['reference'].rstrip('0123456789')+'98765'}]},'ambiguous_reference')
            mapping=[{'partId':ids['R101'],'newReference':'R102'},{'partId':ids['R102'],'newReference':'R101'}]
            assert (await client.call_tool('capture_plan_reference_map',{'sessionId':sid,'mappings':mapping,'eval':'x'})).is_error
            plan=await call('capture_plan_reference_map',{'sessionId':sid,'mappings':mapping});key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
            result=await call('capture_apply_reference_map',{**key,'idempotencyKey':'connected-swap'});report['result']=result
            output=await call('capture_open_edit_result',{**key,'kind':'reference'});assert output['counts']==opened['counts']
            page=next(p for p in (await call('capture_query',{'sessionId':output['sessionId'],'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'] if p['name']=='MCP_PLACE')
            pins=(await call('capture_query',{'sessionId':output['sessionId'],'entity':'pin','scope':{'kind':'page','pageId':page['objectId']},'limit':1000}))['items']
            assert {(p['reference'],p['number']) for p in pins if p['connected']}=={('R102','2'),('R101','1')}
            assert all(p['net']=='MCP_MIDDLE' for p in pins if p['connected'])
            for part in (await call('capture_query',{'sessionId':output['sessionId'],'entity':'part','scope':{'kind':'page','pageId':page['objectId']},'limit':1000}))['items']:
                geometry=await call('capture_get_part_geometry',{'sessionId':output['sessionId'],'partId':part['objectId']})
                assert geometry['location']=={'R102':[300,300],'R101':[500,300]}[part['reference']]
            pending=await call('capture_plan_reference_map',{'sessionId':sid,'mappings':mapping});pk={k:pending[k] for k in ('planId','planDigest')}
            await call('capture_cancel_reference_map',pk);await call('capture_apply_reference_map',{**pk,'idempotencyKey':'cancelled-map'},'write_not_replayed')
            assert len((await call('capture_reference_jobs',{}))['jobs'])==2
            report.update(toolCount=len(tools),opened=output);report['checks'].update(strict_schemas=True,conflicts_and_ambiguous_units_refused=True,physical_pin_net_and_pose_mapping=True,pending_cancel=True,jobs=True)
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            result2=await fresh.call_tool('capture_apply_reference_map',{**key,'idempotencyKey':'connected-swap'});assert not result2.is_error and result2.structured_content['data']['artifact']['sha256']==result['artifact']['sha256']
            recovered=await fresh.call_tool('capture_recover_reference_map',key);assert not recovered.is_error
            opened2=await fresh.call_tool('capture_open_edit_result',{**key,'kind':'reference'});assert not opened2.is_error
            target=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn';target.write_bytes(target.read_bytes()+b'owned reference map tamper negative')
            bad=await fresh.call_tool('capture_open_edit_result',{**key,'kind':'reference'});assert bad.is_error and bad.structured_content['error']['code']=='target_changed'
        report['checks'].update(fresh_server_no_replay=True,recover_and_open=True,tamper_rejected=True);report['passed']=True
    except BaseException as error:report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    finally:
        report['sourceHashAfter']=sha256(a.source)
        if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','toolCount','checks','error')}));return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
