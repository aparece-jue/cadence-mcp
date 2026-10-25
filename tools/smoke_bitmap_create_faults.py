import argparse,asyncio,json,os,sys,shutil
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates

p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','specs-path'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--spec-case',choices=('mixed','legacy'),default='mixed')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);readroot=root/'inputs';readroot.mkdir();repo=Path(__file__).resolve().parents[1]
config=Config(a.install_root.resolve(strict=True),root/'work',(readroot,),60);creator=LibraryCreates(config,LibraryService(config));spec=next(v['spec'] for v in json.loads(a.specs_path.read_text(encoding='utf-8')) if v['name']=='rgb24');
for symbol in spec['symbols']:
 for vector in symbol.get('vectors',[]):
  if vector['kind']=='bitmap':
   source=Path(vector['sourceBmp']);target=readroot/source.name
   if not target.exists():shutil.copyfile(source,target)
   assert sha256(target)==vector['expectedBmpSha256'];vector['sourceBmp']=str(target)
(root/'expected.json').write_text(json.dumps(spec,indent=2));native=creator.execute
report={'passed':False,'checks':{}};calls=0
async def main():
    global calls
    try:
        bad=creator.plan(spec);bad_directory,_,bad_row=creator._load(bad['planId'])
        vector=next(v for s in bad_row['plan']['payload']['spec']['symbols'] for v in s.get('vectors',[]) if v['kind']=='bitmap')
        frozen=Path(vector['sourceBmp']);blob=bytearray(frozen.read_bytes());blob[-1]^=255;frozen.write_bytes(blob)
        try:creator.apply(bad['planId'],bad['planDigest'],'bad-asset');raise AssertionError('Modified asset accepted')
        except CadenceError as error:assert error.code=='bitmap_asset_mismatch',error.code
        assert creator._load(bad['planId'])[2]['state']=='planned' and not (bad_directory/'library.olb').exists()
        report['checks']['asset_tamper_refused_before_native_start']=True
        plan=creator.plan(spec);key={k:plan[k] for k in ('planId','planDigest')};report['lostPlan']=plan
        def lose_receipt(directory,p,cancel,started):
            global calls
            calls+=1;process=native(directory,p,cancel,started);assert process['state']=='exited' and process['returnCode']==0
            (directory/'native-result.json').unlink();return process
        creator.execute=lose_receipt
        try:creator.apply(key['planId'],key['planDigest'],'lost-receipt');raise AssertionError('Missing receipt accepted')
        except CadenceError as error:report['lostError']=error.code
        directory,_,row=creator._load(key['planId']);assert row['state']=='failed';report['lostProcess']=row['process'];before=sha256(directory/'library.olb')
        env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(config.install_root),'--workspace-root',str(config.workspace_root),'--read-root',str(readroot),'--timeout-seconds','60'],env=env)
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            async def call(name,args):
                r=await fresh.call_tool(name,args);assert not r.is_error,r.content
                return r.structured_content['data']
            result=await call('capture_recover_library_create',key);assert result['state']=='verified_recovered' and result['nativeCompletionVerified'] is False and result['mutationReplayed'] is False
            opened=await call('capture_open_created_library',key);pins=await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'pin'});assert pins['total']==12
            part=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'part'}))['items'][0]
            vectors=await call('capture_query_library_vectors',{'libraryId':opened['libraryId'],'partId':part['objectId']});assert vectors['total']==14
            assert (await call('capture_apply_library_create',{**key,'idempotencyKey':'lost-receipt'}))['mutationReplayed'] is False
            report['recovered']=result
        assert calls==1 and before==sha256(directory/'library.olb');report['checks']['receipt_loss_fresh_mcp_recovery_no_replay']=True
        creator.execute=native;cancel=creator.plan(spec);cancel_key={k:cancel[k] for k in ('planId','planDigest')};report['cancelPlan']=cancel
        def stop_at_start(directory,p,event,started):
            def ready(pid):started(pid);assert creator.cancel(cancel_key['planId'],cancel_key['planDigest'])['cancelRequested']
            return native(directory,p,event,ready)
        creator.execute=stop_at_start
        try:creator.apply(cancel_key['planId'],cancel_key['planDigest'],'cancel-native');raise AssertionError('Native start cancel accepted as success')
        except CadenceError as error:assert error.code=='operation_cancelled',error.code
        process=creator._load(cancel_key['planId'])[2]['process'];assert process['remainingOwnedProcesses']==0;report['cancelProcess']=process;report['checks']['native_start_window_cancel']=True
        short=Config(config.install_root,config.workspace_root,(readroot,),1);timeout=LibraryCreates(short,LibraryService(short));planned=timeout.plan(spec);report['timeoutPlan']=planned
        adapter=repo/'src/cadence_mcp/adapters/create_library.tcl';delay=root/'delayed-create.tcl'
        delay.write_text('after 2000\nsource {'+adapter.as_posix()+'}\n',encoding='utf-8')
        command=timeout.native_command
        timeout.native_command=lambda d,p:[command(d,p)[0],str(delay),*command(d,p)[2:]]
        try:timeout.apply(planned['planId'],planned['planDigest'],'native-timeout');raise AssertionError('Expected real one-second timeout')
        except CadenceError as error:assert error.code=='timeout',error.code
        process=timeout._load(planned['planId'])[2]['process'];assert process['state']=='timeout' and process['remainingOwnedProcesses']==0;report['timeoutProcess']=process;report['checks']['real_one_second_timeout']=True
        # Add one undeclared native graphic after a successful save; complete verification must refuse it.
        from cadence_mcp.environment import ADAPTERS,process_env
        from cadence_mcp.process_tree import run_owned_process
        poisoned=LibraryCreates(config,LibraryService(config));p=poisoned.plan(spec);report['graphicPoisonPlan']=p
        execute=poisoned.execute
        def append_undeclared(directory,p,cancel,started):
            process=execute(directory,p,cancel,started);assert process['returnCode']==0
            symbol=spec['symbols'][0];request={'packageName':spec['packageName'],'designator':spec['devices'][0]['designator'],
                'additions':[{'partName':symbol['partName'],'vectors':[{'kind':'ellipse','bounds':[0,0,5,5],'style':0,'width':0,'fill':1,'hatch':0}]}]}
            (directory/'poison-request.json').write_text(json.dumps(request),encoding='utf-8')
            row=run_owned_process([str(config.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_append_vectors.tcl'),str(config.install_root),str(directory/'library.olb'),str(directory/'poison-request.json'),str(directory/'poison-receipt.json')],directory,process_env(config),60)
            assert row['returnCode']==0 and row['remainingOwnedProcesses']==0;report['poisonProcess']=row
            return process
        poisoned.execute=append_undeclared
        try:poisoned.apply(p['planId'],p['planDigest'],'poison');raise AssertionError('Undeclared native graphic accepted')
        except CadenceError as error:assert error.code=='library_creation_mismatch',error.code
        try:poisoned.open_output(p['planId'],p['planDigest']);raise AssertionError('Poisoned library opened')
        except CadenceError as error:assert error.code=='output_unverified',error.code
        report['checks']['undeclared_graphic_saved_but_refused']=True
        report['passed']=True
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    finally:(root/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}))
asyncio.run(main())
