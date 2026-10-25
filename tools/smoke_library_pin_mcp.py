"""Actual MCP library pin edits and strict durable lifecycle acceptance."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','created-library-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);created=a.created_library_root.resolve()
prior=json.loads((created/'report.json').read_text(encoding='utf-8'));sources={c['name']:created/'work/isolated-jobs/capture_library_create'/('plan-'+c['plan']['planId'])/'library.olb' for c in prior['cases'] if c['name'] in ('resistor','homogeneous_shared','heterogeneous_power')}
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),*sum([['--read-root',str(p.parent)] for p in sources.values()],[]),'--timeout-seconds','60'],env=env)
cases=[{'source':'resistor','changes':{'name':'A $[x];中文','number':'101','pinType':0},'affected':1},
       {'source':'homogeneous_shared','changes':{'name':'INPUT_NEW'},'affected':2},
       {'source':'heterogeneous_power','changes':{'name':'A_ONLY'},'affected':1}]
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
    report={'passed':False,'cases':[],'sourceHashesBefore':{k:sha256(p) for k,p in sources.items()},'checks':{}}
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
            for i,fixture in enumerate(cases):
                opened=await call('capture_library_open',{'sourceLibrary':str(sources[fixture['source']])});lid=opened['libraryId']
                pins=(await call('capture_library_query',{'libraryId':lid,'entity':'pin','limit':1000}))['items'];target=next(p for p in pins if p['position']==0)
                plan=await call('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],**fixture['changes']});key={k:plan[k] for k in ('planId','planDigest')}
                assert len(plan['preview']['affected'])==fixture['affected']
                result=await call('capture_apply_library_pin_edit',{**key,'idempotencyKey':'edit-'+str(i)})
                output=await call('capture_open_edited_library',key);observed=(await call('capture_library_query',{'libraryId':output['libraryId'],'entity':'pin','limit':1000}))['items']
                assert sum(p['name']==fixture['changes']['name'] for p in observed)==fixture['affected']
                if i==0:assert any(p['number']=='101' and p['pinType']==0 and p['name']==fixture['changes']['name'] for p in observed)
                assert not result['sourceModified'] and not result['designCacheUpdated'] and result['verificationScope']=='library_device_definitions'
                report['cases'].append({'fixture':fixture,'plan':plan,'result':result,'opened':output,'idempotencyKey':'edit-'+str(i)})
                pending=await call('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],'name':'PENDING'});pk={k:pending[k] for k in ('planId','planDigest')}
                await call('capture_cancel_library_pin_edit',pk);await call('capture_apply_library_pin_edit',{**pk,'idempotencyKey':'cancel-'+str(i)},'write_not_replayed')
                if fixture['source']=='heterogeneous_power':
                    shared=next(p for p in pins if p['position']==2 and p['shared'])
                    await call('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':shared['objectId'],'pinType':0},'shared_pin_function_conflict')
                    await call('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],'number':'3'},'pad_number_conflict')
                assert (await client.call_tool('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],'pinType':True})).is_error
                assert (await client.call_tool('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],'name':'OK','eval':'x'})).is_error
                print(json.dumps({'source':fixture['source'],'passed':True}),flush=True)
            assert len((await call('capture_library_pin_edit_jobs',{}))['jobs'])==6
            report['toolCount']=len(tools);report['checks'].update(strict_schemas=True,shared_affected_rows=True,unicode_literal=True,pad_and_function_conflicts_refused=True,pending_cancel=True,jobs=True)
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            for row in report['cases']:
                key={k:row['plan'][k] for k in ('planId','planDigest')}
                result=await fresh.call_tool('capture_apply_library_pin_edit',{**key,'idempotencyKey':row['idempotencyKey']});assert not result.is_error and result.structured_content['data']['artifact']['sha256']==row['result']['artifact']['sha256']
                opened=await fresh.call_tool('capture_open_edited_library',key);assert not opened.is_error
                recovered=await fresh.call_tool('capture_recover_library_pin_edit',key);assert not recovered.is_error
            last=report['cases'][-1];target=root/'work'/last['result']['outputWorkspaceRelativePath']/'library.olb';target.write_bytes(target.read_bytes()+b'owned edited-OLB tamper negative')
            result=await fresh.call_tool('capture_open_edited_library',{k:last['plan'][k] for k in ('planId','planDigest')});assert result.is_error and result.structured_content['error']['code']=='target_changed'
        report['checks'].update(fresh_server_no_replay=True,recover_and_open=True,tamper_refused=True);report['passed']=True
    except BaseException as error:report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    finally:
        report['sourceHashesAfter']={k:sha256(p) for k,p in sources.items()}
        if report['sourceHashesBefore']!=report['sourceHashesAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','toolCount','checks','error')}));return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
