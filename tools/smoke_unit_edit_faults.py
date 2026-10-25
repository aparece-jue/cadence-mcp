"""Native receipt loss/recovery, start-window cancellation and actual timeout."""
import argparse,json,asyncio,os,sys
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.capture_references import read_units
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_part_edit import CapturePartEdits

class LoseReceipt(CapturePartEdits):
    def verify(self,directory,p,native_completed):
        if native_completed:
            (directory/'native-result.json').unlink()
            raise CadenceError('receipt_lost_fixture','Owned test removes receipt after native completion.','verify')
        return super().verify(directory,p,native_completed)

class CancelAtStart(CapturePartEdits):
    def execute(self,directory,p,cancel,on_started):
        def started(pid):on_started(pid);cancel.set()
        return super().execute(directory,p,cancel,started)

class DelayedPartEdit(CapturePartEdits):
    def native_command(self,directory,p):
        command=list(super().native_command(directory,p));production=command[1];wrapper=directory/'delayed-unit.tcl'
        wrapper.write_text('set production [lindex $argv end]\nset argv [lrange $argv 0 end-1]\nset argc [llength $argv]\nafter 2000\nsource $production\n',encoding='utf-8');command[1]=wrapper;command.append(production);return command

p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source','spec'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);a.spec=a.spec.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
report={'passed':False,'sourceHashBefore':sha256(a.source),'cases':[]}
for mode,cls in [('receipt_loss',LoseReceipt),('cancel_at_start',CancelAtStart),('native_timeout',DelayedPartEdit)]:
    row={'mode':mode,'passed':False};report['cases'].append(row)
    try:
        # Plan reads need their normal timeout; only actual execution uses 1 second.
        normal=Config(a.install_root,root/mode,(a.source.parent,),60);cap=CaptureService(normal);ws=cap.create_workspace(str(a.source));sid=cap.open(ws['workspaceId'])['sessionId']
        identities=read_units(cap,sid);unit=next(u for u in identities.values() if u['referenceDesignator']=='U501A');part=next(p for p in cap.sessions[sid]['data']['part'] if p['objectId']==unit['partId'])
        config=Config(a.install_root,root/mode,(a.source.parent,),1 if mode=='native_timeout' else 60)
        writer=cls(config,cap)
        spec=json.loads(a.spec.read_text(encoding='utf-8'));dev=next(d for d in spec['devices'] if d['designator']=='A');symbol=next(s for s in spec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith('.Normal'));mapping={p['position']:p['number'] for p in dev['mapping']};pins=[{'number':mapping[p['position']],'name':p['name'],'hotSpot':[1000+p['hotSpot'][0],900+p['hotSpot'][1]]} for p in symbol['pins']]
        expected=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in cap.sessions[sid]['data']['pin'] if p['pageId']==part['pageId']]
        plan=writer.plan(sid,part['objectId'],'set_pose',[],[1000,900],0,0,pins,unit_expectations=expected);row['plan']=plan
        try:writer.apply(plan['planId'],plan['planDigest'],mode)
        except CadenceError as error:
            wanted={'receipt_loss':'receipt_lost_fixture','cancel_at_start':'operation_cancelled','native_timeout':'timeout'}[mode]
            assert error.code==wanted,(error.code,wanted);row['errorCode']=error.code
        else:raise AssertionError('Expected native fault not observed')
        directory=writer.root/('plan-'+plan['planId']);ledger=json.loads((directory/'plan.json').read_text(encoding='utf-8'));row['process']=ledger['process']
        assert ledger['process']['remainingOwnedProcesses']==0
        if mode=='receipt_loss':
            before=sha256(directory/'design.dsn')
            async def recover():
                env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(normal.install_root),'--workspace-root',str(normal.workspace_root),'--read-root',str(a.source.parent)],env=env)
                async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
                    key={k:plan[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_recover_part_edit',key);assert not v.is_error,v.content;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'part_edit'})).is_error;return v.structured_content['data']
            recovered=asyncio.run(recover());assert recovered['state']=='verified_recovered' and recovered['nativeCompletionVerified'] is False and not recovered['mutationReplayed'] and recovered['unitAware'];assert recovered['artifact']['sha256']==before==sha256(directory/'design.dsn');row['recovered']=recovered
        else:
            try:writer.apply(plan['planId'],plan['planDigest'],mode)
            except CadenceError as e:assert e.code=='write_not_replayed'
            else:raise AssertionError('Faulted mutation replayed')
        row['passed']=True
    except BaseException as error:row.update(errorType=type(error).__name__,error=str(error))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceHashAfter']=sha256(a.source);report['passed']=all(c['passed'] for c in report['cases']) and report['sourceHashBefore']==report['sourceHashAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)

