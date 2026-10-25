"""Actual stdio acceptance of fixed part edit lifecycle and strict schemas."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','unbound-source','connected-source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
sources={'unbound':a.unbound_source,'connected':a.connected_source}
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),*sum([['--read-root',str(p)] for p in {p.parent for p in sources.values()}],[]),'--timeout-seconds','60'],env=env)
pins=[{'number':'1','name':'1','hotSpot':[340,410]},{'number':'2','name':'2','hotSpot':[380,410]}]
(root/'expected.json').write_text(json.dumps({'moveLocation':[350,400],'movePins':pins,'connectedSurvivor':['R102','1','MCP_MIDDLE']},indent=2),encoding='utf-8')
async def main():
    report={'passed':False,'checks':{},'cases':[],'sourceHashesBefore':{k:sha256(p) for k,p in sources.items()}}
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
            for source_name,operation in [('unbound','set_pose'),('connected','delete')]:
                ws=await call('cadence_create_workspace',{'sourceDesign':str(sources[source_name])});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
                parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];target=next(p for p in parts if p['reference']=='R101')
                args={'sessionId':sid,'partId':target['objectId'],'operation':operation,'expectedConnections':[]}
                for ref in (['R102'] if operation=='delete' else ['R101','R102']):
                    for num in ('1','2'):
                        bound=source_name=='connected' and ref=='R102' and num=='1'
                        args['expectedConnections'].append({'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':ref,'pinNumber':num,'connected':bound,'net':'MCP_MIDDLE' if bound else None})
                if operation=='set_pose':args.update(location=[350,400],rotation=0,mirror=0,expectedPins=pins)
                plan=await call('capture_plan_part_edit',args);key={k:plan[k] for k in ('planId','planDigest')};idem='mcp-'+source_name
                result=await call('capture_apply_part_edit',{**key,'idempotencyKey':idem})
                output=await call('capture_open_edit_result',{**key,'kind':'part_edit'})
                assert result['pageGeometryVerified'] and result['expectedDefinitionsVerified'] and not result['sourceModified']
                assert output['counts']['part']==opened['counts']['part']-(operation=='delete')
                assert (await call('capture_recover_part_edit',key))['artifact']['sha256']==result['artifact']['sha256']
                report['cases'].append({'operation':operation,'plan':plan,'result':result,'output':output,'idempotencyKey':idem})
                pending=await call('capture_plan_part_edit',args);pk={k:pending[k] for k in ('planId','planDigest')}
                await call('capture_cancel_part_edit',pk);await call('capture_apply_part_edit',{**pk,'idempotencyKey':'cancel-'+source_name},'write_not_replayed')
                if operation=='set_pose':
                    for bad in ({**args,'rotation':True},{**args,'extra':'eval'},{**args,'expectedPins':pins[:1]}):assert (await client.call_tool('capture_plan_part_edit',bad)).is_error
                print(json.dumps({'operation':operation,'passed':True}),flush=True)
            assert len((await call('capture_part_edit_jobs',{}))['jobs'])>=4
            report.update(toolCount=len(tools));report['checks'].update(strict_schemas=True,move_and_delete_save_reopen=True,pending_cancel=True,jobs=True)
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            for row in report['cases']:
                key={k:row['plan'][k] for k in ('planId','planDigest')}
                result=await fresh.call_tool('capture_apply_part_edit',{**key,'idempotencyKey':row['idempotencyKey']})
                assert not result.is_error and result.structured_content['data']['artifact']['sha256']==row['result']['artifact']['sha256']
                output=await fresh.call_tool('capture_open_edit_result',{**key,'kind':'part_edit'});assert not output.is_error
            last=report['cases'][-1];target=root/'work'/last['result']['outputWorkspaceRelativePath']/'design.dsn'
            target.write_bytes(target.read_bytes()+b'owned part-edit tamper negative')
            result=await fresh.call_tool('capture_open_edit_result',{**{k:last['plan'][k] for k in ('planId','planDigest')},'kind':'part_edit'})
            assert result.is_error and result.structured_content['error']['code']=='target_changed'
        report['checks'].update(fresh_server_no_replay=True,output_hash_tamper_rejected=True);report['passed']=True
    except BaseException as error:report.update(errorType=type(error).__name__,error=str(error))
    finally:
        report['sourceHashesAfter']={k:sha256(p) for k,p in sources.items()}
        if report['sourceHashesBefore']!=report['sourceHashesAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','sourceHashesBefore','sourceHashesAfter')},ensure_ascii=False))
    return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
