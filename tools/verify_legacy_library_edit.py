"""Read-only original frozen expectation audit; never migrate or replay its ledger."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.library import LibraryService,validate_library
from cadence_mcp.library_edit import expected_library
from cadence_mcp.library_semantics import library_graph
from cadence_mcp.isolated_jobs import digest
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','legacy-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
plans=list((a.legacy_root/'isolated-jobs/library_pin').glob('plan-*/plan.json'));assert len(plans)==1
path=plans[0];ledger=json.loads(path.read_text(encoding='utf-8'));payload=ledger['plan']['payload'];target=path.parent/'library.olb';source=Path(payload['sourceLibrary'])
report={'passed':False,'ledgerHashBefore':sha256(path),'sourceHashBefore':sha256(source),'targetHashBefore':sha256(target),'mutationReplayed':False}
try:
    assert digest(ledger['plan'])==ledger['digest']
    assert report['sourceHashBefore']==payload['sourceFingerprint']
    original=json.loads((source.parent/'inspection.json').read_text(encoding='utf-8'));validate_library(original)
    assert digest(original)==payload['beforeLibraryDigest']
    _,expected,_=expected_library(original,payload['pinId'],payload['name'],payload['number'],payload['pinType'])
    assert digest(expected)==payload['expectedLibraryDigest'],'Must preserve the exact original expectation'
    library=LibraryService(Config(a.install_root,root/'work',(source.parent,target.parent),60));opened=library.open(str(target));actual=library.sessions[opened['libraryId']]['data']
    report.update(expectedSemanticDigest=digest(library_graph(expected)),observedSemanticDigest=digest(library_graph(actual)),rawOrdinalDigestEqual=digest(actual)==payload['expectedLibraryDigest'])
    assert report['expectedSemanticDigest']==report['observedSemanticDigest']
    report.update(passed=True,originalFrozenExpectationVerified=True,legacyLedgerState=ledger['state'],nativeCompletionReaccepted=False)
except BaseException as e:report.update(errorType=type(e).__name__,error=str(e),errorCode=getattr(e,'code',None))
report.update(ledgerHashAfter=sha256(path),sourceHashAfter=sha256(source),targetHashAfter=sha256(target))
if any(report[k+'Before']!=report[k+'After'] for k in ('ledgerHash','sourceHash','targetHash')):report['passed']=False
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
raise SystemExit(0 if report['passed'] else 1)
