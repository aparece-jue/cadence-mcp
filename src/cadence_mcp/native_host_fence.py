"""Durable host fence shared by native export jobs and bridge metadata writers."""
import json,re
from pathlib import Path
from .core import CadenceError,checked_path

NAME='native-netlist-lease.json'
KEYS={'kind','jobId','pid','instanceId','jobDirectory','bindingSha256'}

def fence_path(binding):
    parent=Path(binding).resolve(strict=True).parent
    path=parent/NAME
    if path.is_symlink() or (path.exists() and getattr(path.lstat(),'st_file_attributes',0)&0x400):
        raise CadenceError('bridge_busy','Native host fence is a reparse point; do not follow or remove it.')
    checked_path(str(path),(parent,),exists=False)
    return path

def ensure_idle(binding):
    path=fence_path(binding)
    if path.exists():raise CadenceError('bridge_busy','An unresolved native host operation owns this Capture instance; inspect/recover it without replay.')

def read_fence(binding):
    path=fence_path(binding)
    if not path.exists():return None
    try:
        if not path.is_file() or path.stat().st_size>16384:raise ValueError('size')
        row=json.loads(path.read_text(encoding='utf-8'))
        if (set(row)!=KEYS or row['kind']!='native_netlist_v1' or not re.fullmatch('[a-f0-9]{32}',row['jobId'])
                or type(row['pid']) is not int or row['pid']<=0 or not isinstance(row['instanceId'],str)
                or not isinstance(row['jobDirectory'],str) or not re.fullmatch('[a-f0-9]{64}',row['bindingSha256'])):raise ValueError('shape')
        return row
    except (OSError,ValueError,TypeError,KeyError) as error:
        raise CadenceError('bridge_busy','Native host fence is malformed; preserve it and resolve the original operation.') from error

def claim(binding,row):
    ensure_idle(binding);path=fence_path(binding)
    try:
        with path.open('x',encoding='utf-8') as stream:
            json.dump(row,stream,separators=(',',':'));stream.flush()
            import os
            os.fsync(stream.fileno())
    except FileExistsError as error:raise CadenceError('bridge_busy','Another native operation claimed this host.') from error
    if read_fence(binding)!=row:raise CadenceError('bridge_busy','Native host fence does not match its owner.')

def release(binding,expected):
    row=read_fence(binding)
    if row is None or row!=expected:return False
    fence_path(binding).unlink()
    return True
