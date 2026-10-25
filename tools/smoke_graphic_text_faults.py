"""Native fault and unrelated-graphic preservation tests for page text tasks."""
import argparse,json
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_graphic_text import CaptureGraphicTexts
from cadence_mcp.capture_page_vectors import query_page_vectors
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
class LoseReceipt(CaptureGraphicTexts):
 def verify(self,d,p,native_completed):
  if native_completed:(d/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Private fault after completed native write.')
  return super().verify(d,p,native_completed)
class CancelAtStart(CaptureGraphicTexts):
 def execute(self,d,p,event,started):
  def ready(pid):started(pid);event.set()
  return super().execute(d,p,event,ready)
class ExtraGraphic(CaptureGraphicTexts):
 def execute(self,d,p,event,started):
  result=super().execute(d,p,event,started);assert result['returnCode']==0
  self.extra=run_owned_process([self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'graphic_line_probe.tcl',self.config.install_root,d/'design.dsn',d/'extra-receipt.json',p['schematicName'],p['pageName'],'10','20','30','40','add'],d,process_env(self.config),60);assert self.extra['returnCode']==0 and self.extra['remainingOwnedProcesses']==0
  return result
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument("--mode",choices=("receipt_loss","cancel_at_start","native_timeout","extra_graphic"))
p.add_argument("--operation",choices=("add","update","delete"),default="add")
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve();before=sha256(source);report={'passed':False,'cases':[],'sourceSha256':before,'operation':a.operation}
for mode,cls in [('receipt_loss',LoseReceipt),('cancel_at_start',CancelAtStart),('native_timeout',CaptureGraphicTexts),('extra_graphic',ExtraGraphic)]:
 if a.mode and mode!=a.mode:continue
 row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  cfg=Config(a.install_root,root/mode,(source.parent,),60);cap=CaptureService(cfg);sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];page=next(p for p in cap.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE');writer=cls(cfg,cap);change={'text':'fault text [x]$;\n中文','location':[300,450],'width':180,'height':40,'rotation':1,'mirror':1,'font':{}}
  if a.operation=='add':plan=writer.plan(sid,page['objectId'],change['text'],change['location'],180,40,1,1,{})
  else:
   target=next(v for v in query_page_vectors(cap,sid,page['objectId'],limit=1000)['items'] if v['kind']=='text');plan=writer.plan_edit(sid,target['objectId'],a.operation,None if a.operation=='delete' else change)
  row['plan']=plan
  try:
   if mode=='native_timeout':
    delayed=root/'delayed';delayed.mkdir();script=(ADAPTERS/'write_graphic_text.tcl').read_text(encoding='utf-8')
    for name in ('json.tcl','dbo_qualified_page.tcl'):script=script.replace('[file join [file dirname [info script]] '+name+']','{'+(ADAPTERS/name).as_posix()+'}')
    script=script.replace('set session [DboTclHelper_sCreateSession]', 'set f [open [file join [file dirname $output] before-delay.txt] w];puts $f ready;close $f;after 5000;set session [DboTclHelper_sCreateSession]');(delayed/'write_graphic_text.tcl').write_text(script,encoding='utf-8')
    def timed(command,cwd,env,timeout,**kw):return run_owned_process([delayed/'write_graphic_text.tcl' if str(v)==str(ADAPTERS/'write_graphic_text.tcl') else v for v in command],cwd,env,3,**kw)
    with patch('cadence_mcp.capture_edit.run_owned_process',timed):writer.apply(plan['planId'],plan['planDigest'],mode)
   else:writer.apply(plan['planId'],plan['planDigest'],mode)
   raise AssertionError('Expected refusal')
  except CadenceError as e:row['errorCode']=e.code
  d,_,ledger=writer._load(plan['planId']);row['process']=ledger['process'];assert ledger['process']['remainingOwnedProcesses']==0
  fresh=CaptureGraphicTexts(cfg,cap)
  if mode=='receipt_loss':
   assert row['errorCode']=='receipt_lost_fixture';out_before=sha256(d/'design.dsn');recovered=fresh.recover(plan['planId'],plan['planDigest']);assert recovered['state']=='verified_recovered' and not recovered['nativeCompletionVerified'] and sha256(d/'design.dsn')==out_before;row['recovered']=recovered
  else:
   assert row['errorCode']=={'cancel_at_start':'operation_cancelled','native_timeout':'timeout','extra_graphic':'graphic_text_mismatch'}[mode]
   try:fresh.apply(plan['planId'],plan['planDigest'],mode)
   except CadenceError:pass
   else:raise AssertionError('Must not replay')
   if mode=='extra_graphic':
    try:fresh.recover(plan['planId'],plan['planDigest'])
    except CadenceError as e:assert e.code=='graphic_text_mismatch'
    else:raise AssertionError('Must reject unrelated extra graphic')
    row['extraProcess']=writer.extra
   if mode=='native_timeout':assert (d/'before-delay.txt').read_text().strip()=='ready';row['loadedDllBeforeTimeout']=True
  cap.close(sid);row['passed']=True
 except Exception as e:row['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'mode':mode,'passed':row['passed'],'error':row.get('error'),'errorCode':row.get('errorCode')},ensure_ascii=True),flush=True)
report['sourceUnchanged']=sha256(source)==before;report['passed']=all(c['passed'] for c in report['cases']) and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
