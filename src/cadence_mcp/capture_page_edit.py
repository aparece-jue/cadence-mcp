"""Page creation/rename with definition, connection, graphic and count baselines."""
import copy,json,ntpath
from .capture_pages import CapturePages
from .capture_wire import inventory,connection_digest
from .capture_objects import query_objects, read_inventory
from .capture_design_create import read_document_meta,COUNT_KEYS,require_native_document_encoding
from .isolated_jobs import digest
from .core import CadenceError

TITLEBLOCK_CONTEXT_PROFILE = "titleblock-context-v1"
TITLEBLOCK_NAMED_CONTEXT_PROFILE = "titleblock-named-context-v1"
GENERATED_MODIFICATION_FIELDS = {
    f"{owner} Modify {field}"
    for owner in ("Design", "Schematic", "Page")
    for field in ("Date", "Time")
}


def titleblock_content(attrs, actual_page, expected_page, design, *, named_context=False):
    users = sorted(attrs["userProperties"], key=lambda prop: prop["name"])
    user_names = {prop["name"].casefold() for prop in users}
    content = []
    for prop in attrs["properties"]:
        name, value = prop["name"], prop["value"]
        if name.casefold() not in user_names:
            if name == "Design File Name":
                if ntpath.normcase(ntpath.normpath(value)) != ntpath.normcase(ntpath.normpath(str(design))):
                    raise CadenceError("page_titleblock_context_mismatch", "Titleblock file name does not identify the opened design.")
                value = None
            elif named_context and name == "Design Name":
                stem = ntpath.splitext(ntpath.basename(str(design)))[0]
                if value.casefold() != stem.casefold():
                    raise CadenceError("page_titleblock_context_mismatch", "Titleblock design name does not match the opened filename.")
                value = None
            elif name == "Page Name":
                if value != actual_page:
                    raise CadenceError("page_titleblock_context_mismatch", "Titleblock page name does not match its actual owner.")
                value = expected_page
            elif name in GENERATED_MODIFICATION_FIELDS:
                # Value is generated on save. Keep field membership in the digest.
                value = None
        content.append({"name": name, "value": value})
    return {**attrs, "userProperties": users, "properties": sorted(content, key=lambda prop: prop["name"])}


def graphic_digest(data,objects, *, titleblock_design=None, original=None, named_context=False):
    sch={s['objectId']:s['name'] for s in data['schematic']}
    pages={p['objectId']:[sch[p['schematicId']],p['name']] for p in data['page']}
    parts={p['objectId']:p['reference'] for p in data['part']}
    original_pages = {p['objectId']:p['name'] for p in (original or data)['page']}
    rows=[]
    for obj in objects:
        attrs=copy.deepcopy(obj['attributes']);owner=attrs.pop('partId',None)
        if owner is not None:attrs['ownerReference']=parts[owner]
        if titleblock_design is not None and obj['kind']=='titleblock':
            page_id = obj['pageId']
            attrs = titleblock_content(attrs, original_pages[page_id], pages[page_id][1], titleblock_design,
                                       named_context=named_context)
            attrs['nativeId'] = obj['nativeId']
        rows.append([obj['kind'],pages[obj['pageId']],attrs])
    return digest(sorted(rows,key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False)))

def meta_digest(meta):
    return digest({'rootName':meta['rootName'],'schematics':sorted(s['name'] for s in meta['schematics']),
                   'pages':sorted(meta['pages'],key=lambda p:(p['schematicName'],p['name']))})

