"""Controlled termination, only after a fresh native inventory proves test-only clean state."""
import argparse
import asyncio
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.bridge_rpc import GuiBridgeManager,RpcConnection,process_image
from cadence_mcp.core import CadenceError,Config,sha256
from cadence_mcp.gui_property import GuiPropertyWriter

def terminate_verified(pid,executable,inventory_time):
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
    kernel.GetProcessTimes.argtypes=[w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)]
    kernel.TerminateProcess.argtypes=[w.HANDLE,w.UINT];kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
    handle=kernel.OpenProcess(0x1000|0x0001|0x00100000,False,pid)
    if not handle:raise OSError('Cannot open verified test process')
    try:
        buf=c.create_unicode_buffer(32768);size=w.DWORD(len(buf))
        assert kernel.QueryFullProcessImageNameW(handle,0,buf,c.byref(size))
        assert Path(buf.value).resolve()==executable.resolve()
        created=w.FILETIME();exited=w.FILETIME();k=w.FILETIME();u=w.FILETIME()
        assert kernel.GetProcessTimes(handle,c.byref(created),c.byref(exited),c.byref(k),c.byref(u))
        created_ms=((created.dwHighDateTime<<32)|created.dwLowDateTime)//10000-11644473600000
        assert created_ms<inventory_time and 0<=time.time()*1000-inventory_time<5000
        assert kernel.TerminateProcess(handle,0xC0000005)
        assert kernel.WaitForSingleObject(handle,5000)==0
    finally:kernel.CloseHandle(handle)

async def main(args):
    binding=json.loads(args.binding.read_text(encoding='utf-8'));design=Path(binding['expectedDesign'])
    inventory_before=json.loads(args.allowed_inventory.read_text(encoding='utf-8'))
    allowed={Path(r['path']).resolve() for r in inventory_before['designs']}
    assert allowed and all(p.is_relative_to(args.test_root.resolve()) for p in allowed)
    armed=json.loads((args.output/'armed.json').read_text(encoding='utf-8'));assert armed['pid']==binding['expectedPid']
    manager=GuiBridgeManager((args.binding,));instance=manager.discover()['instances'][0]
    attached=manager.attach(instance['instanceId'],'write')
    writer=GuiPropertyWriter(manager,Config(args.install_root,args.output/'work',(design.parent,),60,args.binding))
    preview=writer.plan(attached['sessionId'],'FULLADD','FULLADD','U1','Crash receipt verification '+str(time.time_ns()))
    original=RpcConnection.call
    def lose_reply(self,operation,params,**kwargs):
        result=original(self,operation,params,**kwargs)
        if operation=='property.apply':raise CadenceError('bridge_unavailable','Fixture: discard save receipt before termination')
        return result
    with patch.object(RpcConnection,'call',lose_reply):
        try:writer.apply(preview['plan']['planId'],preview['planDigest'],'crash-save-receipt')
        except CadenceError as error:assert error.code=='bridge_unavailable'
        else:raise AssertionError('Receipt loss not observed')
    (args.output/'inventory-request.json').write_text('{}',encoding='utf-8')
    end=time.monotonic()+10
    while not (args.output/'crash-inventory.json').exists():
        if (args.output/'inventory-error.json').exists():raise AssertionError('Native inventory failed')
        if time.monotonic()>end:raise TimeoutError('No native safety inventory')
        time.sleep(.05)
    inventory=json.loads((args.output/'crash-inventory.json').read_text(encoding='utf-8'))
    assert inventory['pid']==binding['expectedPid']
    assert {Path(r['path']).resolve() for r in inventory['designs']}==allowed
    assert all(r['dirty'] is False for r in inventory['designs']+inventory['libraries'])
    files={str(p):sha256(p) for p in allowed}
    assert process_image(inventory['pid'])==Path(binding['expectedExecutable']).resolve()
    terminate_verified(inventory['pid'],Path(binding['expectedExecutable']),inventory['timeMs'])
    assert all(sha256(Path(p))==fingerprint for p,fingerprint in files.items())
    params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(args.install_root),
        '--workspace-root',str(args.output/'new-server'),'--read-root',str(design.parent),'--gui-bridge-config',str(args.binding)],env=dict(os.environ))
    async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
        instances=(await client.call_tool('capture_gui_instances',{})).structured_content['data'];assert not instances['instances']
        jobs=(await client.call_tool('capture_gui_jobs',{})).structured_content['data']['jobs']
        assert any(j['planId']==preview['plan']['planId'] and j['state']=='started' for j in jobs)
        result=await client.call_tool('capture_gui_recover_note',{'planId':preview['plan']['planId'],'planDigest':preview['planDigest']})
        assert result.is_error,result.structured_content
        assert (design.parent/'.cadence-mcp-write.lock').exists()
    assert all(sha256(Path(p))==fingerprint for p,fingerprint in files.items())
    report={'terminatedPid':inventory['pid'],'testOnlyCleanDesigns':len(allowed),'cleanLibraries':len(inventory['libraries']),
        'mutationReceiptLost':True,'startedJobSurvived':True,'deadInstanceNotDiscovered':True,
        'recoveryRefusedWithoutNativeReceipt':True,'writeLockPreserved':True,'mutationReplayed':False,
        'planId':preview['plan']['planId'],'planDigest':preview['planDigest'],'fingerprints':files,
        'oldBinding':str(args.binding),'terminationMode':'controlled abrupt termination, exit code 0xC0000005'}
    (args.output/'crash-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--install-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allowed-inventory',type=Path,required=True);parser.add_argument('--test-root',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
