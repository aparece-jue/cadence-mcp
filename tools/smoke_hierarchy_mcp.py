"""Actual stdio acceptance for occurrence structure; no full net claim."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256

p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','source'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--with-clone',action='store_true')
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
expected={'':['halfadd_A','halfadd_B','U1A'],
 'halfadd_A':['U3A','U2A','U3B','U2B','U2C','U1B'],
 'halfadd_B':['U3C','U2D','U3D','U4A','U4B','U1C']}
if a.with_clone:
    expected[''].append('halfadd_C');expected['halfadd_C']=expected['halfadd_A'][:]
expected_count=23 if a.with_clone else 16
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
async def main():
    report={'passed':False,'transport':'stdio','checks':{},'sourceHashBefore':sha256(a.source)}
    env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
    params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server',
        '--install-root',str(a.install_root),'--workspace-root',str(root/'work'),
        '--read-root',str(a.source.parent),'--timeout-seconds','60'],env=env)
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools
            schemas={t.name:t.output_schema for t in tools}
            for t in tools:
                Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,values,error=None):
                result=await client.call_tool(name,values)
                Draft202012Validator(schemas[name]).validate(result.structured_content)
                if error:
                    assert result.is_error and result.structured_content['error']['code']==error,result
                else:assert not result.is_error,result
                return result.structured_content
            ws=(await call('cadence_create_workspace',{'sourceDesign':str(a.source)}))['data']
            opened=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['data'];sid=opened['sessionId']
            first=await call('capture_get_hierarchy',{'sessionId':sid,'limit':3})
            assert first['status']=='partial' and not first['evidence']['complete']
            rows=first['data']['items'][:];cursor=first['data']['nextCursor']
            await call('capture_get_hierarchy',{'sessionId':sid,'cursor':cursor,'limit':4},'stale_cursor')
            while cursor:
                page=(await call('capture_get_hierarchy',{'sessionId':sid,'cursor':cursor,'limit':3}))['data']
                rows+=page['items'];cursor=page['nextCursor']
            assert len(rows)==expected_count and len({tuple(r['instancePathSegments']) for r in rows})==expected_count
            by_id={r['occurrenceId']:r for r in rows};actual={k:[] for k in expected}
            for r in rows:
                if r['parentId'] is not None:actual[by_id[r['parentId']]['reference']].append(r['reference'])
            assert {k:sorted(v) for k,v in actual.items()}=={k:sorted(v) for k,v in expected.items()}
            assert len({r['path'] for r in rows})<expected_count
            whole=(await call('capture_get_hierarchy',{'sessionId':sid,'limit':1000}))['data']
            assert whole['items']==rows and whole['identityScope']=='session_revision'
            assert not whole['occurrenceConnectivityVerified']
            report['checks']['tree_units_paging_and_schema']=True
            for values in ({'sessionId':sid,'limit':True},{'sessionId':sid,'limit':0},{'sessionId':sid,'exec':'x'}):
                assert (await client.call_tool('capture_get_hierarchy',values)).is_error
            second=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['data']
            await call('capture_get_hierarchy',{'sessionId':second['sessionId'],'cursor':first['data']['nextCursor'],'limit':3},'stale_cursor')
            assert (await call('capture_get_hierarchy',{'sessionId':second['sessionId'],'limit':1000}))['data']['items']==rows
            await call('capture_close',{'sessionId':sid})
            await call('capture_get_hierarchy',{'sessionId':sid},'session_lost')
            (root/'work'/ws['workspaceId']/'design.dsn').write_bytes(b'owned tamper negative')
            await call('capture_get_hierarchy',{'sessionId':second['sessionId']},'target_changed')
            report.update(items=rows,toolCount=len(tools))
            report['checks'].update(strict_inputs=True,reopen_and_cursor_binding=True,close_and_tamper_rejection=True)
        report['passed']=True
    except BaseException as error:report.update(errorType=type(error).__name__,error=str(error))
    finally:
        report['sourceHashAfter']=sha256(a.source)
        if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='items'},ensure_ascii=False))
    return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
