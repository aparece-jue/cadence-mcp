"""Native worker faults, fresh MCP recovery and unrelated-view corruption refusal."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256,write_json
from cadence_mcp.library import LibraryService
from cadence_mcp.library_vector_query import query_library_vectors
from cadence_mcp.library_vector_edit import LibraryVectorEdits
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','library-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=(a.library_root/'library.olb').resolve(strict=True);before=sha256(source)
cfg=Config(a.install_root,root/'work',(source.parent,),60);library=LibraryService(cfg);lid=library.open(str(source))['libraryId'];data=library.sessions[lid]['data']
device=next(d for d in data['device'] if d['designator']=='A');part=next(p for p in data['part'] if p['deviceId']==device['objectId'] and p['name'].endswith('.Normal'))
convert=next(p for p in data['part'] if p['deviceId']==device['objectId'] and p['name'].endswith('.Convert'))
vectors=query_library_vectors(library,lid,part['objectId'],None,1000)['items'];text=next(v for v in vectors if v['kind']=='bitmap')
other_vectors=query_library_vectors(library,lid,convert['objectId'],None,1000)['items']
replacement={'bounds':[3,4,43,34],'location':[7,9],'expectedDibSha256':text['descriptor'][5]}
(root/'expected.json').write_text(json.dumps({'sourceHash':before,'sourcePart':part,'replacement':replacement,'unrelatedVectors':other_vectors},ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
creator=LibraryVectorEdits(cfg,library);native=creator.execute;calls=0
report={'passed':False,'checks':{}}
def plan(service):return service.plan(lid,part['objectId'],text['objectId'],'update',None,replacement)
async def main():
 global calls
 try:
  lost=plan(creator);key={k:lost[k] for k in ('planId','planDigest')};report['lostPlan']=lost
  def lose_receipt(d,p,cancel,started):
   global calls
   calls+=1;process=native(d,p,cancel,started);assert process['returnCode']==0 and process['remainingOwnedProcesses']==0
   (d/'native-result.json').unlink();return process
  creator.execute=lose_receipt
  try:creator.apply(key['planId'],key['planDigest'],'lost');raise AssertionError('Missing receipt accepted')
  except CadenceError as error:report['lostError']=error.code
  d,_,row=creator._load(key['planId']);assert row['state']=='failed';saved=sha256(d/'library.olb');report['lostProcess']=row['process']
  env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
  params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(cfg.workspace_root),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   async def call(name,args):
    r=await fresh.call_tool(name,args);assert not r.is_error,(name,r.content);return r.structured_content['data']
   result=await call('capture_recover_library_vector_edit',key)
   assert result['state']=='verified_recovered' and not result['nativeCompletionVerified'] and not result['mutationReplayed']
   assert result['declaredVectorEditVerified'] and result['modeledLibraryPreservationVerified'];report['recovered']=result
   opened=await call('capture_open_edited_library',{**key,'kind':'vector'})
   parts=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'part','limit':1000}))['items']
   assert len(parts)==4
   for part_row in parts:
    items=(await call('capture_query_library_vectors',{'libraryId':opened['libraryId'],'partId':part_row['objectId'],'limit':1000}))['items'];assert len(items)==(14 if part_row['name'].endswith('.Normal') else 13)
    if part_row['name'].endswith('.Normal'):assert next(v for v in items if v['kind']=='bitmap')['descriptor']==['bitmap',replacement['bounds'],replacement['location'],2*[2],56,replacement['expectedDibSha256']]
   assert not (await call('capture_apply_library_vector_edit',{**key,'idempotencyKey':'lost'}))['mutationReplayed']
  assert calls==1 and sha256(d/'library.olb')==saved;report['checks']['fresh_mcp_receipt_recovery_no_replay']=True
  creator.execute=native;cancel=plan(creator);report['cancelPlan']=cancel
  def stop_at_start(d,p,event,started):
   def ready(pid):started(pid);assert creator.cancel(cancel['planId'],cancel['planDigest'])['cancelRequested']
   return native(d,p,event,ready)
  creator.execute=stop_at_start
  try:creator.apply(cancel['planId'],cancel['planDigest'],'cancel');raise AssertionError('Cancelled native accepted')
  except CadenceError as error:assert error.code=='operation_cancelled',error.code
  process=creator._load(cancel['planId'])[2]['process'];assert process['remainingOwnedProcesses']==0;report['cancelProcess']=process;report['checks']['native_start_cancel']=True
  timeout=LibraryVectorEdits(cfg,library);timed=plan(timeout);report['timeoutPlan']=timed
  timeout.config=Config(cfg.install_root,cfg.workspace_root,(source.parent,),1)
  delay=root/'delayed-edit.py';delay.write_text('import time\ntime.sleep(2)\nfrom cadence_mcp.embedded_tcl import main\nraise SystemExit(main())\n',encoding='utf-8');command=timeout.native_command
  timeout.native_command=lambda d,p:[command(d,p)[0],str(delay),*command(d,p)[3:]]
  try:timeout.apply(timed['planId'],timed['planDigest'],'timeout');raise AssertionError('Timeout accepted')
  except CadenceError as error:assert error.code=='timeout',error.code
  process=timeout._load(timed['planId'])[2]['process'];assert process['state']=='timeout' and process['remainingOwnedProcesses']==0;report['timeoutProcess']=process;report['checks']['delayed_native_timeout']=True
  poisoned=LibraryVectorEdits(cfg,library);bad=plan(poisoned);report['poisonPlan']=bad;execute=poisoned.execute
  def corrupt_other_view(d,p,cancel,started):
   process=execute(d,p,cancel,started);assert process['returnCode']==0
   scope=list(p['scope']);scope[-1]=convert['name']
   spec={'scope':scope,'index':0,'old':other_vectors[0]['descriptor'],'operation':'update',
         'replacement':{'kind':'line','start':[0,0],'end':[50,0],'style':4,'width':2},'vectorId':'test-unrelated-view',
         'affectedScopes':[s[:-1]+[convert['name']] for s in p['affectedScopes']]}
   write_json(d/'poison-request.json',spec)
   corrupt=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'edit_library_vector.tcl'),str(cfg.install_root),str(d/'library.olb'),str(d/'poison-request.json'),str(d/'poison-receipt.json')],d,process_env(cfg),60)
   assert corrupt['returnCode']==0 and corrupt['remainingOwnedProcesses']==0;report['poisonProcess']=corrupt
   return process
  poisoned.execute=corrupt_other_view
  try:poisoned.apply(bad['planId'],bad['planDigest'],'poison');raise AssertionError('Unrelated-view change accepted')
  except CadenceError as error:assert error.code=='library_vector_mismatch',error.code
  try:poisoned.open_output(bad['planId'],bad['planDigest']);raise AssertionError('Poisoned output opened')
  except CadenceError as error:assert error.code=='output_unverified',error.code
  try:poisoned.apply(bad['planId'],bad['planDigest'],'poison');raise AssertionError('Poisoned mutation replayed')
  except CadenceError as error:assert error.code=='write_not_replayed',error.code
  report['checks']['unrelated_convert_view_corruption_refused']=True
  # Independent terminal output used only for hash-tamper rejection; retain exact pre-tamper bytes.
  tamper=LibraryVectorEdits(cfg,library);t=plan(tamper);result=tamper.apply(t['planId'],t['planDigest'],'tamper');report['tamperPlan']=t
  directory,_,_=tamper._load(t['planId']);target=directory/'library.olb';(root/'retained-before-tamper.olb').write_bytes(target.read_bytes());target.write_bytes(target.read_bytes()+b'PRIVATE TEST TAMPER')
  for operation in (lambda:tamper.open_output(t['planId'],t['planDigest']),lambda:tamper.recover(t['planId'],t['planDigest']),lambda:tamper.apply(t['planId'],t['planDigest'],'tamper')):
   try:operation();raise AssertionError('Tampered output accepted')
   except CadenceError as error:assert error.code=='target_changed',error.code
  report['checks']['terminal_output_tamper_refused']=True
  report['sourceAndOracleUnchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
  report['passed']=report['sourceAndOracleUnchanged'] and all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
