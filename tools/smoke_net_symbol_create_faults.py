"""Real source-bound symbol native faults; never modifies installation library."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.library import LibraryService
from cadence_mcp.net_symbols import query_net_symbols
from cadence_mcp.capture_net_symbol_create import CaptureNetSymbolCreates
class LoseReceipt(CaptureNetSymbolCreates):
 def verify(self,d,p,native_completed):
  if native_completed:(d/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Owned test removes receipt after native completion.')
  return super().verify(d,p,native_completed)
class CancelAtStart(CaptureNetSymbolCreates):
 def execute(self,d,p,cancel,on_started):
  def started(pid):on_started(pid);cancel.set()
  return super().execute(d,p,cancel,started)
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);olb=(a.install_root/'tools/capture/library/capsym.olb').resolve(strict=True);report={'passed':False,'sourceBefore':sha256(a.source),'libraryBefore':sha256(olb),'cases':[]}
expected=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':ref,'pinNumber':num,'connected':(ref,num)!=('R102','2'),'net':'MCP_SUPPLY' if (ref,num)==('R101','1') else 'MCP_MIDDLE' if (ref,num) in {('R101','2'),('R102','1')} else None} for ref in ('R101','R102') for num in ('1','2')]
for mode,cls in [('receipt_loss',LoseReceipt),('cancel_at_start',CancelAtStart),('timeout',CaptureNetSymbolCreates)]:
 row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  normal=Config(a.install_root,root/mode,(a.source.parent,olb.parent),60);cap=CaptureService(normal);ws=cap.create_workspace(str(a.source));sid=cap.open(ws['workspaceId'])['sessionId'];page=next(p for p in cap.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE');library=LibraryService(normal);lid=library.open(str(olb))['libraryId'];query_net_symbols(library,lid,limit=1);symbol=next(s for s in library.sessions[lid]['netSymbols'] if s['kind']=='global' and s['name']=='VCC')
  cfg=Config(a.install_root,root/mode,(a.source.parent,olb.parent),1 if mode=='timeout' else 60);writer=cls(cfg,cap,library);plan=writer.plan(sid,page['objectId'],lid,symbol['symbolId'],'MCP_SUPPLY',[230,300],[240,310],expected,0,0,[290,310]);row['plan']=plan
  try:writer.apply(plan['planId'],plan['planDigest'],mode)
  except CadenceError as e:assert e.code=={'receipt_loss':'receipt_lost_fixture','cancel_at_start':'operation_cancelled','timeout':'timeout'}[mode],e.code;row['errorCode']=e.code
  else:raise AssertionError('Expected owned native fault not observed')
  d=writer.root/('plan-'+plan['planId']);ledger=json.loads((d/'plan.json').read_text());row['process']=ledger['process'];assert ledger['process']['remainingOwnedProcesses']==0
  if mode=='receipt_loss':
   before=sha256(d/'design.dsn');fresh=CaptureNetSymbolCreates(normal,CaptureService(normal),LibraryService(normal));value=fresh.recover(plan['planId'],plan['planDigest']);assert value['state']=='verified_recovered' and not value['nativeCompletionVerified'] and value['artifact']['sha256']==before==sha256(d/'design.dsn');fresh.open_output(plan['planId'],plan['planDigest']);row['recovered']=value
  else:
   try:writer.apply(plan['planId'],plan['planDigest'],mode)
   except CadenceError as e:assert e.code=='write_not_replayed'
   else:raise AssertionError('Faulted creation replayed')
  row['passed']=True
 except BaseException as e:row.update(error=str(e),errorType=type(e).__name__)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report.update(sourceAfter=sha256(a.source),libraryAfter=sha256(olb));report['passed']=all(c['passed'] for c in report['cases']) and report['sourceBefore']==report['sourceAfter'] and report['libraryBefore']==report['libraryAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
