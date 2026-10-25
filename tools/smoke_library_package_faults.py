"""Package edit recovery/faults and unrelated package/vector preservation rejection."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256,write_json
from cadence_mcp.library import LibraryService
from cadence_mcp.library_package_edit import LibraryPackageEdits
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','library-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=(a.library_root/'library.olb').resolve(strict=True);before=sha256(source)
cfg=Config(a.install_root,root/'work',(source.parent,),60);library=LibraryService(cfg);lid=library.open(str(source))['libraryId']
package=next(p for p in library.sessions[lid]['data']['package'] if p['name']=='MCP_SECOND')
changes={'referenceTemplate':'Z?','footprint':'FAULT_FP','pcbLibrary':'FAULT_LIB'};users=[{'name':'MCP_FAULT','operation':'set','value':'recover 中文\nno replay'}]
(root/'expected.json').write_text(json.dumps({'packageName':'MCP_SECOND','changes':changes,'userProperties':users},ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
creator=LibraryPackageEdits(cfg,library);execute=creator.execute;calls=0;report={'passed':False,'checks':{}}
def plan(service):return service.plan(lid,package['objectId'],changes,users)
async def main():
 global calls
 try:
  lost=plan(creator);report['lostPlan']=lost;key={k:lost[k] for k in ('planId','planDigest')}
  def lose(d,p,cancel,started):
   global calls
   calls+=1;process=execute(d,p,cancel,started);assert process['returnCode']==0 and process['remainingOwnedProcesses']==0
   (d/'native-result.json').unlink();return process
  creator.execute=lose
  try:creator.apply(key['planId'],key['planDigest'],'lost');raise AssertionError('Missing receipt accepted')
  except CadenceError as e:report['lostError']=e.code
  directory,_,row=creator._load(key['planId']);assert row['state']=='failed';saved=sha256(directory/'library.olb');report['lostProcess']=row['process']
  env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
  params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(cfg.workspace_root),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   async def call(name,args):
    r=await fresh.call_tool(name,args);assert not r.is_error,(name,r.content);return r.structured_content['data']
   result=await call('capture_recover_library_package_edit',key);report['recovered']=result
   assert result['state']=='verified_recovered' and not result['nativeCompletionVerified'] and not result['mutationReplayed']
   assert result['packagePropertiesVerified'] and result['modeledLibraryPreservationVerified']
   opened=await call('capture_open_edited_library',{**key,'kind':'package'})
   target=next(p for p in (await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'package','limit':1000}))['items'] if p['name']=='MCP_SECOND')
   props=(await call('capture_query_library_package_properties',{'libraryId':opened['libraryId'],'packageId':target['objectId']}))['properties']
   assert props['footprint']=='FAULT_FP' and props['referenceTemplate']=='Z?' and props['userProperties'][0]['value']==users[0]['value']
   assert not (await call('capture_apply_library_package_edit',{**key,'idempotencyKey':'lost'}))['mutationReplayed']
  assert calls==1 and sha256(directory/'library.olb')==saved;report['checks']['fresh_mcp_receipt_recovery_no_replay']=True
  creator.execute=execute;cancel=plan(creator);report['cancelPlan']=cancel
  def stop(d,p,event,started):
   def ready(pid):started(pid);assert creator.cancel(cancel['planId'],cancel['planDigest'])['cancelRequested']
   return execute(d,p,event,ready)
  creator.execute=stop
  try:creator.apply(cancel['planId'],cancel['planDigest'],'cancel');raise AssertionError('Cancelled package edit accepted')
  except CadenceError as e:assert e.code=='operation_cancelled',e.code
  process=creator._load(cancel['planId'])[2]['process'];assert process['remainingOwnedProcesses']==0;report['cancelProcess']=process;report['checks']['native_start_cancel']=True
  timeout=LibraryPackageEdits(cfg,library);timed=plan(timeout);report['timeoutPlan']=timed;timeout.config=Config(cfg.install_root,cfg.workspace_root,(source.parent,),1)
  delayed=root/'delay.tcl';delayed.write_text('after 2000\nsource {'+(ADAPTERS/'edit_library_package.tcl').as_posix()+'}\n',encoding='utf-8');command=timeout.native_command
  timeout.native_command=lambda d,p:[command(d,p)[0],str(delayed),*command(d,p)[2:]]
  try:timeout.apply(timed['planId'],timed['planDigest'],'timeout');raise AssertionError('Timeout accepted')
  except CadenceError as e:assert e.code=='timeout',e.code
  process=timeout._load(timed['planId'])[2]['process'];assert process['state']=='timeout' and process['remainingOwnedProcesses']==0;report['timeoutProcess']=process;report['checks']['delayed_worker_timeout']=True
  for kind in ('unrelated_package','unrelated_vector'):
   writer=LibraryPackageEdits(cfg,library);poisoned=plan(writer);report[kind+'Plan']=poisoned;native=writer.execute
   def poison(d,p,cancel,started):
    process=native(d,p,cancel,started);assert process['returnCode']==0
    frozen=json.loads(Path(p['beforeEvidence']).read_text(encoding='utf-8'))
    if kind=='unrelated_package':
     other=next(r for r in frozen['packageProperties'] if r['packageName']!='MCP_SECOND')
     spec={'packageId':'test-other','packageName':other['packageName'],'beforeProperties':other,'changes':{'footprint':'UNRELATED_POISON'},'userChanges':[]}
     adapter=ADAPTERS/'edit_library_package.tcl'
    else:
     rows=[r for r in frozen['library']['metadata']['symbols'] if r['scope'][-1].endswith('.Convert')];scope=rows[0]['scope']
     spec={'scope':scope,'index':0,'old':rows[0]['orderedVectors'][0],'operation':'update',
       'replacement':{'kind':'line','start':[-100,-100],'end':[100,100],'style':4,'width':2},'vectorId':'test-other-vector','affectedScopes':[r['scope'] for r in rows]}
     adapter=ADAPTERS/'edit_library_vector.tcl'
    write_json(d/'poison-request.json',spec)
    extra=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(adapter),str(cfg.install_root),str(d/'library.olb'),str(d/'poison-request.json'),str(d/'poison-receipt.json')],d,process_env(cfg),60)
    assert extra['returnCode']==0 and extra['remainingOwnedProcesses']==0;report[kind+'Process']=extra;return process
   writer.execute=poison
   try:writer.apply(poisoned['planId'],poisoned['planDigest'],kind);raise AssertionError('Unrelated mutation accepted')
   except CadenceError as e:assert e.code=='library_package_mismatch',e.code
   try:writer.open_output(poisoned['planId'],poisoned['planDigest']);raise AssertionError('Poisoned package opened')
   except CadenceError as e:assert e.code=='output_unverified',e.code
   try:writer.apply(poisoned['planId'],poisoned['planDigest'],kind);raise AssertionError('Failed mutation replayed')
   except CadenceError as e:assert e.code=='write_not_replayed',e.code
   report['checks'][kind+'_saved_but_refused']=True
  terminal=LibraryPackageEdits(cfg,library);t=plan(terminal);report['tamperPlan']=t;terminal.apply(t['planId'],t['planDigest'],'tamper')
  d,_,_=terminal._load(t['planId']);target=d/'library.olb';(root/'retained-before-tamper.olb').write_bytes(target.read_bytes());target.write_bytes(target.read_bytes()+b'PRIVATE TEST TAMPER')
  for action in (lambda:terminal.open_output(t['planId'],t['planDigest']),lambda:terminal.recover(t['planId'],t['planDigest']),lambda:terminal.apply(t['planId'],t['planDigest'],'tamper')):
   try:action();raise AssertionError('Tampered output accepted')
   except CadenceError as e:assert e.code=='target_changed',e.code
  report['checks']['terminal_hash_tamper_refused']=True
  report['sourceAndOracleUnchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
  report['passed']=report['sourceAndOracleUnchanged'] and all(report['checks'].values())
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
