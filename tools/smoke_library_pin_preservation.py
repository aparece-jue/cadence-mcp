"""Prewritten wrong-preservation oracle and changed-source rejection on owned copies."""
import argparse,copy,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_edit import LibraryPinEdits
from cadence_mcp.isolated_jobs import digest

class WrongPreservation(LibraryPinEdits):
    def create_plan(self,payload):
        graph=self._pin_graph(Path(payload['sourceLibrary']),Path(payload['sourceLibrary']).parent)
        graph['metadata']['symbols'][0]['pinStarts'][0]['start'][0]+=7
        # Keep actual pin-edit expectations; deliberately require an undeclared extra start change.
        before=self.library.sessions[next(iter(self.library.sessions))]['data']
        from cadence_mcp.library_edit import expected_library
        from cadence_mcp.library_semantics import library_graph
        graph['definitions']=library_graph(expected_library(before,payload['pinId'],hot_spot=[-55,0],visible=False)[1])
        payload=copy.deepcopy(payload);payload['expectedGraphDigest']=digest(graph)
        return super().create_plan(payload)

p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
report={'passed':False,'sourceHashBefore':sha256(a.source),'cases':[]}
for mode,cls,code in [('wrong_preservation',WrongPreservation,'library_preservation_failed'),('changed_source',LibraryPinEdits,'target_changed')]:
    row={'mode':mode,'passed':False};report['cases'].append(row)
    try:
        config=Config(a.install_root,root/mode,(a.source.parent,),60);library=LibraryService(config)
        opened=library.open(str(a.source));lid=opened['libraryId'];target=library.sessions[lid]['data']['pin'][0]
        writer=cls(config,library);plan=writer.plan(lid,target['objectId'],hot_spot=[-55,0],visible=False);row['plan']=plan
        if mode=='changed_source':
            source=library.sessions[lid]['directory']/'library.olb';source.write_bytes(source.read_bytes()+b'owned snapshot tamper')
        try:writer.apply(plan['planId'],plan['planDigest'],mode)
        except CadenceError as e:assert e.code==code,e.code;row['errorCode']=e.code
        else:raise AssertionError('Expected refusal absent')
        directory=writer.root/('plan-'+plan['planId']);ledger=json.loads((directory/'plan.json').read_text(encoding='utf-8'))
        if mode=='changed_source':assert ledger['state']=='planned' and not (directory/'library.olb').exists()
        else:
            assert ledger['process']['remainingOwnedProcesses']==0
            try:writer.open_output(plan['planId'],plan['planDigest'])
            except CadenceError as e:assert e.code=='output_unverified'
            else:raise AssertionError('Opened unverified output')
            try:writer.apply(plan['planId'],plan['planDigest'],mode)
            except CadenceError as e:assert e.code=='write_not_replayed'
            else:raise AssertionError('Replayed mutation')
        row['passed']=True
    except BaseException as error:row.update(errorType=type(error).__name__,error=str(error))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(row),flush=True)
report['sourceHashAfter']=sha256(a.source);report['passed']=all(row['passed'] for row in report['cases']) and report['sourceHashAfter']==report['sourceHashBefore']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
