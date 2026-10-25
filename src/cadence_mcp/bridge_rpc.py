"""Authenticated RPC sessions over host-registered Capture endpoints."""
from pathlib import Path
import json
import hashlib
import socket
import threading
import time
import uuid

from .core import CadenceError, sha256
from .gui_readiness import require_write_ready

def process_image(pid: int) -> Path:
    import ctypes as c
    from ctypes import wintypes as w
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; kernel.OpenProcess.restype=w.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
    kernel.CloseHandle.argtypes=[w.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:raise OSError('Cannot inspect Capture process')
    try:
        buffer=c.create_unicode_buffer(32768);size=w.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle,0,buffer,c.byref(size)):raise OSError('Cannot identify process image')
        return Path(buffer.value).resolve(strict=True)
    finally:kernel.CloseHandle(handle)

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key')
        result[key]=value
    return result

class RpcConnection:
    def __init__(self,path:Path):
        self.path=path
        self.binding_digest=None

    def ready_for_write(self):
        config=json.loads(self.path.read_text(encoding='utf-8'))
        require_write_ready(config['expectedPid'])

    def call(self,operation:str,params:dict,*,observed_fingerprint=None) -> dict:
        try:
            if self.path.stat().st_size>16384:raise ValueError('oversized binding')
            config_bytes=self.path.read_bytes()
            digest=hashlib.sha256(config_bytes).hexdigest()
            if self.binding_digest is not None and digest!=self.binding_digest:
                raise CadenceError('instance_replaced','Binding configuration changed; discover and attach again.')
            self.binding_digest=digest
            config=json.loads(config_bytes.decode('utf-8'))
            ep_path=self.path.parent/'endpoint.json'
            if ep_path.stat().st_size>16384:raise ValueError('oversized endpoint')
            endpoint=json.loads(ep_path.read_text(encoding='utf-8'))
            if endpoint['host']!='127.0.0.1' or type(endpoint['port']) is not int or not 0<endpoint['port']<65536:
                raise ValueError('invalid endpoint')
            if endpoint['instanceId']!=config['instanceId'] or endpoint['pid']!=config['expectedPid']:
                raise CadenceError('instance_replaced','Endpoint instance changed; attach again.')
            design=Path(config['expectedDesign']).resolve(strict=True)
            if observed_fingerprint is not None and operation!='property.outcome':raise ValueError('Recovery fingerprint only permits outcome inspection')
            expected_hash=observed_fingerprint or config['sourceFingerprint']
            if sha256(design)!=expected_hash:
                raise CadenceError('target_changed','Bound design file changed; prepare a fresh binding.')
            request={'protocol':2,'requestId':uuid.uuid4().hex,'token':config['token'],
                     'instanceId':config['instanceId'],'expectedDesign':str(design),
                     'operation':operation,'params':params,'deadlineMs':int(time.time()*1000)+(8000 if operation=='property.apply' else 4000)}
            if operation in {'property.plan','property.apply'}:require_write_ready(config['expectedPid'])
            payload=json.dumps(request,ensure_ascii=False,allow_nan=False).encode('utf-8')+b'\n'
            if len(payload)>16384:raise ValueError('oversized request')
            # A new TCP connection per RPC recovers disconnects without retaining authentication state.
            # No application request is automatically replayed after send.
            with socket.create_connection(('127.0.0.1',endpoint['port']),timeout=2) as channel:
                channel.settimeout(8 if operation=='property.apply' else 4)
                channel.sendall(payload)
                raw=bytearray();until=time.monotonic()+(8 if operation=='property.apply' else 4)
                while b'\n' not in raw:
                    channel.settimeout(max(0.01,until-time.monotonic()))
                    block=channel.recv(4096)
                    if not block:raise ValueError('bridge disconnected')
                    raw.extend(block)
                    if len(raw)>16384 or time.monotonic()>until:raise ValueError('bounded response exceeded')
            if raw.count(b'\n')!=1 or not raw.endswith(b'\n'):raise ValueError('multiple frames')
            row=json.loads(raw,object_pairs_hook=unique_object)
            if (set(row)!={'protocol','requestId','instanceId','pid','generation','status','code','data'}
                    or row['protocol']!=2 or row['requestId']!=request['requestId']
                    or row['instanceId']!=config['instanceId'] or row['pid']!=config['expectedPid']
                    or type(row['generation']) is not int or row['generation']<1 or not isinstance(row['data'],dict)):
                raise ValueError('invalid RPC response')
            if row['status']!='succeeded':
                code=row['code']
                allowed={'deadline_exceeded','stale_generation','session_lost','session_limit','session_conflict',
                         'target_changed','result_limit','no_active_page','dbo_error','capability_unavailable',
                         'write_denied','write_access_required','dirty_design','stale_plan','plan_limit','state_indeterminate','object_not_found','ambiguous_target','unknown_outcome','bridge_busy'}
                raise CadenceError(code if code in allowed else 'bridge_protocol_error','Capture rejected the bridge request.','gui_bridge')
            if operation!='property.apply' and sha256(design)!=expected_hash:raise CadenceError('target_changed','Bound file changed during request.')
            if operation=='hello':
                live=process_image(config['expectedPid'])
                if live!=Path(config['expectedExecutable']).resolve():raise CadenceError('instance_replaced','Process executable no longer matches this binding.')
                actual=Path(row['data']['executable']).resolve(strict=True)
                if 'expectedExecutable' not in config or actual!=Path(config['expectedExecutable']).resolve():
                    raise CadenceError('installation_mismatch','Prepare a binding with the verified process executable.')
                if sha256(actual)!=config['executableFingerprint']:
                    raise CadenceError('installation_mismatch','Capture executable fingerprint changed.')
                row['data']['installationFingerprint']=config['executableFingerprint']
            return row
        except CadenceError:raise
        except (OSError,ValueError,KeyError,TypeError,UnicodeError) as error:
            raise CadenceError('bridge_unavailable','GUI bridge is disconnected, unresponsive or invalid.','gui_bridge') from error

