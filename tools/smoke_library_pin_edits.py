"""Independent native edited-OLB semantic graph acceptance on owned copies."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_edit import LibraryPinEdits
from cadence_mcp.library_semantics import library_graph
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','created-library-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);created=a.created_library_root.resolve()
prior=json.loads((created/'report.json').read_text(encoding='utf-8'))
paths={c['name']:created/'work/isolated-jobs/capture_library_create'/('plan-'+c['plan']['planId'])/'library.olb' for c in prior['cases'] if c['name']!='unicode_literal'}
paths['official']=a.install_root/'tools/capture/library/pspice/analog.olb'
cases=[{'name':'vendor_combined','source':'official','package':'R','position':0,'changes':{'name':'MCP_PIN_A','number':'101','pin_type':0}},
       {'name':'resistor_unicode','source':'resistor','package':'MCP_RES','position':0,'changes':{'name':'A $[x];中文'}},
       {'name':'homogeneous_name','source':'homogeneous_shared','package':'MCP_DUAL','designator':'A','position':0,'changes':{'name':'INPUT_NEW'}},
       {'name':'homogeneous_number','source':'homogeneous_shared','package':'MCP_DUAL','designator':'A','position':0,'changes':{'number':'11'}},
       {'name':'heterogeneous_name','source':'heterogeneous_power','package':'MCP_HETERO','designator':'A','position':0,'changes':{'name':'A_ONLY'}}]
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
config=Config(a.install_root,root/'work',tuple({p.parent for p in paths.values()}),60);report={'passed':False,'cases':[]}
for fixture in cases:
    row={'name':fixture['name'],'passed':False};report['cases'].append(row);source=paths[fixture['source']];row['sourceHashBefore']=sha256(source)
    try:
        library=LibraryService(config);writer=LibraryPinEdits(config,library);opened=library.open(str(source));sid=opened['libraryId'];data=library.sessions[sid]['data']
        packages={p['objectId']:p['name'] for p in data['package']};devices={p['objectId']:p['designator'] for p in data['device']}
        selected=[p for p in data['pin'] if packages[p['packageId']]==fixture['package'] and p['position']==fixture['position'] and ('designator' not in fixture or devices[p['deviceId']]==fixture['designator'])]
        assert selected;target=selected[0]
        plan=writer.plan(sid,target['objectId'],**fixture['changes']);row['plan']=plan
        result=writer.apply(plan['planId'],plan['planDigest'],fixture['name']);row['result']=result
        fresh=LibraryPinEdits(config,LibraryService(config));again=fresh.apply(plan['planId'],plan['planDigest'],fixture['name']);assert again['artifact']['sha256']==result['artifact']['sha256']
        opened=fresh.open_output(plan['planId'],plan['planDigest']);after=fresh.library.sessions[opened['libraryId']]['data'];row['opened']=opened
        changed=[]
        for k in fixture['changes']:
            field={'pin_type':'pinType'}.get(k,k)
            wanted=fixture['changes'][k]
            assert sum(p[field]==wanted for p in after['pin'])>=len(plan['preview']['affected']) if k=='name' else any(p[field]==wanted for p in after['pin'])
        if fixture['name']=='homogeneous_name':assert len(plan['preview']['affected'])==2
        if fixture['name']=='heterogeneous_name':assert len(plan['preview']['affected'])==1
        row['sourceHashAfter']=sha256(source);assert row['sourceHashAfter']==row['sourceHashBefore'];row['passed']=True
    except BaseException as error:row.update(errorType=type(error).__name__,error=str(error),errorCode=getattr(error,'code',None))
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('name','passed','errorCode','error')},ensure_ascii=False),flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
