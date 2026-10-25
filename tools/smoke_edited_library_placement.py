"""Actual MCP edited-library -> empty design placement integration."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','library-edit-root','design-fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);libroot=a.library_edit_root.resolve();designroot=a.design_fixture_root.resolve()
old=json.loads((libroot/'report.json').read_text(encoding='utf-8'));libcase=next(c for c in old['cases'] if c['fixture']['source']=='resistor');key={k:libcase['plan'][k] for k in ('planId','planDigest')}
designreport=json.loads((designroot/'report.json').read_text(encoding='utf-8'));source=designroot/'work'/designreport['result']['outputWorkspaceRelativePath']/'design.dsn'
library=libroot/'work'/libcase['result']['outputWorkspaceRelativePath']/'library.olb'
pins=[{'number':'101','name':'A $[x];中文','hotSpot':[280,300],'connected':False,'net':None},{'number':'2','name':'B','hotSpot':[320,300],'connected':False,'net':None}]
(root/'expected.json').write_text(json.dumps({'reference':'R601','location':[300,300],'pins':pins,'designCacheUpdated':False},ensure_ascii=False,indent=2),encoding='utf-8')
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(libroot/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'sourceHashBefore':sha256(source),'libraryHashBefore':sha256(library)}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            async def call(name,args):
                result=await client.call_tool(name,args);assert not result.is_error,result
                return result.structured_content['data']
            opened=await call('capture_open_edited_library',key)
            part=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'part','packageName':'MCP_RES'}))['items'][0]
            ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});ds=await call('capture_open',{'workspaceId':ws['workspaceId']})
            page=(await call('capture_query',{'sessionId':ds['sessionId'],'entity':'page','scope':{'kind':'design'}}))['items'][0]
            plan=await call('capture_plan_placement',{'sessionId':ds['sessionId'],'pageId':page['objectId'],'libraryId':opened['libraryId'],'libraryPartId':part['objectId'],'reference':'R601','location':[300,300],'value':'1k','expectedPins':pins,'expectedExistingConnections':[]});pk={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
            result=await call('capture_apply_placement',{**pk,'idempotencyKey':'edited-lib-R601'});report['result']=result
            output=await call('capture_open_edit_result',{**pk,'kind':'placement'});assert output['counts']=={'schematic':1,'page':1,'part':1,'pin':2}
            part=(await call('capture_query',{'sessionId':output['sessionId'],'entity':'part','scope':{'kind':'design'}}))['items'][0]
            geometry=await call('capture_get_part_geometry',{'sessionId':output['sessionId'],'partId':part['objectId']})
            assert sorted((p['number'],p['name'],p['hotSpot']) for p in geometry['pins'])==sorted((p['number'],p['name'],p['hotSpot']) for p in pins)
            report.update(passed=True,opened=output,geometry=geometry)
    except BaseException as error:report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    finally:
        report.update(sourceHashAfter=sha256(source),libraryHashAfter=sha256(library))
        if report['sourceHashBefore']!=report['sourceHashAfter'] or report['libraryHashBefore']!=report['libraryHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','error')}));return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
