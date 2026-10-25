import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator

async def main(args):
    cfg=json.loads(args.binding.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True,exist_ok=True)
    params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server',
        '--install-root',str(args.install_root),'--workspace-root',str(args.output/'work'),
        '--read-root',str(Path(cfg['expectedDesign']).parent),'--gui-bridge-config',str(args.binding),
        '--timeout-seconds','60'],env=dict(os.environ))
    async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
        tools=(await client.list_tools()).tools
        schemas={t.name:t.output_schema for t in tools}
        async def call(name,values):
            reply=await client.call_tool(name,values)
            assert not reply.is_error,(name,reply.structured_content)
            Draft202012Validator(schemas[name]).validate(reply.structured_content)
            return reply.structured_content['data']
        instances=await call('capture_gui_instances',{})
        assert len(instances['instances'])==1
        identity=instances['instances'][0]['instanceId']
        attached=await call('capture_gui_attach',{'instanceId':identity,'access':'write'})
        assert attached['readOnly'] is False
        preview=await call('capture_gui_plan_note',{'sessionId':attached['sessionId'],
            'schematicName':'FULLADD','pageName':'FULLADD','reference':'U1','value':'MCP metadata write verification'})
        values={'planId':preview['plan']['planId'],'planDigest':preview['planDigest'],'idempotencyKey':'fixture-note-v1'}
        applied=await call('capture_gui_apply_note',values)
        assert applied['saved'] and applied['reopened'] and applied['propertyMatched'] and applied['definitionConnectivityMatched']
        replay=await call('capture_gui_apply_note',values)
        assert replay['idempotentReplay']
        status=await call('capture_gui_status',{})
        assert status['dirtyState']=='clean'
        (args.output/'write-smoke-report.json').write_text(json.dumps({'preview':preview,'applied':applied,
            'idempotentReplay':replay['idempotentReplay'],'statusAfter':status},ensure_ascii=False,indent=2),encoding='utf-8')
        (args.output/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(applied,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binding',type=Path,required=True)
    p.add_argument('--install-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    asyncio.run(main(p.parse_args()))