class GuiBridgeManager:
    def __init__(self,configs=(),roots=()):
        self.configs=tuple(configs);self.roots=tuple(roots)
        self.instances={};self.sessions={};self.lock=threading.RLock();self.active_operations={}

    def discover(self):
        with self.lock:
            paths=set(self.configs)
            for directory in self.roots:
                root=directory.resolve(strict=True)
                for candidate in sorted(root.glob('gui-bridge-*/binding.json')):
                    if not candidate.resolve().is_relative_to(root):continue
                    paths.add(candidate.resolve())
                    if len(paths)>64:raise CadenceError('instance_limit','At most 64 registered bridge candidates.')
            available=[];unavailable=0;found={}
            for path in sorted(paths):
                try:
                    connection=RpcConnection(path)
                    reply=connection.call('hello',{})
                    data=reply['data'];identity=reply['instanceId']
                    if identity in found:raise CadenceError('ambiguous_instance','Duplicate instance registration.')
                    found[identity]=connection
                    available.append({'instanceId':identity,'pid':reply['pid'],'generation':reply['generation'],**data})
                except CadenceError:unavailable+=1
            self.instances=found
            return {'instances':available,'unavailableCount':unavailable,'automaticRetargeting':False}

    def attach(self,instance_id,access='read'):
        with self.lock:
            if instance_id not in self.instances:self.discover()
            if instance_id not in self.instances:raise CadenceError('instance_not_found','No authenticated registered instance.')
            connection=self.instances[instance_id]
            hello=connection.call('hello',{})
            if hello['data']['bindingLost']:raise CadenceError('target_changed','The instance binding was invalidated.')
            sid=uuid.uuid4().hex;generation=hello['generation']
            params={'sessionId':sid,'generation':generation}
            if access!='read':params['access']=access
            reply=connection.call('session.open',params)
            if reply['generation']!=generation or reply['data'].get('sessionId')!=sid or reply['data'].get('readOnly') is not (access=='read'):
                raise CadenceError('bridge_protocol_error','Session acknowledgement does not match the request.')
            self.sessions[sid]={'connection':connection,'instanceId':instance_id,'generation':generation,'pid':reply['pid'],'access':access}
            return {'sessionId':sid,'instanceId':instance_id,'generation':generation,'pid':reply['pid'],**reply['data']}

    def query(self,session_id,entity):
        with self.lock:
            if entity not in {'status','pages','selection'}:raise CadenceError('capability_unavailable','Only typed read queries are enabled.')
            if session_id not in self.sessions:raise CadenceError('session_lost','GUI session is detached or lost.')
            session=self.sessions[session_id]
            try:
                reply=session['connection'].call(entity,{'sessionId':session_id,'generation':session['generation']})
                if reply['generation']!=session['generation']:raise CadenceError('session_lost','GUI generation changed.')
            except CadenceError as error:
                # Transport failure loses this logical session. Reattach is explicit; never replay.
                self.sessions.pop(session_id,None)
                raise error
            return {'sessionId':session_id,'generation':reply['generation'],**reply['data']}

    def detach(self,session_id):
        with self.lock:
            if session_id not in self.sessions:raise CadenceError('session_lost','GUI session is already detached.')
            session=self.sessions.pop(session_id)
            try:
                session['connection'].call('session.close',{'sessionId':session_id,'generation':session['generation']})
                remote=True
            except CadenceError:remote=False
            return {'detached':True,'remoteReleaseConfirmed':remote}

    def status(self):
        """Convenience status only when one authenticated instance is registered."""
        with self.lock:
            found=self.discover()['instances']
            if len(found)!=1:
                raise CadenceError('ambiguous_instance' if found else 'bridge_unavailable',
                                   'Choose an explicit instance through GUI discovery and attach.')
            instance=found[0]
            attached=self.attach(instance['instanceId']);sid=attached['sessionId']
            try:
                state=self.query(sid,'status')
                return {**instance,**state,'bindingVerified':True}
            finally:
                if sid in self.sessions:self.detach(sid)
