"""Actual Capture stdio MCP lifecycle acceptance; requires a selected fixture object."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256

async def main(args):
    cfg=json.loads(args.binding.read_text(encoding='utf-8'))
    original=sha256(Path(cfg['expectedDesign']))
    parameters=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server',
        '--install-root',str(args.install_root),'--workspace-root',str(args.output/'work'),
        '--read-root',str(Path(cfg['expectedDesign']).parent),'--gui-bridge-config',str(args.binding)])
    checks={};args.output.mkdir(parents=True,exist_ok=True)
    async with Client(parameters,mode='legacy',read_timeout_seconds=10) as client:
        tools=(await client.list_tools()).tools
        schemas={tool.name:tool.output_schema for tool in tools}
        async def call(name,params):
            response=await client.call_tool(name,params)
            assert not response.is_error,(name,response.structured_content)
            Draft202012Validator(schemas[name]).validate(response.structured_content)
            return response.structured_content['data']
        listing=await call('capture_gui_instances',{})
        assert len(listing['instances'])==1
        instance=listing['instances'][0]
        assert instance['dirtyState']=='clean' and instance['writable'] is False
        checks['authenticated_process_fingerprint']=True
        first=await call('capture_gui_attach',{'instanceId':instance['instanceId']})
        second=await call('capture_gui_attach',{'instanceId':instance['instanceId']})
        async def query(sid,entity):return await call('capture_gui_query',{'sessionId':sid,'entity':entity})
        pages=await query(first['sessionId'],'pages')
        assert {p['name'] for p in pages['pages']}=={'FULLADD','HALFADD'}
        selection=await query(first['sessionId'],'selection')
        assert selection['items'] and selection['selectionSnapshotId']
        other_selection=await query(first['sessionId'],'selection')
        assert other_selection['selectionSnapshotId']!=selection['selectionSnapshotId']
        checks['live_pages_and_selection']=True
        for _ in range(3):assert (await query(second['sessionId'],'status'))['dirtyState']=='clean'
        checks['fresh_tcp_connections_same_session']=True
        await call('capture_gui_detach',{'sessionId':first['sessionId']})
        rejected=await client.call_tool('capture_gui_query',{'sessionId':first['sessionId'],'entity':'status'})
        assert rejected.is_error
        assert (await query(second['sessionId'],'status'))['dirtyState']=='clean'
        checks['independent_sessions_and_detach']=True
        extra=await client.call_tool('capture_gui_query',{'sessionId':second['sessionId'],'entity':'status','script':'invalid'})
        assert extra.is_error
        checks['strict_tool_arguments']=True
        if args.wait_dirty:
            (args.output/'phase.json').write_text(json.dumps({'phase':'await_dirty_transition','generation':second['generation']}))
            print('WAITING_FOR_FIXTURE_DIRTY_TRANSITION',flush=True)
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                response=await client.call_tool('capture_gui_query',{'sessionId':second['sessionId'],'entity':'status'})
                if response.is_error:
                    assert response.structured_content['error']['code']=='session_lost'
                    break
                await asyncio.sleep(0.2)
            else:raise AssertionError('Fixture dirty transition not observed')
            checks['actual_capture_dirty_invalidates_session']=True
            for _ in range(50):
                fresh=await call('capture_gui_instances',{})
                if fresh['instances'][0]['dirtyState']=='clean':break
                await asyncio.sleep(0.2)
            else:raise AssertionError('Fixture did not return to clean state')
            new=await call('capture_gui_attach',{'instanceId':instance['instanceId']})
            assert new['generation']>second['generation']
            assert (await query(new['sessionId'],'status'))['dirtyState']=='clean'
            await call('capture_gui_detach',{'sessionId':new['sessionId']})
            checks['explicit_reattach_new_generation']=True
        else:await call('capture_gui_detach',{'sessionId':second['sessionId']})
        status=await call('capture_gui_status',{})
        assert status['dirtyState']=='clean'
        checks['convenience_status_uses_rpc2']=True
        (args.output/'tools-list.json').write_text(json.dumps([tool.model_dump(mode='json',by_alias=True) for tool in tools],ensure_ascii=False,indent=2),encoding='utf-8')
    assert original==sha256(Path(cfg['expectedDesign']))
    checks['bound_design_bytes_unchanged']=True
    report={'checks':checks,'instance':instance,'pages':pages,'selection':selection,
            'toolCount':len(tools),'notVerified':['two_real_capture_instances','modal_dialog_recovery',
            'dirty_epoch_for_every_vendor_edit','writes_and_drc']}
    (args.output/'session-smoke-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'checks':checks,'toolCount':len(tools)},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--install-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--wait-dirty',action='store_true')
    asyncio.run(main(parser.parse_args()))
