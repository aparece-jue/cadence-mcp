"""Missing-device receipt-loss fresh MCP recovery and owned cancel/timeout faults."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from unittest.mock import patch
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_multiunit_place import CaptureMultiunitPlacements
from cadence_mcp.capture_references import read_units
from cadence_mcp.capture_unit_edit import cache_digest
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','spec'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);a.source=a.source.resolve(strict=True);spec=json.loads(a.spec.read_text(encoding='utf-8'));before=sha256(a.source);report={'passed':False,'sourceBefore':before,'cases':[]}
class LostReceipt(CaptureMultiunitPlacements):
 def verify(self,directory,p,native_completed):
  if native_completed:(directory/'native-result.json').unlink();raise CadenceError('receipt_lost_fixture','Private test removes completion receipt after native save.','verify')
  return super().verify(directory,p,native_completed)
class CancelAtStart(CaptureMultiunitPlacements):
 def execute(self,directory,p,cancel,on_started):
  def started(pid):on_started(pid);cancel.set()
  return super().execute(directory,p,cancel,started)
class Delayed(CaptureMultiunitPlacements):
 def execute(self,directory,p,cancel,on_started):
  wrapper=directory/'delayed-cached-unit.tcl';wrapper.write_text('set production [lindex $argv end]\nset argv [lrange $argv 0 end-1]\nset argc [llength $argv]\nafter 2000\nsource $production\n',encoding='utf-8')
  def launch(argv,cwd,env,timeout_seconds,**kw):
   argv=list(argv);original=argv[1];argv[1]=wrapper;argv.append(original);return run_owned_process(argv,cwd,env,timeout_seconds,**kw)
  with patch('cadence_mcp.capture_cached_unit_add.run_owned_process',side_effect=launch):return super().execute(directory,p,cancel,on_started)
for mode,cls in [('receipt_loss',LostReceipt),('cancel_at_start',CancelAtStart),('timeout',Delayed)]:
 row={'mode':mode,'passed':False};report['cases'].append(row)
 try:
  normal=Config(a.install_root,root/mode,(a.source.parent,),60);cap=CaptureService(normal);sid=cap.open(cap.create_workspace(str(a.source))['workspaceId'])['sessionId'];identities=read_units(cap,sid);owner=next(u for u in identities.values() if u['referenceDesignator']=='U501A');cache_digest(cap,sid);cache=cap.sessions[sid]['cacheDefinitions'];package=next(p for p in cache['package'] if p['name']==owner['packageName']);device=next(d for d in cache['device'] if d['packageId']==package['objectId'] and d['designator']=='P');part=next(p for p in cache['part'] if p['deviceId']==device['objectId'] and p['name'].endswith('.Normal'));dev=next(d for d in spec['devices'] if d['designator']=='P');symbol=next(s for s in spec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith('.Normal'));mapping={p['position']:p['number'] for p in dev['mapping']};pins=[{'number':mapping[p['position']],'name':p['name'],'hotSpot':[1400+p['hotSpot'][0],700+p['hotSpot'][1]],'connected':True,'net':p['name']} for p in symbol['pins']];ownerpart=next(p for p in cap.sessions[sid]['data']['part'] if p['objectId']==owner['partId']);existing=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in cap.sessions[sid]['data']['pin'] if p['pageId']==ownerpart['pageId']];cfg=Config(normal.install_root,normal.workspace_root,normal.read_roots,1 if mode=='timeout' else 60);writer=cls(cfg,cap,None);plan=writer.plan_add(sid,owner['partId'],part['objectId'],[1400,700],0,0,pins,existing);row['plan']=plan
  try:writer.apply(plan['planId'],plan['planDigest'],mode);raise AssertionError('Expected fault absent')
  except CadenceError as e:assert e.code=={'receipt_loss':'receipt_lost_fixture','cancel_at_start':'operation_cancelled','timeout':'timeout'}[mode],(e.code,str(e))
  directory,path,ledger=writer._load(plan['planId']);row['process']=ledger['process'];assert ledger['process']['remainingOwnedProcesses']==0
  if mode=='receipt_loss':
   saved=sha256(directory/'design.dsn')
   async def recover():
    env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(normal.install_root),'--workspace-root',str(normal.workspace_root),'--read-root',str(a.source.parent)],env=env)
    async with Client(params,mode='legacy',read_timeout_seconds=300) as client:
     key={k:plan[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_recover_multiunit_placement',key);assert not v.is_error,v.content;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'multiunit_placement'})).is_error;return v.structured_content['data']
   restored=asyncio.run(recover());assert not restored['nativeCompletionVerified'] and not restored['mutationReplayed'] and restored['cachedViewVerified'] and restored['nativePageNetworksVerified'];assert sha256(directory/'design.dsn')==saved;row['recovered']=restored
  else:
   try:writer.apply(plan['planId'],plan['planDigest'],mode);raise AssertionError('Fault replayed')
   except CadenceError as e:assert e.code=='write_not_replayed'
  row['passed']=sha256(a.source)==before
 except BaseException as e:
  import traceback
  row.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(mode,row['passed'],row.get('error'),flush=True)
report['passed']=all(c['passed'] for c in report['cases']) and sha256(a.source)==before;(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)
