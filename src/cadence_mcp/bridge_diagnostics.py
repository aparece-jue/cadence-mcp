"""Read-only diagnosis using only host-registered bindings; never retarget or dismiss UI."""
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import socket
import time
from .bridge_rpc import RpcConnection,process_image,unique_object
from .core import CadenceError,sha256
from .gui_readiness import require_write_ready

def process_status(pid):
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.CloseHandle.argtypes=[w.HANDLE]
    handle=kernel.OpenProcess(0x1000|0x00100000,False,pid)
    if not handle:return 'stopped' if c.get_last_error()==87 else 'unknown'
    try:return 'stopped' if kernel.WaitForSingleObject(handle,0)==0 else 'running'
    finally:kernel.CloseHandle(handle)

def inspect_binding(path,active_operations=None):
    result={'bindingId':path.parent.name,'condition':'invalid_binding','nextAction':'inspect_binding','checks':{}}
    started=time.monotonic()
    try:
        if path.stat().st_size>16384:raise ValueError('oversized binding')
        cfg=json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique_object)
        if type(cfg['expectedPid']) is not int or cfg['expectedPid']<=0:raise ValueError('invalid process')
        result.update(instanceId=cfg['instanceId'],pid=cfg['expectedPid'])
        status=process_status(cfg['expectedPid']);result['checks']['process']=status
        design=Path(cfg['expectedDesign']).resolve(strict=True)
        result['checks']['fileFingerprint']='matches' if sha256(design)==cfg['sourceFingerprint'] else 'changed'
        lock=design.parent/'.cadence-mcp-write.lock'
        result['checks']['unresolvedWriteLock']=lock.exists()
        if lock.exists():
            active=(active_operations or {}).get(cfg['instanceId'])
            result.update(condition='write_in_progress' if active else 'unresolved_write',nextAction='wait_for_current_write' if active else 'review_job_or_recover_without_replay')
            return result
        if status!='running':
            result.update(condition='process_stopped' if status=='stopped' else 'process_state_unknown',nextAction='start_capture_and_prepare_new_binding' if status=='stopped' else 'inspect_process_access')
            return result
        if process_image(cfg['expectedPid'])!=Path(cfg['expectedExecutable']).resolve():
            result.update(condition='process_replaced',nextAction='prepare_new_binding');return result
        try:require_write_ready(cfg['expectedPid']);result['checks']['window']='enabled'
        except CadenceError as error:
            result['checks']['window']='modal_or_disabled' if error.code=='bridge_busy' else 'unknown'
            result.update(condition='modal_or_disabled_window' if error.code=='bridge_busy' else 'window_state_unknown',nextAction='resolve_capture_dialog' if error.code=='bridge_busy' else 'inspect_capture_window')
            return result
        if result['checks']['fileFingerprint']!='matches':
            result.update(condition='design_file_changed',nextAction='inspect_change_before_new_binding');return result
        endpoint=path.parent/'endpoint.json'
        if not endpoint.exists():result.update(condition='bridge_not_loaded',nextAction='run_load_gui_bridge');return result
        if endpoint.stat().st_size>16384:raise ValueError('oversized endpoint')
        ep=json.loads(endpoint.read_text(encoding='utf-8'),object_pairs_hook=unique_object)
        if (ep.get('instanceId')!=cfg['instanceId'] or ep.get('pid')!=cfg['expectedPid'] or ep.get('host')!='127.0.0.1'
                or type(ep.get('port')) is not int or not 0<ep['port']<65536):
            result.update(condition='endpoint_identity_mismatch',nextAction='prepare_new_binding');return result
        try:reply=RpcConnection(path).call('hello',{})
        except CadenceError as error:
            result.update(condition='listener_unavailable_or_unresponsive',nextAction='inspect_listener_then_explicit_reload',errorCode=error.code);return result
        data=reply['data']
        if data.get('bindingLost') or Path(data['activeDesign']).resolve()!=design:
            result.update(condition='active_design_mismatch',nextAction='select_intended_design_and_prepare_new_binding');return result
        result.update(condition='ready' if data.get('dirtyState')=='clean' else 'design_dirty',nextAction='ready' if data.get('dirtyState')=='clean' else 'review_unsaved_changes',generation=reply['generation'])
        result['checks'].update(dirtyState=data.get('dirtyState'),remoteSessionCount=data.get('sessionCount'),remotePlanCount=data.get('propertyPlanCount'))
        return result
    except (OSError,ValueError,KeyError,TypeError,CadenceError):
        return result
    finally:result['elapsedSeconds']=round(time.monotonic()-started,3)

def diagnose(manager):
    # No long-lived GUI lock: health checks must not wait behind independent Dbo verification workers.
    paths=set(manager.configs)
    for directory in manager.roots:
        root=directory.resolve(strict=True)
        for path in root.glob('gui-bridge-*/binding.json'):
            if path.resolve().is_relative_to(root):paths.add(path.resolve())
    if len(paths)>64:raise CadenceError('instance_limit','At most 64 registered bindings.')
    rows=[inspect_binding(path,getattr(manager,'active_operations',{})) for path in sorted(paths)]
    return {'status':'ready' if rows and all(row['condition']=='ready' for row in rows) else 'attention',
            'bindings':rows,'automaticRepair':False,'mutationReplayed':False}
