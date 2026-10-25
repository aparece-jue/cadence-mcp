"""Native pin-style faults preserve original OLB and never replay uncertain mutations."""
import argparse,json,shutil
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError,sha256,write_json
from cadence_mcp.library import LibraryService
from cadence_mcp.library_edit import LibraryPinEdits
from cadence_mcp.library_pin_style import query_style,scopes
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process

class LoseReceipt(LibraryPinEdits):
 def verify(self,d,p,native_completed):
  if native_completed:(d/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Private fault removes completed receipt.')
  return super().verify(d,p,native_completed)
class CancelAtStart(LibraryPinEdits):
 def execute(self,d,p,event,started):
  def ready(pid):started(pid);event.set()
  return super().execute(d,p,event,ready)
class CorruptOtherFlag(LibraryPinEdits):
 def execute(self,d,p,event,started):
  result=super().execute(d,p,event,started);assert result['returnCode']==0
  lib=LibraryService(Config(self.config.install_root,self.config.workspace_root,(d,),60));lid=lib.open(str(d/'library.olb'))['libraryId'];data=lib.sessions[lid]['data'];part=next(t for t in data['part'] if t['name']=='RES.Convert');pin=next(t for t in data['pin'] if t['partId']==part['objectId'] and t['position']==1);scope=scopes(data)[pin['objectId']];flags=query_style(lib,lid,pin['objectId'])['flags'];assert flags['dot'] is False;lib.close(lid)
  spec={'targetPin':pin['objectId'],'expectedName':pin['name'],'expectedNumber':pin['number'],'expectedType':pin['pinType'],'expectedPosition':pin['position'],'identity':dict(zip(('packageName','deviceDesignator','devicePosition','cellName','partName'),scope[:5])),'changeName':False,'newName':'','changeNumber':False,'newNumber':'','changeType':False,'newType':0,'pinStyle':{'dot':True},'expectedStyle':flags};write_json(d/'other-flag-request.json',spec)
  self.other_process=run_owned_process([self.config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'edit_library_pin.tcl',self.config.install_root,d/'library.olb',d/'other-flag-request.json',d/'other-receipt.json'],d,process_env(self.config),60);assert self.other_process['returnCode']==0 and self.other_process['remainingOwnedProcesses']==0
  return result

p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--mode',choices=['receipt_loss','cancel_at_start','native_timeout','other_flag'])
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve();before=sha256(source);report={'passed':False,'sourceBefore':before,'cases':[]}
for mode,cls in [('receipt_loss',LoseReceipt),('cancel_at_start',CancelAtStart),('native_timeout',LibraryPinEdits),('other_flag',CorruptOtherFlag)]:
 if a.mode and mode!=a.mode:continue
 row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  cfg=Config(a.install_root.resolve(),root/mode,(source.parent,),60);lib=LibraryService(cfg);lid=lib.open(str(source))['libraryId'];data=lib.sessions[lid]['data'];part=next(t for t in data['part'] if t['name']=='RES.Normal');target=next(t for t in data['pin'] if t['partId']==part['objectId'] and t['position']==0);scope=scopes(data)[target['objectId']];writer=cls(cfg,lib);plan=writer.plan(lid,target['objectId'],style={'dot':True});row['plan']=plan
  def apply():return writer.apply(plan['planId'],plan['planDigest'],mode)
  try:
   if mode=='native_timeout':
    delayed=root/'delayed';delayed.mkdir();text=(ADAPTERS/'edit_library_pin.tcl').read_text(encoding='utf-8');assert 'set phase set_pin_style;' in text;delay='set marker [open [file join [file dirname $output] before-style-delay.txt] w];puts $marker ready;close $marker;after 2000;set phase set_pin_style;';(delayed/'edit_library_pin.tcl').write_text(text.replace('set phase set_pin_style;',delay),encoding='utf-8')
    for name in ('json.tcl','dbo_pin_style.tcl'):shutil.copy2(ADAPTERS/name,delayed/name)
    writer.config=Config(cfg.install_root,cfg.workspace_root,cfg.read_roots,1)
    with patch('cadence_mcp.library_edit.ADAPTERS',delayed):apply()
   else:apply()
   raise AssertionError('Expected native fault was accepted')
  except CadenceError as error:
   expected={'receipt_loss':'receipt_lost_fixture','cancel_at_start':'operation_cancelled','native_timeout':'timeout','other_flag':'library_pin_style_mismatch'}[mode];assert error.code==expected,(error.code,expected);row['errorCode']=error.code
  directory,_,ledger=writer._load(plan['planId']);row['process']=ledger['process'];assert row['process']['remainingOwnedProcesses']==0
  if mode=='native_timeout':assert (directory/'before-style-delay.txt').read_text().strip()=='ready';row['nativeStyleLookupReachedBeforeTimeout']=True
  if mode=='receipt_loss':
   artifact=sha256(directory/'library.olb');fresh=LibraryPinEdits(cfg,LibraryService(cfg));result=fresh.recover(plan['planId'],plan['planDigest']);assert result['nativePinStylesVerified'] and not result['nativeCompletionVerified'] and result['state']=='verified_recovered';opened=fresh.open_output(plan['planId'],plan['planDigest']);newdata=fresh.library.sessions[opened['libraryId']]['data'];target_id=next(key for key,value in scopes(newdata).items() if value==scope);assert query_style(fresh.library,opened['libraryId'],target_id)['flags']['dot'] is True;assert sha256(directory/'library.olb')==artifact;row['recovered']=result
  else:
   try:writer.apply(plan['planId'],plan['planDigest'],mode);raise AssertionError('Fault mutation replayed')
   except CadenceError as error:assert error.code=='write_not_replayed'
   if mode=='other_flag':
    try:writer.recover(plan['planId'],plan['planDigest']);raise AssertionError('Corrupt unrelated flag recovered')
    except CadenceError as error:assert error.code=='library_pin_style_mismatch'
    row['otherFlagProcess']=writer.other_process
  row['passed']=True
 except BaseException as error:row.update(error=str(error),errorType=type(error).__name__)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceAfter']=sha256(source);report['passed']=all(c['passed'] for c in report['cases']) and before==report['sourceAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if not report['passed']:raise SystemExit(1)
