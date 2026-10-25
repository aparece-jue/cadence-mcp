"""Script-only acceptance for job closure, concurrent diagnosis and repeated Capture operations."""
import argparse
import asyncio
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import statistics
import sys
import time
from mcp import Client
from jsonschema import Draft202012Validator
from cadence_mcp.core import Config,sha256
from cadence_mcp.server import create_server
from cadence_mcp.gui_loader import load

def resources(pid):
    size=c.c_size_t
    class Counters(c.Structure):
        _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD),('PeakWorkingSetSize',size),('WorkingSetSize',size),
            ('QuotaPeakPagedPoolUsage',size),('QuotaPagedPoolUsage',size),('QuotaPeakNonPagedPoolUsage',size),
            ('QuotaNonPagedPoolUsage',size),('PagefileUsage',size),('PeakPagefileUsage',size),('PrivateUsage',size)]
    kernel=c.WinDLL('kernel32',use_last_error=True);psapi=c.WinDLL('psapi',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.GetProcessHandleCount.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
    psapi.GetProcessMemoryInfo.argtypes=[w.HANDLE,c.POINTER(Counters),w.DWORD]
    handle=kernel.OpenProcess(0x1000|0x0010,False,pid)
    if not handle:raise OSError('Cannot sample process counters')
    try:
        count=w.DWORD();memory=Counters();memory.cb=c.sizeof(memory)
        if not kernel.GetProcessHandleCount(handle,c.byref(count)) or not psapi.GetProcessMemoryInfo(handle,c.byref(memory),memory.cb):
            raise OSError('Cannot read counters')
        return {'handles':count.value,'privateBytes':memory.PrivateUsage,'workingSetBytes':memory.WorkingSetSize}
    finally:kernel.CloseHandle(handle)

async def client_calls(client):
    tools=(await client.list_tools()).tools
    validators={tool.name:Draft202012Validator(tool.output_schema) for tool in tools}
    async def call(name,values,ok=True):
        result=await client.call_tool(name,values)
        validators[name].validate(result.structured_content)
        assert bool(result.is_error) is (not ok),(name,result.structured_content)
        return result.structured_content['data'] if ok else result.structured_content['error']
    return tools,call

async def main(args):
    args.output.mkdir(parents=True,exist_ok=True)
    old=json.loads(args.crash_report.read_text(encoding='utf-8'));old_binding=Path(old['oldBinding'])
    target=Path(json.loads(old_binding.read_text(encoding='utf-8'))['expectedDesign']);before=sha256(target)
    old_cfg=Config(args.install_root,args.output/'resolution-work',(target.parent,),60,old_binding)
    async with Client(create_server(old_cfg),mode='legacy',read_timeout_seconds=180) as client:
        _,call=await client_calls(client)
        jobs=(await call('capture_gui_jobs',{}))['jobs']
        existing=next(job for job in jobs if job['planId']==old['planId'])
        if existing['state']=='resolved_saved_artifact':
            closed=json.loads((old_binding.parent/f"plan-{old['planId']}.json").read_text(encoding='utf-8'))
            resolved=closed['result'];review={'reusedPriorExplicitResolution':True}
            assert resolved['savedArtifactVerified'] and not (target.parent/'.cadence-mcp-write.lock').exists()
        else:
            review=await call('capture_gui_review_note',{'planId':old['planId'],'planDigest':old['planDigest']})
            assert 'accept_saved_artifact' in review['review']['allowedDecisions']
            assert (target.parent/'.cadence-mcp-write.lock').exists()
            values={'planId':old['planId'],'planDigest':old['planDigest'],'reviewId':review['review']['reviewId'],
                    'reviewDigest':review['reviewDigest'],'decision':'accept_saved_artifact'}
            resolved=await call('capture_gui_resolve_note',values)
            assert resolved['savedArtifactVerified'] and not resolved['nativeCompletionVerified']
            assert (await call('capture_gui_resolve_note',values))['idempotentReplay']
            assert not (target.parent/'.cadence-mcp-write.lock').exists() and before==sha256(target)
    (args.output/'resolution-report.json').write_text(json.dumps({'review':review,'result':resolved,'fileUnchanged':True},indent=2),encoding='utf-8')
    print('Crashed test job reviewed and explicitly closed without editing its DSN.',flush=True)

    cfg_data=json.loads(args.binding.read_text(encoding='utf-8'));design=Path(cfg_data['expectedDesign']);pid=cfg_data['expectedPid']
    cfg=Config(args.install_root,args.output/'soak-work',(design.parent,),60,args.binding)
    latencies=[];samples=[];reloaded=0;write_count=0
    async with Client(create_server(cfg),mode='legacy',read_timeout_seconds=180) as client:
        tools,call=await client_calls(client)
        async def write(index,measure=False):
            nonlocal write_count
            instances=(await call('capture_gui_instances',{}))['instances'];assert len(instances)==1
            attached=await call('capture_gui_attach',{'instanceId':instances[0]['instanceId'],'access':'write'})
            preview=await call('capture_gui_plan_note',{'sessionId':attached['sessionId'],'schematicName':'FULLADD',
                'pageName':'FULLADD','reference':'U1','value':f'Operations soak {args.output.name} write {index} {time.time_ns()}'})
            values={'planId':preview['plan']['planId'],'planDigest':preview['planDigest'],'idempotencyKey':preview['plan']['planId']}
            task=asyncio.create_task(call('capture_gui_apply_note',values))
            if measure:
                await asyncio.sleep(.08);started=time.monotonic()
                diagnosis=await call('capture_gui_diagnose',{})
                elapsed=time.monotonic()-started;latencies.append(elapsed)
                assert diagnosis['bindings'][0]['condition'] in {'ready','write_in_progress'},diagnosis
                assert elapsed<2.5,elapsed
            result=await task
            assert result['reopened'] and result['definitionConnectivityMatched'] and result['nativeReceiptReleased']
            assert (await call('capture_gui_apply_note',values))['idempotentReplay']
            write_count+=1
        await write('warmup-1');await write('warmup-2')
        async def sample(label):
            diagnosis=await call('capture_gui_diagnose',{})
            remote=diagnosis['bindings'][0]['checks'];assert remote['remoteSessionCount']==0
            samples.append({'label':label,'host':resources(os.getpid()),'capture':resources(pid),
                'remoteSessionCount':remote['remoteSessionCount'],'remotePlanCount':remote['remotePlanCount'],
                'temporaryVerificationFiles':len(list(design.parent.glob('verify-copy-*.dsn')))+len(list(design.parent.glob('inspection-*.json')))+len(list(design.parent.glob('property-*.json')))})
        await sample('baseline-after-warmup')
        for block in range(6):
            for _ in range(20):
                instance=(await call('capture_gui_instances',{}))['instances'][0]
                attached=await call('capture_gui_attach',{'instanceId':instance['instanceId']})
                await call('capture_gui_query',{'sessionId':attached['sessionId'],'entity':'status'})
                pages=await call('capture_gui_query',{'sessionId':attached['sessionId'],'entity':'pages'});assert len(pages['pages'])==2
                await call('capture_gui_detach',{'sessionId':attached['sessionId']})
            for index in range(4):await write(f'{block}-{index}',True)
            result=await asyncio.to_thread(load,args.binding,True,30);assert not result['desktopActionsUsed'];reloaded+=1
            await sample(f'block-{block+1}')
            print(f'Block {block+1}/6: 20 read sessions, 4 verified writes and CLI reload passed.',flush=True)
        baseline=samples[0];last=samples[-1]
        bounds={'hostHandleGrowth':16,'captureHandleGrowth':12,'hostPrivateByteGrowth':24*1024*1024,'capturePrivateByteGrowth':48*1024*1024}
        growth={'hostHandleGrowth':last['host']['handles']-baseline['host']['handles'],
                'captureHandleGrowth':last['capture']['handles']-baseline['capture']['handles'],
                'hostPrivateByteGrowth':last['host']['privateBytes']-baseline['host']['privateBytes'],
                'capturePrivateByteGrowth':last['capture']['privateBytes']-baseline['capture']['privateBytes']}
        growth_passed=all(growth[k]<=v for k,v in bounds.items())
        assert last['temporaryVerificationFiles']==baseline['temporaryVerificationFiles']
        assert all(s['remotePlanCount']<=baseline['remotePlanCount'] for s in samples)
        report={'readSessionCycles':120,'verifiedWritesIncludingWarmup':write_count,'cliReloads':reloaded,
            'concurrentDiagnosticSeconds':latencies,'maxConcurrentDiagnosticSeconds':max(latencies),
            'samples':samples,'growth':growth,'predeclaredBounds':bounds,'desktopActionsUsed':False,
            'resourceBoundsPassed':growth_passed,'scope':'bounded repeatability test, not days-long stability certification'}
        (args.output/'soak-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        assert growth_passed,(growth,bounds)
        (args.output/'tools-list.json').write_text(json.dumps([tool.model_dump(mode='json',by_alias=True) for tool in tools],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'jobClosurePassed':True,'readSessionCycles':120,'verifiedWrites':write_count,'cliReloads':reloaded,'growth':growth}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--install-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--crash-report',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
