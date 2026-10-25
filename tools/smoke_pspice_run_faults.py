"""Actual native receipt loss + fresh MCP recovery, and launch-window cancel."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_runs import PSpiceRuns
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);sources=root/'source';sources.mkdir();repo=Path(__file__).resolve().parents[1]
source=sources/'dc.cir';source.write_text('* independent fault fixture\nV1 1 0 DC 5\nR1 1 2 1k\nR2 2 0 1k\n.DC V1 5 5 1\n.PROBE\n.END\n')
config=Config(a.install_root.resolve(strict=True),root/'work',(sources,),60);inputs=PSpiceInputs(config);writer=PSpiceRuns(config,inputs,PSpiceDat(config))
sid=inputs.prepare(str(source))['simulationId'];expected=[{'block':0,'row':0,'traceName':'V(2)','real':2.5,'imaginary':None,'absoluteTolerance':1e-6,'relativeTolerance':0.0}]
(root/'expected.json').write_text(json.dumps(expected,indent=2))
report={'passed':False,'sourceHashBefore':sha256(source),'checks':{}};native=writer.execute;calls=0
async def main():
    global calls
    try:
        plan=writer.plan(sid,'dc',expected);key={k:plan[k] for k in ('planId','planDigest')};report['lostReceiptPlan']=plan
        def lose_receipt(directory,p,cancel,started):
            global calls
            calls+=1;process=native(directory,p,cancel,started)
            assert process['state']=='exited' and process['returnCode']==0 and process['remainingOwnedProcesses']==0
            (directory/'receipt.json').unlink();return process
        writer.execute=lose_receipt
        try:writer.apply(**{'plan_id':key['planId'],'plan_digest':key['planDigest'],'idempotency_key':'lost-receipt'});raise AssertionError('Missing receipt accepted')
        except CadenceError as error:report['lostReceiptError']=error.code
        directory,_,row=writer._load(key['planId']);assert row['state']=='failed';report['lostReceiptProcess']=row['process']
        hashes={name:sha256(directory/name) for name in ('result.out','result.dat')}
        env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
        params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(config.install_root),'--workspace-root',str(config.workspace_root),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            async def call(name,args):
                r=await fresh.call_tool(name,args);assert not r.is_error,r.content
                return r.structured_content['data']
            recovered=await call('pspice_recover_run',key);report['recovered']=recovered
            assert recovered['state']=='verified_recovered' and recovered['nativeCompletionVerified'] is False and recovered['numericalAcceptanceVerified'] and recovered['mutationReplayed'] is False
            data=await call('pspice_open_run_dat',key);assert data['jobAssociationVerified']
            sample=await call('pspice_dat_samples',{'datId':data['datId'],'block':0,'traceName':'V(2)','offset':0,'limit':1})
            assert sample['jobAssociationVerified'] and abs(sample['items'][0]['real']-2.5)<=1e-6
            reused=await call('pspice_apply_run',{**key,'idempotencyKey':'lost-receipt'});assert reused['mutationReplayed'] is False
        assert calls==1 and hashes=={name:sha256(directory/name) for name in hashes}
        report['checks']['actual_native_receipt_loss_fresh_mcp_recovery_without_replay']=True
        writer.execute=native;pending=writer.plan(sid,'dc',expected);cancel_key={k:pending[k] for k in ('planId','planDigest')};report['cancelPlan']=pending
        def cancel_start(directory,p,cancel,started):
            def ready(pid):
                started(pid);result=writer.cancel(cancel_key['planId'],cancel_key['planDigest']);assert result['cancelRequested']
            return native(directory,p,cancel,ready)
        writer.execute=cancel_start
        try:writer.apply(cancel_key['planId'],cancel_key['planDigest'],'native-start-cancel');raise AssertionError('Started native worker was not cancelled')
        except CadenceError as error:assert error.code=='operation_cancelled',error.code
        _,_,row=writer._load(cancel_key['planId']);assert row['state']=='cancelled' and row['process']['remainingOwnedProcesses']==0
        report['cancelProcess']=row['process'];report['checks']['real_owned_native_launch_window_cancel']=True
        report['passed']=True
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    finally:
        report['sourceHashAfter']=sha256(source)
        if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}))
asyncio.run(main())
