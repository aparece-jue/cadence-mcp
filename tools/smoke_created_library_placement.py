import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','library-fixture-root','page-fixture-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);repo=Path(__file__).resolve().parents[1];libroot=a.library_fixture_root.resolve(strict=True);pageroot=a.page_fixture_root.resolve(strict=True)
libreport=json.loads((libroot/'report.json').read_text(encoding='utf-8'));libplan=next(c['plan'] for c in libreport['cases'] if c['name']=='resistor');libkey={k:libplan[k] for k in ('planId','planDigest')}
page_report=json.loads((pageroot/'report.json').read_text(encoding='utf-8'));created=next(c for c in page_report['cases'] if c['operation']=='create');source=pageroot/'work'/created['result']['outputWorkspaceRelativePath']/'design.dsn'
expected=[{'number':'1','name':'A','hotSpot':[680,300],'connected':False,'net':None},{'number':'2','name':'B','hotSpot':[720,300],'connected':False,'net':None}]
(root/'expected.json').write_text(json.dumps({'reference':'R401','location':[700,300],'pins':expected,'value':'4k7','footprint':'MCP_RES_FP'},indent=2));before=sha256(source)
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(libroot/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'sourceHashBefore':before,'phase':'open'}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            async def call(name,args):
                r=await client.call_tool(name,args);assert not r.is_error,r.content
                return r.structured_content['data']
            library=await call('capture_open_created_library',libkey)
            part=(await call('capture_library_query',{'libraryId':library['libraryId'],'entity':'part','packageName':'MCP_RES'}))['items'][0]
            workspace=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':workspace['workspaceId']})
            page=next(p for p in (await call('capture_query',{'sessionId':opened['sessionId'],'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_EMPTY_ACCEPT')
            report['phase']='placement'
            plan=await call('capture_plan_placement',{'sessionId':opened['sessionId'],'pageId':page['objectId'],'libraryId':library['libraryId'],'libraryPartId':part['objectId'],'reference':'R401','location':[700,300],'value':'4k7','expectedPins':expected,'expectedExistingConnections':[]});key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
            result=await call('capture_apply_placement',{**key,'idempotencyKey':'created-library-placement'});report['result']=result
            output=await call('capture_open_edit_result',{**key,'kind':'placement'});assert output['counts']['part']==opened['counts']['part']+1 and output['counts']['pin']==opened['counts']['pin']+2
            assert result['expectedGlobalHotspotsVerified'] and result['sourceModified'] is False
            report.update(passed=True,opened=output)
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    finally:
        report['sourceHashAfter']=sha256(source)
        if before!=report['sourceHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':report['passed'],'phase':report['phase'],'error':report.get('error'),'report':str(root/'report.json')}))
asyncio.run(main())
