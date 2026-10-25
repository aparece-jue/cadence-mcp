"""Actual stdio persistent engine task acceptance, fixed self-authored fixtures."""
import argparse,asyncio,json,math,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=root/'sources';source.mkdir();repo=Path(__file__).resolve().parents[1]
(source/'dc.cir').write_text('* independent nested DC task\n.INC resistors.inc\nV1 1 0 DC 5\n.DC V1 5 5 1\n.PROBE\n.END\n',encoding='ascii')
(source/'resistors.inc').write_text('R1 1 2 1k\nR2 2 0 1k\n',encoding='ascii')
(source/'ac.cir').write_text('* independent RC AC task\nV1 IN 0 DC 0 AC 1\nR1 IN OUT 1k\nC1 OUT 0 1u\n.AC LIN 3 79.5774715 238.7324146\n.PROBE\n.END\n',encoding='ascii')
(source/'bad.cir').write_text('* intentional undefined output selector\nV1 IN 0 DC 5\nR1 IN OUT 1k\nR2 OUT 0 1k\n.DC V1 5 5 1\n.PRINT DC V(OUT)\n.PROBE V(OUT)\n.END\n',encoding='ascii')
expected={'dc':{'block':0,'row':0,'traceName':'V(2)','real':2.5,'absoluteTolerance':1e-6},'ac':{'block':0,'row':1,'traceName':'V(OUT)','real':0.5,'imaginary':-0.5,'absoluteTolerance':1e-6}}
(root/'expected.json').write_text(json.dumps(expected,indent=2))
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(source),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'phase':'start','checks':{},'cases':[],'sourceHashesBefore':{p.name:sha256(p) for p in source.iterdir()}};keys=[]
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;assert len(tools)==81;schemas={t.name:t.output_schema for t in tools}
            for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,args):
                r=await client.call_tool(name,args);assert not r.is_error,r.content
                Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
            prepared={}
            for name in ('dc','ac','bad'):prepared[name]=await call('pspice_prepare',{'sourceCircuit':str(source/(name+'.cir'))})
            report['phase']='native_happy'
            for name in ('dc','ac'):
                plan=await call('pspice_plan_run',{'simulationId':prepared[name]['simulationId'],'analysis':name,'expectedSamples':[expected[name]]});key={k:plan[k] for k in ('planId','planDigest')};keys.append((name,key))
                result=await call('pspice_apply_run',{**key,'idempotencyKey':'happy-'+name});assert result['jobAssociationVerified'] and result['numericalAcceptanceVerified']
                opened=await call('pspice_open_run_dat',key);assert opened['jobAssociationVerified'] and opened['producedByPlan']==key['planId'] and opened['solverSuccessVerified']
                sample=await call('pspice_dat_samples',{'datId':opened['datId'],'block':0,'traceName':expected[name]['traceName'],'offset':expected[name]['row'],'limit':1})
                assert sample['jobAssociationVerified'] and sample['producedByPlan']==key['planId']
                assert abs(sample['items'][0]['real']-expected[name]['real'])<=1e-6
                if name=='ac':assert abs(sample['items'][0]['imaginary']+0.5)<=1e-6
                assert (await client.call_tool('pspice_dat_open',{'sourceDat':str(root/'work/isolated-jobs/pspice_engine_run'/('plan-'+key['planId'])/'result.dat')})).is_error
                await call('pspice_dat_close',{'datId':opened['datId']})
                report['cases'].append({'analysis':name,'plan':plan,'result':result,'dat':opened,'sample':sample})
            report['checks']['fresh_dc_ac_closure_and_association']=True
            report['phase']='negative_oracles'
            wrong=await call('pspice_plan_run',{'simulationId':prepared['dc']['simulationId'],'analysis':'dc','expectedSamples':[{**expected['dc'],'real':3.0}]});wrong_key={k:wrong[k] for k in ('planId','planDigest')}
            r=await client.call_tool('pspice_apply_run',{**wrong_key,'idempotencyKey':'wrong-value'});assert r.is_error and r.structured_content['error']['code']=='simulation_expectation_mismatch',r.content
            assert (await client.call_tool('pspice_open_run_dat',wrong_key)).is_error
            r=await client.call_tool('pspice_apply_run',{**wrong_key,'idempotencyKey':'wrong-value'});assert r.is_error and r.structured_content['error']['code']=='write_not_replayed'
            report['checks']['real_solve_wrong_expectation_rejected_no_replay']=True
            bad=await call('pspice_plan_run',{'simulationId':prepared['bad']['simulationId'],'analysis':'dc'});bad_key={k:bad[k] for k in ('planId','planDigest')}
            r=await client.call_tool('pspice_apply_run',{**bad_key,'idempotencyKey':'bad-circuit'});assert r.is_error and r.structured_content['error']['code']=='pspice_output_error',r.content
            report['checks']['actual_solver_error_classified']=True
            pending=await call('pspice_plan_run',{'simulationId':prepared['dc']['simulationId'],'analysis':'dc'});pending_key={k:pending[k] for k in ('planId','planDigest')};await call('pspice_cancel_run',pending_key)
            assert (await client.call_tool('pspice_apply_run',{**pending_key,'idempotencyKey':'pending-cancel'})).is_error
            assert (await client.call_tool('pspice_plan_run',{'simulationId':prepared['dc']['simulationId'],'analysis':'dc','eval':'unsafe'})).is_error
            report['checks']['pending_cancel_and_strict_schema']=True
            timeout=await call('pspice_plan_run',{'simulationId':prepared['dc']['simulationId'],'analysis':'dc','timeoutSeconds':1});timeout_key={k:timeout[k] for k in ('planId','planDigest')}
            r=await client.call_tool('pspice_apply_run',{**timeout_key,'idempotencyKey':'timeout'});assert r.is_error and r.structured_content['error']['code']=='timeout',r.content
            row=json.loads((root/'work/isolated-jobs/pspice_engine_run'/('plan-'+timeout_key['planId'])/'plan.json').read_text());assert row['process']['remainingOwnedProcesses']==0 and row['process']['state']=='timeout'
            report['checks']['real_timeout_owned_zero']=True;report['timeout']=row['process']
            report['jobs']=await call('pspice_run_jobs',{'offset':0,'limit':1})
        report['phase']='fresh_server'
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            for name,key in keys:
                r=await fresh.call_tool('pspice_apply_run',{**key,'idempotencyKey':'happy-'+name});assert not r.is_error and r.structured_content['data']['mutationReplayed'] is False
                r=await fresh.call_tool('pspice_open_run_dat',key);assert not r.is_error and r.structured_content['data']['jobAssociationVerified']
            # Alter only an owned failed/success task DAT. A cached verified result must recheck it.
            name,key=keys[0];path=root/'work/isolated-jobs/pspice_engine_run'/('plan-'+key['planId'])/'result.dat'
            with path.open('ab') as stream:stream.write(b'controlled-tamper-negative')
            r=await fresh.call_tool('pspice_apply_run',{**key,'idempotencyKey':'happy-'+name});assert r.is_error and r.structured_content['error']['code']=='target_changed'
            assert (await fresh.call_tool('pspice_open_run_dat',key)).is_error
            report['checks']['fresh_server_idempotency_and_all_artifact_hashes']=True
        report.update(passed=True,toolCount=81)
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    finally:
        report['sourceHashesAfter']={p.name:sha256(p) for p in source.iterdir()}
        if report['sourceHashesBefore']!=report['sourceHashesAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'phase':report['phase'],'error':report.get('error'),'report':str(root/'report.json')}))
asyncio.run(main())
