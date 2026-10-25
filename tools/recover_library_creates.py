from pathlib import Path
import json
from cadence_mcp.core import Config,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates,actual_graph,expected_graph
repo=Path(r'D:\workspace\git\cadence-mcp');old=repo/'.local/library-creates-20261023';root=repo/'.local/library-creates-recover-20261023';root.mkdir(exist_ok=False)
config=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),old/'work',(old,),60);library=LibraryService(config);creator=LibraryCreates(config,library)
original=json.loads((old/'report.json').read_text());report={'passed':False,'originalReportSha256':sha256(old/'report.json'),'mutationReplayed':False,'cases':[]}
for case in original['cases']:
    plan=case['plan'];row={'name':case['name'],'passed':False,'planId':plan['planId']};report['cases'].append(row)
    directory,_,record=creator._load(plan['planId']);target=directory/'library.olb';before=sha256(target)
    try:
        result=creator.recover(plan['planId'],plan['planDigest']);opened=creator.open_output(plan['planId'],plan['planDigest']);pins=library.query(opened['libraryId'],'pin',None,None,1000)['items']
        assert before==sha256(target) and result['mutationReplayed'] is False
        assert result['uniquePhysicalPadCount']==len({p['number'] for p in pins})
        row.update(passed=True,result=result,opened=opened,physicalPadCount=result['uniquePhysicalPadCount'],logicalPinRows=len(pins),artifactSha256Unchanged=True)
    except BaseException as error:
        row.update(error=str(error),errorCode=getattr(error,'code',type(error).__name__))
        for path in directory.glob('library-verify-*.json'):
            raw=json.loads(path.read_text())
            try:(directory/'verification-diff.json').write_text(json.dumps({'expected':expected_graph(record['plan']['payload']['spec']),'actual':actual_graph(raw)},indent=2))
            except Exception as decode:row['decodeDiagnostic']=str(decode)
report['passed']=all(c['passed'] for c in report['cases'])
(root/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'passed':report['passed'],'cases':[{k:c.get(k) for k in ('name','passed','errorCode','physicalPadCount','logicalPinRows')} for c in report['cases']],'report':str(root/'report.json')}))
