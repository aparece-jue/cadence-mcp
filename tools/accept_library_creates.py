import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates,expected_graph,actual_graph
from library_create_fixtures import specs
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);config=Config(a.install_root.resolve(strict=True),root/'work',(root,),60);library=LibraryService(config);creator=LibraryCreates(config,library)
cases=specs();(root/'expected.json').write_text(json.dumps(cases,indent=2));report={'passed':False,'cases':[]}
for name,spec in cases.items():
    case={'name':name,'passed':False,'phase':'plan'};report['cases'].append(case)
    try:
        plan=creator.plan(spec);case['plan']=plan;case['phase']='native_create'
        result=creator.apply(plan['planId'],plan['planDigest'],name);opened=creator.open_output(plan['planId'],plan['planDigest'])
        pins=library.query(opened['libraryId'],'pin',spec['packageName'],None,1000)['items'];physical=len({p['number'] for p in pins})
        assert physical==len({p['number'] for d in spec['devices'] for p in d['mapping']})
        case.update(passed=True,phase='independent_reopen',result=result,opened=opened,physicalPadCount=physical,logicalPinRows=len(pins))
    except BaseException as error:
        case.update(error=str(error),errorCode=getattr(error,'code',type(error).__name__))
        if 'plan' in case:
            directory,_,row=creator._load(case['plan']['planId']);case['jobState']=row['state'];case['process']=row.get('process')
            if (directory/'native-result.json').exists():case['native']=json.loads((directory/'native-result.json').read_text())
            for path in directory.glob('library-verify-*.json'):
                raw=json.loads(path.read_text());(directory/'verification-raw-copy.json').write_text(json.dumps(raw,indent=2))
                try:(directory/'verification-diff.json').write_text(json.dumps({'expected':expected_graph(spec),'actual':actual_graph(raw)},indent=2))
                except Exception as diagnostic:case['decodeDiagnostic']=str(diagnostic)
report['passed']=all(c['passed'] for c in report['cases'])
(root/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'passed':report['passed'],'cases':[{k:c.get(k) for k in ('name','passed','phase','errorCode')} for c in report['cases']],'report':str(root/'report.json')}))
