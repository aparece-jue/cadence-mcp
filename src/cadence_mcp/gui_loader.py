"""Generate a trusted, PID-bound Capture loader. Not an MCP eval interface."""
import json
import re
from pathlib import Path
import subprocess
import time
import uuid
from .bridge_rpc import RpcConnection,process_image
from .core import CadenceError,sha256

def tcl_string(value):
    escapes={'\\':'\\\\','"':'\\"','$':'\\$','[':'\\[',']':'\\]','\n':'\\n','\r':'\\r','\t':'\\t'}
    return '"'+''.join(escapes.get(char,('\\u%04x'%ord(char) if ord(char)<=65535 else '\\U%08x'%ord(char)) if ord(char)>127 else char) for char in str(value))+'"'

def prepare_loader(binding):
    binding=binding.resolve(strict=True)
    if binding.stat().st_size>16384:raise CadenceError('invalid_binding','Oversized binding.')
    config=json.loads(binding.read_text(encoding='utf-8'))
    executable=Path(config['expectedExecutable']).resolve(strict=True)
    if process_image(config['expectedPid'])!=executable or sha256(executable)!=config['executableFingerprint']:
        raise CadenceError('instance_replaced','Prepare a fresh binding for the actual Capture process.')
    design=Path(config['expectedDesign']).resolve(strict=True)
    if sha256(design)!=config['sourceFingerprint']:raise CadenceError('target_changed','Design changed; preserve any unresolved write record.')
    adapter=Path(__file__).parent/'adapters/bridge.tcl'
    tag=uuid.uuid4().hex
    payload=binding.parent/f'load-{tag}.tcl';wrapper=binding.parent/f'invoke-{tag}.tcl'
    receipt=binding.parent/f'loaded-{tag}.json'
    # Everything interpolated is a literal data value; the executable script is fixed host code.
    code='''# Trusted loader. Refuse a different process or design before stopping any bridge.
if {[pid] != PID} {error "Bridge loader belongs to another process"}
uplevel #0 [list source ADAPTER]
if {![string equal -nocase [::cmcpBridge::activeDesign] [file normalize DESIGN]]} {error "Wrong active design; loader will not retarget"}
::cmcpBridge::stop
::cmcpBridge::start BINDING
set ::cmcpLoaderStream [::open RECEIPT {WRONLY CREAT EXCL}]
try {fconfigure $::cmcpLoaderStream -encoding utf-8 -translation lf;puts $::cmcpLoaderStream [cmcp::obj pid [pid] loaded true]} finally {close $::cmcpLoaderStream;unset ::cmcpLoaderStream}
'''
    literals={'PID':str(config['expectedPid']),'ADAPTER':tcl_string(adapter.as_posix()),
              'DESIGN':tcl_string(design.as_posix()),'BINDING':tcl_string(binding.as_posix()),'RECEIPT':tcl_string(receipt.as_posix())}
    code=re.sub(r'\b(PID|ADAPTER|DESIGN|BINDING|RECEIPT)\b',lambda match:literals[match.group(0)],code)
    payload.write_text(code,encoding='utf-8')
    # Capture CLI replays command files; source ensures Tcl parses complete multiline procedures.
    wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n',encoding='utf-8')
    return config,wrapper,receipt

def load(binding,reload=False,wait_seconds=30):
    binding=Path(binding)
    if not reload:
        try:
            reply=RpcConnection(binding).call('hello',{})
            if not reply['data']['bindingLost']:
                return {'state':'already_available','pid':reply['pid'],'instanceId':reply['instanceId'],'generation':reply['generation']}
        except CadenceError:pass
    config,wrapper,receipt=prepare_loader(binding)
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    child=subprocess.Popen([config['expectedExecutable'],str(wrapper)],startupinfo=startup)
    end=time.monotonic()+wait_seconds
    while not receipt.exists():
        if time.monotonic()>end:
            raise CadenceError('bridge_load_timeout','Capture did not acknowledge the loader; inspect its startup/modal state. Do not blindly rerun a business write.')
        time.sleep(.1)
    reply=RpcConnection(binding).call('hello',{})
    if reply['data']['bindingLost']:raise CadenceError('target_changed','Target changed while loading.')
    return {'state':'loaded','pid':reply['pid'],'instanceId':reply['instanceId'],'generation':reply['generation'],
            'desktopActionsUsed':False}
