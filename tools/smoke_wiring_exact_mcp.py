"""Actual MCP explicit-grid geometry acceptance on an owned native wire fixture."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.source.parent),'--timeout-seconds','60'],env=env)
(root/'expected.json').write_text(json.dumps({'page':'MCP_PLACE','wire':[[330,310],[490,310]],'grid10Origin0OffGridVertices':0,'grid10Origin5OffGridVertices':2},indent=2),encoding='utf-8')
async def main():
    report={'passed':False,'sourceHashBefore':sha256(a.source),'checks':{}}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            async def call(name,args,error=None):
                r=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(r.structured_content)
                if error:assert r.is_error and r.structured_content['error']['code']==error,r
                else:assert not r.is_error,r
                return r.structured_content['data']
            ws=await call('cadence_create_workspace',{'sourceDesign':str(a.source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
            pages=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'];page=next(p for p in pages if p['name']=='MCP_PLACE')
            report['reports']=[]
            for origin,wanted in [([0,0],0),([5,5],2)]:
                result=await call('capture_check_wiring',{'sessionId':sid,'gridSize':10,'gridOrigin':origin})
                off=[f for f in result['findings'] if f['pageId']==page['objectId'] and f['ruleId']=='WIRE-OFF-GRID-VERTEX']
                assert len(off)==wanted,(origin,off)
                assert result['profile']=='wire-geometry-advisory@0.2.0' and result['geometryComplete'] and result['designPassed'] is None and not result['electricalConnectivityVerified']
                path=root/'work'/ws['workspaceId']/result['artifact']['workspaceRelativePath'];assert sha256(path)==result['artifact']['sha256']
                report['reports'].append(result)
            await call('capture_check_wiring',{'sessionId':sid,'gridOrigin':[0,0]},'invalid_grid')
            for values in ({'sessionId':sid,'gridSize':True},{'sessionId':sid,'gridSize':10,'gridOrigin':[True,0]}):assert (await client.call_tool('capture_check_wiring',values)).is_error
            (root/'work'/ws['workspaceId']/'design.dsn').write_bytes(b'owned stale design negative')
            await call('capture_check_wiring',{'sessionId':sid,'gridSize':10},'target_changed')
            report.update(toolCount=len(tools),passed=True,checks={'native_grid_declared_origins':True,'artifact_hashes':True,'strict_inputs':True,'tamper_rejected':True})
    except BaseException as error:
        import traceback
        report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    finally:
        report['sourceHashAfter']=sha256(a.source)
        if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','toolCount','checks','error')}));return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
