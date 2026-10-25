"""Read a known placed DSN cache through real stdio MCP; no cache mutation."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source','cache-name'):p.add_argument('--'+key,required=True)
p.add_argument("--expected-pin-one-name",default="1")
p.add_argument("--require-official-ttl",action="store_true")
a=p.parse_args();root=Path(a.workspace_root).resolve();root.mkdir(exist_ok=False);source=Path(a.source).resolve(strict=True);repo=Path(__file__).resolve().parents[1]
async def main():
    report={'passed':False,'sourceHashBefore':sha256(source),'checks':{}}
    env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
    params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',a.install_root,'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;report['toolCount']=len(tools);schemas={t.name:t.output_schema for t in tools}
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,values):
                r=await client.call_tool(name,values);assert not r.is_error,r.content
                Draft202012Validator(schemas[name]).validate(r.structured_content)
                return r.structured_content['data']
            ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
            if a.require_official_ttl:
                all_packages=await call('capture_query_cache',{'sessionId':sid,'entity':'package','limit':1000})
                assert {'74LS04','74LS08','74LS32'}<=set(p['name'] for p in all_packages['items'])
                report['allPackageNames']=[p['name'] for p in all_packages['items']]
            report['entities']={}
            for entity,count in [('package',1),('device',1),('cell',1),('part',1),('pin',2)]:
                rows=[];cursor=None
                while True:
                    page=await call('capture_query_cache',{'sessionId':sid,'entity':entity,'packageName':a.cache_name,'limit':1,'cursor':cursor})
                    assert page['scope']=='dsn_cache_device_definitions' and not page['cacheSynchronizationVerified']
                    rows+=page['items'];cursor=page['nextCursor']
                    if cursor is None:break
                assert len(rows)==count,(entity,rows)
                report['entities'][entity]=rows
            assert report['entities']['package'][0]['footprint']=='AXRC05'
            assert {(p['number'],p['name']) for p in report['entities']['pin']}=={('1',a.expected_pin_one_name),('2','2')}
            assert all(p['pinType']==4 and p['visible'] for p in report['entities']['pin'])
            assert (await call('capture_query_cache',{'sessionId':sid,'entity':'pin','packageName':'does-not-exist'}))['items']==[]
            assert (await client.call_tool('capture_query_cache',{'sessionId':sid,'entity':'pin','eval':'bad'})).is_error
            report['checks']['native_cache_model_and_empty_filter']=True
            await call('capture_close',{'sessionId':sid})
            assert (await client.call_tool('capture_query_cache',{'sessionId':sid,'entity':'pin'})).is_error
            report['checks']['closed_session_refused']=True;report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        report['sourceHashAfter']=sha256(source)
        if report['sourceHashAfter']!=report['sourceHashBefore']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'tools':report['toolCount'],'report':str(root/'report.json')}))
asyncio.run(main())
