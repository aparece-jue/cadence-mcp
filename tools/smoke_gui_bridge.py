"""Run against an explicitly prepared live Capture binding; never log tokens."""
import argparse
import asyncio
import json
from pathlib import Path
import socket
import sys
import uuid

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.gui_bridge import GuiBridgeClient
from cadence_mcp.core import sha256

async def main(args):
    config=json.loads(args.binding.read_text(encoding='utf-8'))
    endpoint=json.loads((args.binding.parent/'endpoint.json').read_text(encoding='utf-8'))
    original=sha256(Path(config['expectedDesign']))
    base={'protocol':1,'requestId':uuid.uuid4().hex,'token':config['token'],
          'instanceId':config['instanceId'],'expectedDesign':config['expectedDesign'],'operation':'status'}
    checks={}
    status=GuiBridgeClient(args.binding).status()
    for label,changes in [('bad_token',{'token':'wrong'}),('wrong_instance',{'instanceId':'wrong'}),
                          ('unknown_operation',{'operation':'eval'}),('extra_field',{'script':'invalid'}),
                          ('wrong_protocol',{'protocol':2}),('wrong_binding',{'expectedDesign':'C:/wrong.dsn'})]:
        with socket.create_connection(('127.0.0.1',endpoint['port']),timeout=4) as channel:
            channel.settimeout(4)
            channel.sendall(json.dumps({**base,**changes}).encode()+b'\n')
            try:reply=channel.recv(1024)
            except ConnectionResetError:reply=b''
            assert reply==b'',label
            checks[label+'_rejected']=True
    with socket.create_connection(('127.0.0.1',endpoint['port']),timeout=4) as channel:
        channel.settimeout(4)
        payload=json.dumps(base).encode()+b'\n'
        channel.sendall(payload[:20]); channel.sendall(payload[20:])
        reply=bytearray()
        while b'\n' not in reply:
            block=channel.recv(4096)
            assert block
            reply.extend(block)
        assert json.loads(reply)['status']=='succeeded'
        checks['fragmented_frame_accepted']=True
    for label,payload in [('oversized',b'x'*16385+b'\n'),('malformed',b'{bad}\n')]:
        with socket.create_connection(('127.0.0.1',endpoint['port']),timeout=4) as channel:
            channel.settimeout(4)
            channel.sendall(payload)
            try:reply=channel.recv(1024)
            except ConnectionResetError:reply=b''
            assert reply==b''
            checks[label+'_rejected']=True
    parameters=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server',
        '--install-root',str(args.install_root),'--workspace-root',str(args.output/'work'),
        '--read-root',str(Path(config['expectedDesign']).parent),'--gui-bridge-config',str(args.binding)])
    async with Client(parameters,mode='legacy',read_timeout_seconds=15) as client:
        tools=(await client.list_tools()).tools
        response=await client.call_tool('capture_gui_status',{})
        assert not response.is_error
        tool=next(t for t in tools if t.name=='capture_gui_status')
        Draft202012Validator(tool.output_schema).validate(response.structured_content)
        assert response.structured_content['data']['instanceId']==status['instanceId']
        extra=await client.call_tool('capture_gui_status',{'eval':'invalid'})
        assert extra.is_error
        checks['stdio_mcp_status']=True
        checks['strict_mcp_arguments']=True
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],ensure_ascii=False,indent=2),encoding='utf-8')
    assert original==sha256(Path(config['expectedDesign']))
    checks['bound_design_unchanged']=True
    report={'status':status,'checks':checks,'notVerified':['dirty_state','actual_gui_switch','multiple_capture_instances',
             'drc_execution','writes','modal_dialog_recovery','restart_recovery']}
    (args.output/'bridge-smoke-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'checks':checks,'pid':status['pid'],'output':str(args.output)},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--install-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
