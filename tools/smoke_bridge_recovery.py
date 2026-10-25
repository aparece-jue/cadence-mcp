"""Explicit fixture-only fault injection; never an MCP execution endpoint."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.bridge_rpc import GuiBridgeManager,RpcConnection
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.gui_property import GuiPropertyWriter

async def main(args):
    config=json.loads(args.binding.read_text(encoding='utf-8'));design=Path(config['expectedDesign'])
    args.output.mkdir(parents=True,exist_ok=True)
    parameters=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server',
        '--install-root',str(args.install_root),'--workspace-root',str(args.output/'work'),
        '--read-root',str(design.parent),'--gui-bridge-config',str(args.binding),'--timeout-seconds','60'],env=dict(os.environ))
    async def call(client,name,values,ok=True):
        result=await client.call_tool(name,values)
        assert bool(result.is_error) is (not ok),(name,result.structured_content)
        return result.structured_content
    report={}
    async with Client(parameters,mode='legacy',read_timeout_seconds=180) as client:
        found=(await call(client,'capture_gui_instances',{}))['data']['instances'];assert len(found)==1
        attached=(await call(client,'capture_gui_attach',{'instanceId':found[0]['instanceId'],'access':'write'}))['data']
        preview=(await call(client,'capture_gui_plan_note',{'sessionId':attached['sessionId'],'schematicName':'FULLADD',
            'pageName':'FULLADD','reference':'U1','value':'cancelled note'}))['data']
        p={'planId':preview['plan']['planId'],'planDigest':preview['planDigest']}
        before=sha256(design)
        cancelled=await call(client,'capture_gui_cancel_note',p)
        await call(client,'capture_gui_apply_note',{**p,'idempotencyKey':'cancelled'},False)
        assert before==sha256(design)
        report['cancelBeforeApply']=cancelled['data']
        await call(client,'capture_gui_detach',{'sessionId':attached['sessionId']})
    # A real native save, followed by deliberate host-side receipt loss.
    manager=GuiBridgeManager((args.binding,));identity=manager.discover()['instances'][0]['instanceId']
    attached=manager.attach(identity,'write')
    host=GuiPropertyWriter(manager,Config(args.install_root,args.output/'fault-work',(design.parent,),60,args.binding))
    preview=host.plan(attached['sessionId'],'FULLADD','FULLADD','U1','Recovery receipt verification')
    original=RpcConnection.call
    def lose_reply(self,operation,params,**kwargs):
        result=original(self,operation,params,**kwargs)
        if operation=='property.apply':raise CadenceError('bridge_unavailable','Fixture: save receipt deliberately discarded')
        return result
    with patch.object(RpcConnection,'call',lose_reply):
        try:host.apply(preview['plan']['planId'],preview['planDigest'],'lost-save-receipt')
        except CadenceError as error:assert error.code=='bridge_unavailable'
        else:raise AssertionError('Injected receipt loss was not observed')
    assert (design.parent/'.cadence-mcp-write.lock').exists()
    # Fresh stdio server has no in-memory plans or sessions; recover only from the durable record.
    async with Client(parameters,mode='legacy',read_timeout_seconds=180) as client:
        jobs=(await call(client,'capture_gui_jobs',{}))['data']['jobs']
        assert any(j['planId']==preview['plan']['planId'] and j['state']=='started' for j in jobs)
        p={'planId':preview['plan']['planId'],'planDigest':preview['planDigest']}
        recovered=(await call(client,'capture_gui_recover_note',p))['data']
        assert recovered['recovered'] and recovered['saved'] and recovered['definitionConnectivityMatched']
        assert not (design.parent/'.cadence-mcp-write.lock').exists()
        again=(await call(client,'capture_gui_recover_note',p))['data']
        assert again['sourceFingerprintAfter']==recovered['sourceFingerprintAfter']
        report['recoveredAfterServerRestart']=recovered
        report['jobsAfter']=(await call(client,'capture_gui_jobs',{}))['data']
        report['statusAfter']=(await call(client,'capture_gui_status',{}))['data']
        tools=(await client.list_tools()).tools
        (args.output/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],ensure_ascii=False,indent=2),encoding='utf-8')
    (args.output/'recovery-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'cancelled':True,'saveReceiptLost':True,'freshServerRecovered':True,'tools':len(tools)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--install-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