class CapturePageEdits(CapturePages):
    operations = ('create', 'rename', 'delete')

    def plan(self, session_id, operation, schematic_id, page_id, name):
        if operation in ('create', 'rename') and isinstance(name, str):
            require_native_document_encoding(name)
        return super().plan(session_id, operation, schematic_id, page_id, name)

    # Same persistent kind as existing native-tested page plans; older plans
    # without stronger baselines must not pass verification as a new plan.
    def plan_payload(self,session,data,expected,payload):
        sid=session['sessionId'] if 'sessionId' in session else next(k for k,v in self.capture.sessions.items() if v is session)
        connections=inventory(self.capture,sid)
        graphics = read_inventory(self.capture, sid, 'graphics', titleblock_users=True)
        meta=read_document_meta(self.config,session['design'],session['design'].parent)
        expected_meta=copy.deepcopy(meta)
        if payload['operation']=='create':
            expected_meta['pages'].append({'schematicName':payload['schematicName'],'name':payload['name'],'counts':{k:0 for k in COUNT_KEYS}})
        else:
            target = next((page for page in expected_meta['pages'] if
                           (page['schematicName'], page['name']) == (payload['schematicName'], payload['oldName'])), None)
            if target is None:
                raise CadenceError('page_metadata_mismatch', 'Native page metadata cannot bind the target.')
            if payload['operation'] == 'delete':
                target_id, = {row['objectId'] for row in data['page']} - {row['objectId'] for row in expected['page']}
                if any(target['counts'].values()) or any(
                    row['pageId'] == target_id for row in (*connections, *graphics)
                ):
                    raise CadenceError('page_not_empty', 'Native counts, connection objects and graphics must all show an empty page.')
                expected_meta['pages'].remove(target)
            else:
                target['name'] = payload['name']
        return self.freeze_content(sid, session, data, expected, payload, connections, graphics, expected_meta)

    def freeze_content(self, sid, session, data, expected, payload, connections, graphics, expected_meta):
        named_context = session['design'].name.casefold() != 'design.dsn' or self.design_relative_path(payload).casefold() != 'design.dsn'
        profile = TITLEBLOCK_NAMED_CONTEXT_PROFILE if named_context else TITLEBLOCK_CONTEXT_PROFILE
        payload.update(expectedConnectionDigest=connection_digest(expected,connections),
                       expectedGraphicDigest=graphic_digest(expected, graphics, titleblock_design=session['design'],
                                                            original=data, named_context=named_context),
                       graphicBaselineProfile=profile, expectedMetaDigest=meta_digest(expected_meta))
        if len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))>48000:raise CadenceError('plan_limit','Document baseline exceeds durable record bound.')
        self.capture._session(sid);return payload
    def verify_content(self,verifier,sid,p):
        if not all(k in p for k in ('expectedConnectionDigest','expectedGraphicDigest','expectedMetaDigest')):
            raise CadenceError('invalid_plan','Legacy internal page plans lack the required content baselines.')
        session=verifier._session(sid);data=session['data']
        if connection_digest(data,inventory(verifier,sid))!=p['expectedConnectionDigest']:raise CadenceError('page_connection_mismatch','Page operation changed connection-object baseline.','verify')
        profile = p.get('graphicBaselineProfile')
        if profile in (TITLEBLOCK_CONTEXT_PROFILE, TITLEBLOCK_NAMED_CONTEXT_PROFILE):
            graphics = read_inventory(verifier, sid, 'graphics', titleblock_users=True)
            actual_graphic_digest = graphic_digest(data, graphics, titleblock_design=session['design'],
                                                   named_context=profile == TITLEBLOCK_NAMED_CONTEXT_PROFILE)
        else:
            # Retain the original digest for pre-profile internal plans.
            query_objects(verifier,sid,'graphics','graphic',None,None,1)
            actual_graphic_digest = graphic_digest(data, session['objectInventories']['graphics'])
        if actual_graphic_digest != p['expectedGraphicDigest']:
            raise CadenceError('page_graphic_mismatch','Page operation changed graphic/part/display baseline.','verify')
        meta=read_document_meta(self.config,session['design'],session['design'].parent)
        if meta_digest(meta)!=p['expectedMetaDigest']:raise CadenceError('page_metadata_mismatch','Page root or native content counts differ from the explicit plan.','verify')
    def verify(self,directory,p,native_completed):
        result=super().verify(directory,p,native_completed)
        result.update(connectionAndGraphicBaselineVerified=True,nativeRootAndPageCountsVerified=True)
        result['notChecked']+=['generated_titleblock_modification_values','custom_plugin_objects',
                               'bus_member_semantics','erc_bookmark_details','native_cached_bounds_rendering']
        return result
