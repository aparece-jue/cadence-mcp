"""Owned OLB pixel-only fault must fail the production preservation verifier."""
import argparse,hashlib,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_vector_query import query_library_vectors
from cadence_mcp.library_vector_edit import LibraryVectorEdits

p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-a','source-b'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
source=(a.source_a/'library.olb').resolve(strict=True);before=sha256(source)
original=(a.source_a/'pattern.bmp').read_bytes()[14:];poison=(a.source_b/'pattern.bmp').read_bytes()[14:]
assert len(original)==len(poison)==56 and original!=poison
cfg=Config(a.install_root,root/'work',(root,source.parent),60)
report={'passed':False,'checks':{}}
try:
    library=LibraryService(cfg);lid=library.open(str(source))['libraryId']
    part=next(v for v in library.sessions[lid]['data']['part'] if v['name']=='GATE.Normal')
    vectors=query_library_vectors(library,lid,part['objectId'],None,1000)['items']
    assert vectors[-1]['descriptor'][-1]==hashlib.sha256(original).hexdigest()
    writer=LibraryVectorEdits(cfg,library)
    plan=writer.plan(lid,part['objectId'],vectors[0]['objectId'],'update',{'kind':'line','start':[-15,3],'end':[15,3],'style':1,'width':2})
    report['plan']=plan;key={k:plan[k] for k in ('planId','planDigest')};native=writer.execute
    def change_only_pixels(directory,payload,cancel,started):
        process=native(directory,payload,cancel,started)
        assert process['returnCode']==0 and process['remainingOwnedProcesses']==0
        path=(directory/'library.olb').resolve(strict=True)
        assert path.is_relative_to(cfg.workspace_root)
        blob=path.read_bytes();assert blob.count(original)==1 and blob.count(poison)==0
        changed=blob.replace(original,poison)
        assert len(changed)==len(blob)
        path.write_bytes(changed)
        report['poisonProcess']=process
        return process
    writer.execute=change_only_pixels
    try:
        writer.apply(key['planId'],key['planDigest'],'pixel-fault')
        raise AssertionError('Changed image accepted')
    except CadenceError as error:
        assert error.code=='library_vector_mismatch',error.code
        report['expectedError']=error.code
    directory,_,ledger=writer._load(key['planId'])
    assert ledger['state']=='failed'
    # A new Dbo process must actually read the replacement pixels, not merely fail to open.
    saved=library.open(str(directory/'library.olb'))['libraryId']
    part=next(v for v in library.sessions[saved]['data']['part'] if v['name']=='GATE.Normal')
    actual=query_library_vectors(library,saved,part['objectId'],None,1000)['items']
    assert len(actual)==14
    assert actual[-1]['descriptor'][:-1]==vectors[-1]['descriptor'][:-1]
    assert actual[-1]['descriptor'][-1]==hashlib.sha256(poison).hexdigest()
    assert actual[0]['descriptor']==['line',[-15,3],[15,3],1,2]
    report['checks']['valid_same_geometry_pixel_only_mismatch_refused']=True
    try:
        writer.open_output(key['planId'],key['planDigest'])
        raise AssertionError('Unverified output opened')
    except CadenceError as error:assert error.code=='output_unverified',error.code
    try:
        writer.apply(key['planId'],key['planDigest'],'pixel-fault')
        raise AssertionError('Write replayed')
    except CadenceError as error:assert error.code=='write_not_replayed',error.code
    report['checks']['unverified_open_and_replay_refused']=True
    report['checks']['source_unchanged']=sha256(source)==before
    report['passed']=all(report['checks'].values())
except BaseException as error:
    import traceback
    report.update(error=str(error),traceback=traceback.format_exc())
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'error':report.get('error')}));raise SystemExit(0 if report['passed'] else 1)
