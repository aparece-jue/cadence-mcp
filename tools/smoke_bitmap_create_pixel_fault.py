"""Valid pixel-only private OLB mutation must fail declared new-library verification."""
import argparse,copy,hashlib,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates
from cadence_mcp.library_vector_query import query_library_vectors
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','specs-path'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
spec=copy.deepcopy(next(v['spec'] for v in json.loads(a.specs_path.read_text(encoding='utf-8')) if v['name']=='rgb24'))
vector=next(v for s in spec['symbols'] for v in s['vectors'] if v['kind']=='bitmap')
source=Path(vector['sourceBmp']);before=sha256(source);dib=source.read_bytes()[14:];poison=dib[:-1]+bytes([dib[-1]^255])
assert len(poison)==len(dib) and poison!=dib
cfg=Config(a.install_root,root/'work',(source.parent,),60);report={'passed':False,'checks':{}}
try:
    writer=LibraryCreates(cfg,LibraryService(cfg));plan=writer.plan(spec);key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
    native=writer.execute
    def change_pixels(directory,payload,cancel,started):
        process=native(directory,payload,cancel,started)
        assert process['returnCode']==0 and process['remainingOwnedProcesses']==0
        path=(directory/'library.olb').resolve(strict=True);assert path.is_relative_to(cfg.workspace_root)
        blob=path.read_bytes();count=blob.count(dib);assert 1<=count<=4,count
        changed=blob.replace(dib,poison);assert len(changed)==len(blob)
        path.write_bytes(changed);report['replacedDibOccurrences']=count;report['process']=process
        return process
    writer.execute=change_pixels
    try:writer.apply(key['planId'],key['planDigest'],'pixel-fault');raise AssertionError('Changed pixels accepted')
    except CadenceError as error:assert error.code=='library_creation_mismatch',error.code
    directory,_,ledger=writer._load(key['planId']);assert ledger['state']=='failed';saved=sha256(directory/'library.olb')
    reader=LibraryService(Config(cfg.install_root,cfg.workspace_root,(directory,),60))
    lid=reader.open(str(directory/'library.olb'))['libraryId'];observed=[]
    for part in reader.sessions[lid]['data']['part']:
        items=query_library_vectors(reader,lid,part['objectId'],None,1000)['items']
        bitmap=next(v['descriptor'] for v in items if v['kind']=='bitmap')
        wanted=next(v for s in spec['symbols'] if s['partName']==part['name'] for v in s['vectors'] if v['kind']=='bitmap')
        assert bitmap==['bitmap',wanted['bounds'],wanted['location'],[2,2],56,hashlib.sha256(poison).hexdigest()]
        observed.append(bitmap)
    assert len(observed)==4;report['observed']=observed
    report['checks']['native_reopen_proves_only_declared_pixel_digest_mismatch']=True
    try:writer.open_output(key['planId'],key['planDigest']);raise AssertionError('Unverified artifact opened')
    except CadenceError as error:assert error.code=='output_unverified',error.code
    try:writer.apply(key['planId'],key['planDigest'],'pixel-fault');raise AssertionError('Write replayed')
    except CadenceError as error:assert error.code=='write_not_replayed',error.code
    fresh=LibraryCreates(cfg,LibraryService(cfg))
    try:fresh.recover(key['planId'],key['planDigest']);raise AssertionError('Wrong pixels recovered')
    except CadenceError as error:assert error.code=='library_creation_mismatch',error.code
    report['checks']['fresh_recovery_open_and_replay_refused']=True
    report['checks']['source_and_unverified_output_unchanged_during_reads']=sha256(source)==before and sha256(directory/'library.olb')==saved
    report['passed']=all(report['checks'].values())
except BaseException as error:
    import traceback
    report.update(error=str(error),traceback=traceback.format_exc())
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));raise SystemExit(0 if report['passed'] else 1)
