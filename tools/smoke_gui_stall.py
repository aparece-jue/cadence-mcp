"""Real Capture fixture stall test; source fixture_stall_probe.tcl separately first."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.bridge_rpc import GuiBridgeManager
from cadence_mcp.core import CadenceError,Config,sha256
from cadence_mcp.gui_property import GuiPropertyWriter

def wait_file(path,seconds):
    end=time.monotonic()+seconds
    while not path.exists():
        if time.monotonic()>end:raise TimeoutError(path.name)
        time.sleep(.05)

async def main(args):
    binding=json.loads(args.binding.read_text(encoding='utf-8'));design=Path(binding['expectedDesign'])
    before=sha256(design);manager=GuiBridgeManager((args.binding,))
    instance=manager.discover()['instances'][0];attached=manager.attach(instance['instanceId'],'write')
    writer=GuiPropertyWriter(manager,Config(args.install_root,args.output/'work',(design.parent,),60,args.binding))
    preview=writer.plan(attached['sessionId'],'FULLADD','FULLADD','U1','MUST NOT BE APPLIED AFTER DEADLINE')
    (args.output/'ready.json').write_text('{}',encoding='utf-8')
    wait_file(args.output/'block-started.json',30)
    started=time.monotonic()
    try:writer.apply(preview['plan']['planId'],preview['planDigest'],'blocked-fixture-write')
    except CadenceError as error:
        code=error.code;assert code=='bridge_unavailable',code
    else:raise AssertionError('Blocked write unexpectedly completed')
    elapsed=time.monotonic()-started;assert 7<=elapsed<=11,elapsed
    try:manager.query(attached['sessionId'],'status')
    except CadenceError as error:assert error.code=='session_lost'
    else:raise AssertionError('Timed-out write session survived')
    wait_file(args.output/'block-ended.json',15)
    # Give the expired queued request a chance to be rejected, then prove no write.
    time.sleep(.2);assert before==sha256(design)
    params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(args.install_root),
        '--workspace-root',str(args.output/'new-server'),'--read-root',str(design.parent),'--gui-bridge-config',str(args.binding)],env=dict(os.environ))
    async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
        result=await client.call_tool('capture_gui_recover_note',{'planId':preview['plan']['planId'],'planDigest':preview['planDigest']})
        assert not result.is_error,result.structured_content
        recovered=result.structured_content['data'];assert recovered['disposition']=='not_applied'
        assert not (design.parent/'.cadence-mcp-write.lock').exists()
        found=(await client.call_tool('capture_gui_instances',{})).structured_content['data']['instances']
        fresh=(await client.call_tool('capture_gui_attach',{'instanceId':found[0]['instanceId']})).structured_content['data']
        assert fresh['sessionId']!=attached['sessionId']
        status=await client.call_tool('capture_gui_query',{'sessionId':fresh['sessionId'],'entity':'status'})
        assert not status.is_error,status.structured_content
    assert before==sha256(design)
    report={'guiBlockedSeconds':12,'clientTimeoutSeconds':round(elapsed,3),'errorCode':code,
            'oldSessionRejected':True,'lateRequestDidNotWrite':True,'freshServerRetiredUnstartedJob':recovered,
            'explicitNewSessionPassed':True,'fingerprintBefore':before,'fingerprintAfter':sha256(design)}
    (args.output/'stall-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--install-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
