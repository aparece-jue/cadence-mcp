"""Read immutable DSN cache definitions separately from external OLB sessions."""
import json
from .core import CadenceError,checked_path,new_id
from .environment import run_tcl
from .library import FIELDS,validate_library


def query_cache(capture,sid,entity,package_name=None,cursor=None,limit=100):
    with capture.lock:
        session=capture._session(sid)
        if entity not in FIELDS or type(limit) is not int or not 1<=limit<=1000:raise CadenceError('invalid_query','Invalid cache entity or page size.')
        if 'cacheDefinitions' not in session:
            directory=checked_path(str(capture._workspace(session['workspaceId'])['directory']),(capture.config.workspace_root,))
            output=directory/(new_id('cache-read')+'.json')
            run_tcl(capture.config,'inspect_cache.tcl',[str(session['design']),str(output),'100000'],directory)
            capture._session(sid)
            try:
                if output.stat().st_size>32*1024*1024:raise ValueError('size')
                data=json.loads(output.read_text(encoding='utf-8'));validate_library(data)
            except (OSError,ValueError) as error:raise CadenceError('invalid_worker_result','Invalid cache inspection document.','decode') from error
            session['cacheDefinitions']=data;session['cacheCursors']={};output.unlink()
        data=session['cacheDefinitions'];signature=(entity,package_name,limit);offset=0
        if cursor is not None:
            saved=session['cacheCursors'].get(cursor)
            if saved is None or saved[0]!=signature:raise CadenceError('stale_cursor','Cache cursor belongs to another session/query.')
            offset=saved[1]
        rows=data[entity]
        if package_name is not None:
            packages={p['objectId'] for p in data['package'] if p['name']==package_name}
            rows=[r for r in rows if (r['objectId'] if entity=='package' else r['packageId']) in packages]
        next_cursor=None
        if offset+limit<len(rows):
            if len(session['cacheCursors'])>=10000:raise CadenceError('cursor_limit','Cache cursor limit reached.')
            next_cursor=new_id('cache-cursor');session['cacheCursors'][next_cursor]=(signature,offset+limit)
        return {'sessionId':sid,'revision':session['revision'],'scope':'dsn_cache_device_definitions',
            'items':rows[offset:offset+limit],'total':len(rows),'nextCursor':next_cursor,'complete':next_cursor is None,
            'enumerationScope':'cached_and_local_package_definitions','sourceQualifiedPackageIdentityVerified':False,
            'readOnly':True,'externalSourceLibraryVerified':False,'cacheSynchronizationVerified':False,
            'notChecked':['source_olb_identity','cache_update_or_replacement','instance_override_inheritance','embedded_cache_closure']}
