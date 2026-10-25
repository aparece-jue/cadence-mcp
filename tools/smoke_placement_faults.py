"""Real placement receipt loss/MCP recovery, start cancellation and delayed timeout."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.capture import CaptureService
from cadence_mcp.library import LibraryService
from cadence_mcp.capture_place import CapturePlacements
from cadence_mcp.core import Config,CadenceError,sha256

p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source','library'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
repo=Path(__file__).resolve().parents[1];source=a.source.resolve(strict=True);olb=a.library.resolve(strict=True)
config=Config(a.install_root.resolve(strict=True),root/'work',(source.parent,olb.parent),60)
capture=CaptureService(config);library=LibraryService(config);writer=CapturePlacements(config,capture,library)
pins=[{'number':'1','name':'1','hotSpot':[690,310],'connected':False,'net':None},{'number':'2','name':'2','hotSpot':[730,310],'connected':False,'net':None}]
existing=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':r,'pinNumber':n,'connected':False,'net':None} for r in ('R101','R102') for n in ('1','2')]
report={'passed':False,'createdAt':datetime.now(timezone.utc).isoformat(),'checks':{},'sourceHashBefore':sha256(source),'libraryHashBefore':sha256(olb)}
try:
    ws=capture.create_workspace(str(source));sid=capture.open(ws['workspaceId'])['sessionId']
    page=next(p for p in capture.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE')
    lid=library.open(str(olb))['libraryId'];data=library.sessions[lid]['data']
    package=next(p for p in data['package'] if p['name']=='R');part=next(p for p in data['part'] if p['packageId']==package['objectId'])
    def plan(target=writer):return target.plan(sid,page['objectId'],lid,part['objectId'],'R103',[700,300],0,0,'2k',pins,existing)
    execute=writer.execute;calls=0;lost=plan()
    def lose(directory,payload,cancel,started):
        global calls
        calls+=1;result=execute(directory,payload,cancel,started)
        assert result['state']=='exited' and result['returnCode']==0
        (directory/'native-result.json').unlink()
        return result
    writer.execute=lose
    try:writer.apply(lost['planId'],lost['planDigest'],'lost-placement');raise AssertionError('Missing receipt accepted')
    except CadenceError:assert writer._load(lost['planId'])[2]['state']=='failed'
    directory=writer._load(lost['planId'])[0];saved_hash=sha256(directory/'design.dsn')
    async def recover():
        env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
        params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(config.install_root),
            '--workspace-root',str(config.workspace_root),'--read-root',str(source.parent),'--read-root',str(olb.parent),'--timeout-seconds','60'],env=env)
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            keys={k:lost[k] for k in ('planId','planDigest')}
            response=await client.call_tool('capture_recover_placement',keys);assert not response.is_error,response.content
            output=await client.call_tool('capture_open_edit_result',{**keys,'kind':'placement'});assert not output.is_error,output.content
            return response.structured_content['data']
    result=asyncio.run(recover())
    assert result['state']=='verified_recovered' and not result['nativeCompletionVerified'] and not result['mutationReplayed']
    assert calls==1 and sha256(directory/'design.dsn')==saved_hash
    report['recovered']=result;report['checks']['fresh_mcp_recover_and_open_no_replay']=True
    writer.execute=execute;cancelled=plan()
    def cancel_start(directory,payload,cancel,started):
        def on_started(pid):started(pid);assert writer.cancel(cancelled['planId'],cancelled['planDigest'])['cancelRequested']
        return execute(directory,payload,cancel,on_started)
    writer.execute=cancel_start
    try:writer.apply(cancelled['planId'],cancelled['planDigest'],'cancel-placement');raise AssertionError('Cancel ignored')
    except CadenceError as error:assert error.code=='operation_cancelled'
    row=writer._load(cancelled['planId'])[2];assert row['state']=='cancelled' and row['process']['remainingOwnedProcesses']==0
    report['cancelledProcess']=row['process'];report['checks']['native_start_cancel']=True
    slow_config=Config(config.install_root,config.workspace_root,config.read_roots,1)
    slow=CapturePlacements(slow_config,capture,library);timed=plan(slow)
    adapter=root/'delayed-adapter';adapter.mkdir()
    (adapter/'edit_place.tcl').write_text('set production [lindex $argv end]\nset argv [lrange $argv 0 end-1]\nset argc [llength $argv]\nafter 2000\nsource $production\n',encoding='utf-8')
    # Append the production script path in a test-only wrapper, then restore
    # production argv before the deliberate delay; no production input hook.
    from cadence_mcp.environment import process_env
    from cadence_mcp.process_tree import run_owned_process
    def delayed(directory,payload,cancel,started):
        # Reuse the real copy/argv builder, replacing only its process launcher.
        def launch(argv,cwd,env,timeout_seconds,**kw):
            original_script=argv[1];argv=list(argv);argv[1]=adapter/'edit_place.tcl';argv.append(original_script)
            return run_owned_process(argv,cwd,env,timeout_seconds,**kw)
        with patch('cadence_mcp.capture_place.run_owned_process',side_effect=launch):
            return CapturePlacements.execute(slow,directory,payload,cancel,started)
    slow.execute=delayed
    try:slow.apply(timed['planId'],timed['planDigest'],'timeout-placement');raise AssertionError('Timeout ignored')
    except CadenceError as error:assert error.code=='timeout'
    row=slow._load(timed['planId'])[2];assert row['state']=='failed' and row['process']['state']=='timeout' and row['process']['remainingOwnedProcesses']==0
    report['timeoutProcess']=row['process'];report['checks']['deliberately_delayed_worker_timeout']=True
    assert sha256(capture.sessions[sid]['design'])==report['sourceHashBefore']
    assert sha256(library.sessions[lid]['directory']/'library.olb')==report['libraryHashBefore']
    report['passed']=True
except BaseException as error:report['error']=str(error);raise
finally:
    report.update(sourceHashAfter=sha256(source),libraryHashAfter=sha256(olb))
    if report['sourceHashBefore']!=report['sourceHashAfter'] or report['libraryHashBefore']!=report['libraryHashAfter']:report['passed']=False
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'checks':report['checks'],'report':str(root/'report.json')}))
