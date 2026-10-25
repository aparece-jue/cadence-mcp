"""MCP bitmap deletion and non-target pixel preservation during ordinary vector edits."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','library-root','accepted-query-report'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=(a.library_root/'library.olb').resolve(strict=True);before=sha256(source)
previous=json.loads(a.accepted_query_report.read_text(encoding='utf-8'));assert previous['passed']
baseline=next(c['vectors'] for c in previous['cases'] if c['label']=='A')
baseline=[v['descriptor'] for v in baseline];assert baseline[-1][0]=='bitmap'
cases=[]
for operation,index,replacement in [('update',0,{'kind':'line','start':[-15,3],'end':[15,3],'style':1,'width':2}),('delete',13,None)]:
    expected=copy.deepcopy(baseline)
    if operation=='update':expected[index]=['line',[-15,3],[15,3],1,2]
    else:expected.pop(index)
    cases.append({'name':'line-update-retain-bitmap' if operation=='update' else 'bitmap-delete','operation':operation,'index':index,'replacement':replacement,'expected':expected})
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=os.environ.copy())

async def main():
    report={'passed':False,'scope':'bitmap delete and pixel retention; no public bitmap creation/replacement or rendering certification','cases':[]};keys=[]
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
            async def call(name,args):
                value=await client.call_tool(name,args)
                assert not value.is_error,(name,value.structured_content)
                return value.structured_content['data']
            lid=(await call('capture_library_open',{'sourceLibrary':str(source)}))['libraryId']
            part=next(v for v in (await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'] if v['name']=='GATE.Normal')
            vectors=(await call('capture_query_library_vectors',{'libraryId':lid,'partId':part['objectId'],'limit':1000}))['items']
            assert [v['descriptor'] for v in vectors]==baseline
            for case in cases:
                row={'name':case['name'],'passed':False};report['cases'].append(row)
                try:
                    plan=await call('capture_plan_library_vector_edit',{'libraryId':lid,'partId':part['objectId'],'vectorId':vectors[case['index']]['objectId'],'operation':case['operation'],'replacement':case['replacement']});row['plan']=plan
                    key={k:plan[k] for k in ('planId','planDigest')}
                    result=await call('capture_apply_library_vector_edit',{**key,'idempotencyKey':case['name']});row['result']=result
                    assert result['modeledLibraryPreservationVerified'] and result['declaredVectorEditVerified']
                    output=await call('capture_open_edited_library',{**key,'kind':'vector'});row['opened']=output
                    parts=(await call('capture_library_query',{'libraryId':output['libraryId'],'entity':'part','limit':1000}))['items']
                    rows=[]
                    for saved in parts:
                        if saved['name']!='GATE.Normal':continue
                        observed=(await call('capture_query_library_vectors',{'libraryId':output['libraryId'],'partId':saved['objectId'],'limit':1000}))['items']
                        assert [v['descriptor'] for v in observed]==case['expected']
                        rows.append(observed)
                    assert len(rows)==2
                    row.update(passed=True,observed=rows);keys.append((case['name'],key))
                except BaseException as error:
                    import traceback
                    row.update(error=str(error),traceback=traceback.format_exc())
                print(case['name'],row['passed'],row.get('error'),flush=True)
        async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
            for name,key in keys:
                response=await client.call_tool('capture_apply_library_vector_edit',{**key,'idempotencyKey':name})
                assert not response.is_error and response.structured_content['data']['mutationReplayed'] is False
                assert not (await client.call_tool('capture_recover_library_vector_edit',key)).is_error
                assert not (await client.call_tool('capture_open_edited_library',{**key,'kind':'vector'})).is_error
            report['fresh_lifecycle_no_replay']=True
        report['source_and_oracle_unchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
        report['passed']=len(keys)==len(cases) and report['source_and_oracle_unchanged']
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']

raise SystemExit(0 if asyncio.run(main()) else 1)
