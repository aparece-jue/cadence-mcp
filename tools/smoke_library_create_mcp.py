import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from library_create_fixtures import specs
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);readroot=root/'inputs';readroot.mkdir();repo=Path(__file__).resolve().parents[1]
cases=specs();special=copy.deepcopy(cases['resistor']);special['packageName']='MCP_测试';special['symbols'][0]['pins'][0]['name']='A $[x];中文';cases['unicode_literal']=special
for i,line in enumerate(cases['all_pin_types']['symbols'][0]['lines']):line.update(style=i,width=i%3)
cases['all_pin_types']['symbols'][0]['lines'].append({'start':[-5,-5],'end':[5,5],'style':4,'width':2})
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');expected_hash=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(readroot),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'phase':'start','cases':[],'checks':{}};keys=[]
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;assert len(tools)==88;schemas={t.name:t.output_schema for t in tools}
            for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,args):
                result=await client.call_tool(name,args);assert not result.is_error,result.content
                Draft202012Validator(schemas[name]).validate(result.structured_content);return result.structured_content['data']
            report['phase']='create'
            for name,spec in cases.items():
                case={'name':name,'passed':False};report['cases'].append(case)
                try:
                    plan=await call('capture_plan_library_create',{'spec':spec});key={k:plan[k] for k in ('planId','planDigest')};keys.append((name,key))
                    result=await call('capture_apply_library_create',{**key,'idempotencyKey':name});opened=await call('capture_open_created_library',key)
                    case.update(plan=plan,result=result,opened=opened)
                    pins=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'pin','packageName':spec['packageName'],'limit':1000}))['items']
                    physical=len({p['number'] for p in pins});assert physical==result['uniquePhysicalPadCount']
                    assert len(pins)==sum(len(d['mapping']) for d in spec['devices'])
                    if name=='unicode_literal':assert any(p['name']=='A $[x];中文' for p in pins)
                    case.update(passed=True,physicalPadCount=physical,logicalPinRows=len(pins))
                except BaseException as error:case['error']=str(error)
            assert all(c['passed'] for c in report['cases']),report['cases']
            report['phase']='negative'
            broken=copy.deepcopy(cases['resistor']);broken['devices'][0]['mapping']=broken['devices'][0]['mapping'][:1]
            assert (await client.call_tool('capture_plan_library_create',{'spec':broken})).is_error
            assert (await client.call_tool('capture_plan_library_create',{'spec':cases['resistor'],'eval':'unsafe'})).is_error
            wrong=copy.deepcopy(cases['resistor']);wrong['expectedHomogeneous']=False
            plan=await call('capture_plan_library_create',{'spec':wrong});key={k:plan[k] for k in ('planId','planDigest')}
            result=await client.call_tool('capture_apply_library_create',{**key,'idempotencyKey':'wrong-oracle'});assert result.is_error and result.structured_content['error']['code']=='library_creation_mismatch',result.content
            assert (await client.call_tool('capture_open_created_library',key)).is_error
            result=await client.call_tool('capture_apply_library_create',{**key,'idempotencyKey':'wrong-oracle'});assert result.is_error and result.structured_content['error']['code']=='write_not_replayed'
            report['checks']['complete_mapping_strict_schema_wrong_native_oracle_no_replay']=True
            pending=await call('capture_plan_library_create',{'spec':cases['resistor']});key={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_library_create',key)
            assert (await client.call_tool('capture_apply_library_create',{**key,'idempotencyKey':'pending-cancel'})).is_error
            report['jobs']=await call('capture_library_create_jobs',{'offset':0,'limit':1});report['checks']['pending_cancel_jobs']=True
        report['phase']='fresh_server'
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            for name,key in keys:
                r=await fresh.call_tool('capture_apply_library_create',{**key,'idempotencyKey':name});assert not r.is_error and r.structured_content['data']['mutationReplayed'] is False
                r=await fresh.call_tool('capture_open_created_library',key);assert not r.is_error
            name,key=keys[-1];target=root/'work/isolated-jobs/capture_library_create'/('plan-'+key['planId'])/'library.olb'
            with target.open('ab') as stream:stream.write(b'controlled-artifact-tamper')
            r=await fresh.call_tool('capture_apply_library_create',{**key,'idempotencyKey':name});assert r.is_error and r.structured_content['error']['code']=='target_changed'
            assert (await fresh.call_tool('capture_open_created_library',key)).is_error
            report['checks']['fresh_idempotency_open_and_hash_tamper_rejection']=True
        report['passed']=sha256(root/'expected.json')==expected_hash;report['toolCount']=88
    except BaseException as error:
        import traceback
        report.update(error=str(error)[:4000],traceback=traceback.format_exc()[-6000:])
    finally:(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'phase':report['phase'],'cases':[{k:c.get(k) for k in ('name','passed','error')} for c in report['cases']],'error':report.get('error'),'report':str(root/'report.json')},ensure_ascii=False))
asyncio.run(main())
