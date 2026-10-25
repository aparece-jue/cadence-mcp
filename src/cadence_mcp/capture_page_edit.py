"""Page creation/rename with definition, connection, graphic and count baselines."""
import copy,json
from .capture_pages import CapturePages
from .capture_wire import inventory,connection_digest
from .capture_objects import query_objects
from .capture_design_create import read_document_meta,COUNT_KEYS
from .isolated_jobs import digest
from .core import CadenceError

def graphic_digest(data,objects):
    sch={s['objectId']:s['name'] for s in data['schematic']}
    pages={p['objectId']:[sch[p['schematicId']],p['name']] for p in data['page']}
    parts={p['objectId']:p['reference'] for p in data['part']}
    rows=[]
    for obj in objects:
        attrs=copy.deepcopy(obj['attributes']);owner=attrs.pop('partId',None)
        if owner is not None:attrs['ownerReference']=parts[owner]
        rows.append([obj['kind'],pages[obj['pageId']],attrs])
    return digest(sorted(rows,key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False)))

def meta_digest(meta):
    return digest({'rootName':meta['rootName'],'schematics':sorted(s['name'] for s in meta['schematics']),
                   'pages':sorted(meta['pages'],key=lambda p:(p['schematicName'],p['name']))})

class CapturePageEdits(CapturePages):
    # Same persistent kind as existing native-tested page plans; older plans
    # without stronger baselines must not pass verification as a new plan.
    def plan_payload(self,session,data,expected,payload):
        sid=session['sessionId'] if 'sessionId' in session else next(k for k,v in self.capture.sessions.items() if v is session)
        connections=inventory(self.capture,sid)
        query_objects(self.capture,sid,'graphics','graphic',None,None,1)
        graphics=session['objectInventories']['graphics']
        meta=read_document_meta(self.config,session['design'],session['design'].parent)
        expected_meta=copy.deepcopy(meta)
        if payload['operation']=='create':
            expected_meta['pages'].append({'schematicName':payload['schematicName'],'name':payload['name'],'counts':{k:0 for k in COUNT_KEYS}})
        else:
            for page in expected_meta['pages']:
                if page['schematicName']==payload['schematicName'] and page['name']==payload['oldName']:page['name']=payload['name']
        payload.update(expectedConnectionDigest=connection_digest(expected,connections),expectedGraphicDigest=graphic_digest(expected,graphics),
                       expectedMetaDigest=meta_digest(expected_meta))
        if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Page baseline exceeds durable record bound.')
        self.capture._session(sid);return payload
    def verify_content(self,verifier,sid,p):
        if not all(k in p for k in ('expectedConnectionDigest','expectedGraphicDigest','expectedMetaDigest')):
            raise CadenceError('invalid_plan','Legacy internal page plans lack the required content baselines.')
        session=verifier._session(sid);data=session['data']
        if connection_digest(data,inventory(verifier,sid))!=p['expectedConnectionDigest']:raise CadenceError('page_connection_mismatch','Page operation changed connection-object baseline.','verify')
        query_objects(verifier,sid,'graphics','graphic',None,None,1)
        if graphic_digest(data,session['objectInventories']['graphics'])!=p['expectedGraphicDigest']:raise CadenceError('page_graphic_mismatch','Page operation changed graphic/part/display baseline.','verify')
        meta=read_document_meta(self.config,session['design'],session['design'].parent)
        if meta_digest(meta)!=p['expectedMetaDigest']:raise CadenceError('page_metadata_mismatch','Page root or native content counts differ from the explicit plan.','verify')
    def verify(self,directory,p,native_completed):
        result=super().verify(directory,p,native_completed)
        result.update(connectionAndGraphicBaselineVerified=True,nativeRootAndPageCountsVerified=True)
        result['notChecked']+=['custom_plugin_objects','bus_member_semantics','erc_bookmark_details','native_cached_bounds_rendering']
        return result
