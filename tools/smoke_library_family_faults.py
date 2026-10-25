import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates
from cadence_mcp.environment import process_env
import subprocess
from library_create_fixtures import specs
p=argparse.ArgumentParser();p.add_argument('--spec-file',type=Path,required=True)
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);readroot=root/'inputs';readroot.mkdir();repo=Path(__file__).resolve().parents[1]
config=Config(a.install_root.resolve(strict=True),root/'work',(readroot,),60);creator=LibraryCreates(config,LibraryService(config));spec=json.loads(a.spec_file.read_text(encoding='utf-8'))['two_footprints'];(root/'expected.json').write_text(json.dumps(spec,indent=2));native=creator.execute
report={'passed':False,'checks':{}};calls=0
async def main():
    global calls
    try:
        plan=creator.plan(spec);key={k:plan[k] for k in ('planId','planDigest')};report['lostPlan']=plan
        def lose_receipt(directory,p,cancel,started):
            global calls
            calls+=1;process=native(directory,p,cancel,started);assert process['state']=='exited' and process['returnCode']==0
            (directory/'native-result.json').unlink();return process
        creator.execute=lose_receipt
        try:creator.apply(key['planId'],key['planDigest'],'lost-receipt');raise AssertionError('Missing receipt accepted')
        except CadenceError as error:report['lostError']=error.code
        directory,_,row=creator._load(key['planId']);assert row['state']=='failed';report['lostProcess']=row['process'];before=sha256(directory/'library.olb')
        env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(config.install_root),'--workspace-root',str(config.workspace_root),'--read-root',str(readroot),'--timeout-seconds','60'],env=env)
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            async def call(name,args):
                r=await fresh.call_tool(name,args);assert not r.is_error,r.content
                return r.structured_content['data']
            result=await call('capture_recover_library_create',key);assert result['state']=='verified_recovered' and result['nativeCompletionVerified'] is False and result['mutationReplayed'] is False
            opened=await call('capture_open_created_library',key);pins=await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'pin'});assert pins['total']==4
            assert (await call('capture_apply_library_create',{**key,'idempotencyKey':'lost-receipt'}))['mutationReplayed'] is False
            report['recovered']=result
        assert calls==1 and before==sha256(directory/'library.olb');report['checks']['receipt_loss_fresh_mcp_recovery_no_replay']=True
        creator.execute=native;cancel=creator.plan(spec);cancel_key={k:cancel[k] for k in ('planId','planDigest')};report['cancelPlan']=cancel
        def stop_at_start(directory,p,event,started):
            def ready(pid):started(pid);assert creator.cancel(cancel_key['planId'],cancel_key['planDigest'])['cancelRequested']
            return native(directory,p,event,ready)
        creator.execute=stop_at_start
        try:creator.apply(cancel_key['planId'],cancel_key['planDigest'],'cancel-native');raise AssertionError('Native start cancel accepted as success')
        except CadenceError as error:assert error.code=='operation_cancelled',error.code
        process=creator._load(cancel_key['planId'])[2]['process'];assert process['remainingOwnedProcesses']==0;report['cancelProcess']=process;report['checks']['native_start_window_cancel']=True
        short=Config(config.install_root,config.workspace_root,(readroot,),1);timeout=LibraryCreates(short,LibraryService(short));planned=timeout.plan(spec);report['timeoutPlan']=planned
        try:timeout.apply(planned['planId'],planned['planDigest'],'native-timeout');raise AssertionError('Expected real one-second timeout')
        except CadenceError as error:assert error.code=='timeout',error.code
        process=timeout._load(planned['planId'])[2]['process'];assert process['state']=='timeout' and process['remainingOwnedProcesses']==0;report['timeoutProcess']=process;report['checks']['real_one_second_timeout']=True
        creator.execute=native
        altered=creator.plan(spec);altered_key={k:altered[k] for k in ('planId','planDigest')};report['alteredPlan']=altered
        def change_other_package(directory,p,event,started):
            process=native(directory,p,event,started);assert process['returnCode']==0
            child=subprocess.run([str(config.install_root/'tcltk/bin/tclsh.exe'),str(repo/'tools/fault_library_family_footprint.tcl'),str(config.install_root),str(directory/'library.olb'),spec['packages'][1]['packageName']],env=process_env(config),capture_output=True,timeout=60)
            (directory/'fault.stdout').write_bytes(child.stdout);(directory/'fault.stderr').write_bytes(child.stderr);assert child.returncode==0,child.stderr
            return process
        creator.execute=change_other_package
        try:creator.apply(altered_key['planId'],altered_key['planDigest'],'changed-second-package');raise AssertionError('Second package footprint corruption accepted')
        except CadenceError as error:assert error.code=='library_creation_mismatch',error.code
        try:creator.recover(altered_key['planId'],altered_key['planDigest']);raise AssertionError('Corrupt family recovered')
        except CadenceError as error:assert error.code=='library_creation_mismatch',error.code
        assert creator._load(altered_key['planId'])[2]['state']=='failed';report['checks']['second_package_native_footprint_corruption_refused']=True
        report['passed']=True
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    finally:(root/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}))
asyncio.run(main())
