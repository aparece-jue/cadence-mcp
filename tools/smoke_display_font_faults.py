import argparse,json,traceback
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256,write_json
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_references import read_units
from cadence_mcp.capture_display_fonts import CaptureDisplayFonts,query_font,read_fonts
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
class LostReceipt(CaptureDisplayFonts):
 def verify(self,d,p,native_completed):
  if native_completed:(d/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Owned receipt removed after save.')
  return super().verify(d,p,native_completed)
class CancelAtStart(CaptureDisplayFonts):
 def execute(self,d,p,cancel,on_started):
  def started(pid):
   on_started(pid);row=self._load(d.name.removeprefix('plan-'))[2];assert self.cancel(row['plan']['planId'],row['digest'])['cancelRequested']
  return super().execute(d,p,cancel,started)
class CorruptOtherFont(CaptureDisplayFonts):
 def execute(self,d,p,cancel,on_started):
  process=super().execute(d,p,cancel,on_started);assert process['returnCode']==0
  cap=self.capture;sid=next(iter(cap.sessions));session=cap.sessions[sid];units=read_units(cap,sid);rows=read_fonts(self.config,session['design'],session['design'].parent,units);other=next(r for r in rows if r['nativeId']!=p['nativeId'] and r['fonts']);unit=next(u for u in units.values() if u['nativeId']==other['nativeId']);prop=other['fonts'][0];font=list(prop['font']);font[1]=-23 if font[1]!=-23 else -25
  request={k:unit[k] for k in ('nativeId','schematicName','pageName','reference')};request.update(property=prop['name'],oldFont=prop['font'],newFont=font,oldFontDefault=prop['fontDefault'],oldDefaultFontType=prop['defaultFontType']);write_json(d/'unrelated-request.json',request)
  changed=run_owned_process([self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_display_font.tcl',self.config.install_root,d/'design.dsn',d/'unrelated-request.json',d/'unrelated-receipt.json'],d,process_env(self.config),60,cancel=cancel,on_started=on_started);assert changed['returnCode']==0 and changed['remainingOwnedProcesses']==0;write_json(d/'unrelated-process.json',changed);return process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();source=a.source.resolve();root.mkdir(exist_ok=False);report={'passed':False,'sourceHashBefore':sha256(source),'cases':[]}
for mode,cls,code in [('receipt_loss',LostReceipt,'receipt_lost_fixture'),('cancel_at_start',CancelAtStart,'operation_cancelled'),('native_timeout',CaptureDisplayFonts,'timeout'),('unrelated_font_changed',CorruptOtherFont,'display_font_persistence_mismatch'),('changed_source',CaptureDisplayFonts,'target_changed'),('changed_expectation',CaptureDisplayFonts,'target_changed')]:
 row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  c=Config(a.install_root.resolve(),root/mode,(source.parent,),60);cap=CaptureService(c);writer=cls(c,cap);sid=cap.open(cap.create_workspace(str(source))['workspaceId'])['sessionId'];units=read_units(cap,sid);owner=next(u for u in units.values() if u['reference']=='U501' and u['deviceDesignator']=='A');old=query_font(cap,sid,owner['partId'],'Part Reference');plan=writer.plan(sid,owner['partId'],'Part Reference',{**old['font'],'height':-17,'weight':700,'italic':True,'quality':1});row['plan']=plan;payload=writer._load(plan['planId'])[2]['plan']['payload']
  if mode=='native_timeout':writer.config=Config(c.install_root,c.workspace_root,c.read_roots,1)
  if mode.startswith('changed_'):
   file=Path(payload['sourceDesign' if mode=='changed_source' else 'expectedEvidence']);file.write_bytes(file.read_bytes()+b'owned frozen input tamper')
  try:writer.apply(plan['planId'],plan['planDigest'],mode)
  except CadenceError as e:assert e.code==code,e.code;row['errorCode']=e.code
  else:raise AssertionError('Expected refusal absent')
  d,_,ledger=writer._load(plan['planId'])
  if mode.startswith('changed_'):assert ledger['state']=='planned' and not (d/'design.dsn').exists()
  else:
   row['process']=ledger['process'];assert row['process']['remainingOwnedProcesses']==0 and row['process']['rootExitSignalConfirmed'] and row['process']['observedProcessExitSignalsConfirmed']
   if mode=='native_timeout':assert row['process']['state']=='timeout'
   if mode=='receipt_loss':
    before=sha256(d/'design.dsn');fresh=CaptureDisplayFonts(c,CaptureService(c));result=fresh.recover(plan['planId'],plan['planDigest']);assert result['state']=='verified_recovered' and not result['nativeCompletionVerified'] and result['allDisplayFontsVerified'];assert sha256(d/'design.dsn')==before;row['recovered']=result
   else:
    try:writer.open_output(plan['planId'],plan['planDigest'])
    except CadenceError as e:assert e.code=='output_unverified'
    else:raise AssertionError('Unverified output opened')
    try:writer.apply(plan['planId'],plan['planDigest'],mode)
    except CadenceError as e:assert e.code=='write_not_replayed'
    else:raise AssertionError('Mutation replayed')
  row['passed']=True
 except BaseException as e:row.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceHashAfter']=sha256(source);report['passed']=all(row['passed'] for row in report['cases']) and report['sourceHashBefore']==report['sourceHashAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
