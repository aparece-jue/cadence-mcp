"""Real worker receipt loss and native-start cancellation; no mutation replay."""
import argparse,json,asyncio,os,sys
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from pathlib import Path
from datetime import datetime,timezone
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_wire import CaptureWireAdds
from cadence_mcp.core import Config,CadenceError,sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True)
config=Config(a.install_root.resolve(strict=True),root/'work',(source.parent,),60)
capture=CaptureService(config);writer=CaptureWireAdds(config,capture)
expected=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':r,'pinNumber':p,
    'connected':(r,p) in {('R101','2'),('R102','1')},'net':'MCP_MIDDLE' if (r,p) in {('R101','2'),('R102','1')} else None}
    for r in ('R101','R102') for p in ('1','2')]
report={'passed':False,'createdAt':datetime.now(timezone.utc).isoformat(),'checks':{},'sourceHashBefore':sha256(source)}
try:
    ws=capture.create_workspace(str(source));opened=capture.open(ws['workspaceId']);sid=opened['sessionId']
    page=next(p for p in capture.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE')
    def plan():return writer.plan(sid,page['objectId'],[330,310],[490,310],'MCP_MIDDLE',expected)
    execute=writer.execute;calls=0
    lost=plan()
    def lose(directory,payload,cancel,started):
        global calls
        calls+=1;process=execute(directory,payload,cancel,started)
        assert process['state']=='exited' and process['returnCode']==0
        (directory/'native-result.json').unlink()
        return process
    writer.execute=lose
    try:writer.apply(lost['planId'],lost['planDigest'],'lost-wire-receipt');raise AssertionError('Missing receipt accepted')
    except CadenceError:assert writer._load(lost['planId'])[2]['state']=='failed'
    directory=writer._load(lost['planId'])[0];before=sha256(directory/'design.dsn')
    async def recover_over_mcp():
        env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        parameters=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server',
            '--install-root',str(config.install_root),'--workspace-root',str(config.workspace_root),
            '--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
        async with Client(parameters,mode='legacy',read_timeout_seconds=90) as client:
            keys={key:lost[key] for key in ('planId','planDigest')}
            response=await client.call_tool('capture_recover_wire_add',keys)
            assert not response.is_error,response.content
            result=response.structured_content['data']
            opened=await client.call_tool('capture_open_edit_result',{**keys,'kind':'wire_add'})
            assert not opened.is_error,opened.content
            return result
    recovered=asyncio.run(recover_over_mcp())
    report['recoveryTransport']='fresh_stdio_mcp'
    report['checks']['mcp_recovery_output_opened']=True
    assert recovered['state']=='verified_recovered' and not recovered['nativeCompletionVerified'] and not recovered['mutationReplayed']
    assert calls==1 and sha256(directory/'design.dsn')==before
    report['recovered']=recovered;report['checks']['real_saved_output_receipt_loss_fresh_verify_no_replay']=True
    writer.execute=execute;cancelled=plan()
    def cancel_start(directory,payload,cancel,started):
        def on_started(pid):
            started(pid);assert writer.cancel(cancelled['planId'],cancelled['planDigest'])['cancelRequested']
        return execute(directory,payload,cancel,on_started)
    writer.execute=cancel_start
    try:writer.apply(cancelled['planId'],cancelled['planDigest'],'cancel-native-wire');raise AssertionError('Cancel not acknowledged')
    except CadenceError as error:assert error.code=='operation_cancelled'
    row=writer._load(cancelled['planId'])[2]
    assert row['state']=='cancelled' and row['process']['remainingOwnedProcesses']==0
    report['cancelledProcess']=row['process'];report['checks']['real_owned_worker_start_cancel']=True
    assert sha256(capture.sessions[sid]['design'])==report['sourceHashBefore']
    report['passed']=True
finally:
    report['sourceHashAfter']=sha256(source)
    if report['sourceHashAfter']!=report['sourceHashBefore']:report['passed']=False
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'checks':report['checks'],'report':str(root/'report.json')}))
