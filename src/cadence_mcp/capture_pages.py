"""Create/rename pages in isolated DSN outputs with explicit definition expectations."""
from datetime import datetime,timezone
import copy,json,re
from .capture import CaptureService
from .capture_edit import CapturePropertyEdits,definition_baseline
from .core import CadenceError,checked_path,sha256
from .environment import ADAPTERS


class CapturePages(CapturePropertyEdits):
    kind='capture_page'
    def plan(self,session_id,operation,schematic_id,page_id,name):
        if operation not in ('create','rename') or not isinstance(name,str) or not re.fullmatch(r'\w[\w .-]{0,63}',name) or name.strip(' .')!=name:
            raise CadenceError('invalid_page_change','Provide create/rename and a bounded page name without path/control characters.')
        with self.capture.lock:
            session=self.capture._session(session_id);data=session['data']
            schematic=next((s for s in data['schematic'] if s['objectId']==schematic_id),None)
            if schematic is None:raise CadenceError('object_not_found','Schematic is outside this session.')
            if sum(s['name']==schematic['name'] for s in data['schematic'])!=1:raise CadenceError('ambiguous_target','Schematic name is not unique.')
            siblings=[p for p in data['page'] if p['schematicId']==schematic_id]
            if any(p['name'].casefold()==name.casefold() for p in siblings):raise CadenceError('page_name_conflict','Page name already exists, ignoring case.')
            expected=copy.deepcopy(data);old_name=''
            if operation=='create':
                if page_id is not None:raise CadenceError('invalid_page_change','Creation does not accept an existing page ID.')
                expected['page'].append({'objectId':'planned-new-page','schematicId':schematic_id,'name':name,'generation':1})
            else:
                page=next((p for p in siblings if p['objectId']==page_id),None)
                if page is None:raise CadenceError('object_not_found','Page does not belong to the selected schematic.')
                old_name=page['name']
                if sum(p['name']==old_name for p in siblings)!=1:raise CadenceError('ambiguous_target','Old page name is not unique.')
                next(p for p in expected['page'] if p['objectId']==page_id)['name']=name
            payload={'sourceDesign':str(session['design']),'sourceFingerprint':session['revision'],
                'operation':operation,'schematicName':schematic['name'],'oldName':old_name,'name':name,
                'expectedDefinitionDigest':definition_baseline(expected),'beforeDefinitionDigest':definition_baseline(data)}
            return self.create_plan(self.plan_payload(session,data,expected,payload))

    def plan_payload(self,session,data,expected,payload):return payload

    def verify_content(self,verifier,sid,payload):pass

    def preview(self,payload):return {k:payload[k] for k in ('operation','schematicName','oldName','name','sourceFingerprint')}

    def preflight(self,payload):
        source=checked_path(payload['sourceDesign'],(self.config.workspace_root,))
        if source.suffix.lower()!='.dsn' or sha256(source)!=payload['sourceFingerprint']:raise CadenceError('target_changed','Source design changed after planning.')
        if payload['operation'] not in ('create','rename'):raise CadenceError('invalid_plan','Unsupported page operation.')

    def native_command(self,directory,payload):
        return [self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_page.tcl',self.config.install_root,
                directory/'design.dsn',directory/'native-result.json',payload['operation'],payload['schematicName'],payload['oldName'],payload['name']]

    def verify(self,directory,payload,native_completed):
        target=checked_path(str(directory/'design.dsn'),(directory,));before=sha256(target)
        if native_completed:
            receipt=directory/'native-result.json'
            if receipt.stat().st_size>4096 or json.loads(receipt.read_text(encoding='utf-8'))!={'saved':True,'operation':payload['operation'],'schematicName':payload['schematicName'],'name':payload['name']}:
                raise CadenceError('invalid_worker_result','Native page save receipt mismatch.','verify')
        verifier=CaptureService(self.config);verifier.workspaces['verify']={'directory':directory,'manifest':{'copiedFingerprint':before}}
        opened=verifier.open('verify');sid=opened['sessionId']
        try:
            if definition_baseline(verifier.sessions[sid]['data'])!=payload['expectedDefinitionDigest']:
                raise CadenceError('page_verification_failed','Saved pages, parts or pin nets differ from the explicit planned definition changes.','verify')
            self.verify_content(verifier,sid,payload)
        finally:verifier.close(sid)
        self.preflight(payload)
        if sha256(target)!=before:raise CadenceError('target_changed','Output changed during page verification.')
        ident=directory.name.removeprefix('plan-')
        artifact={'artifactId':'page-'+ident,'kind':'capture_edited_design','workspaceRelativePath':'design.dsn','sha256':before,
                  'size':target.stat().st_size,'producedByJob':ident,'sourceFingerprint':payload['sourceFingerprint'],
                  'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'validated'}
        return {'planId':ident,'state':'verified' if native_completed else 'verified_recovered','artifact':artifact,
                'operation':payload['operation'],'schematicName':payload['schematicName'],'name':payload['name'],
                'nativeCompletionVerified':native_completed,'independentReopenVerified':True,'expectedDefinitionsVerified':True,
                'sourceModified':False,'outputWorkspaceRelativePath':directory.relative_to(self.config.workspace_root).as_posix(),
                'notChecked':['occurrence_connectivity','hierarchy_dependencies','graphic_layout','native_drc']}
