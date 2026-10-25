"""Native MCP placement acceptance on the original two-resistor fixture."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source','library'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
source=a.source.resolve(strict=True);lib=a.library.resolve(strict=True)
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),
    '--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(lib.parent),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'checks':{},'sourceHashBefore':sha256(source),'libraryHashBefore':sha256(lib)}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;report['toolCount']=len(tools);schemas={t.name:t.output_schema for t in tools}
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,values):
                row=await client.call_tool(name,values);assert not row.is_error,row.content
                Draft202012Validator(schemas[name]).validate(row.structured_content)
                return row.structured_content['data']
            ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
            page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE')
            library=await call('capture_library_open',{'sourceLibrary':str(lib)});lid=library['libraryId']
            part=(await call('capture_library_query',{'libraryId':lid,'entity':'part','packageName':'R'}))['items'][0]
            expected=[{'number':'1','name':'1','hotSpot':[690,310],'connected':False,'net':None},{'number':'2','name':'2','hotSpot':[730,310],'connected':False,'net':None}]
            existing=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':r,'pinNumber':p,'connected':False,'net':None} for r in ('R101','R102') for p in ('1','2')]
            args={'sessionId':sid,'pageId':page['objectId'],'libraryId':lid,'libraryPartId':part['objectId'],'reference':'R103','location':[700,300],'value':'2k','expectedPins':expected,'expectedExistingConnections':existing}
            plan=await call('capture_plan_placement',args);keys={k:plan[k] for k in ('planId','planDigest')}
            result=await call('capture_apply_placement',{**keys,'idempotencyKey':'placed-happy'})
            assert result['expectedGlobalHotspotsVerified'] and not result['embeddedCacheClosureVerified']
            output=await call('capture_open_edit_result',{**keys,'kind':'placement'});assert output['counts']['part']==12 and output['counts']['pin']==47
            report['happy']={'plan':plan,'result':result};report['checks']['mcp_save_hotspots_properties_reopen']=True
            bad=await call('capture_plan_placement',{**args,'reference':'R104','expectedPins':[{**p,'hotSpot':[0,0]} for p in expected]})
            bad_keys={k:bad[k] for k in ('planId','planDigest')}
            rejected=await client.call_tool('capture_apply_placement',{**bad_keys,'idempotencyKey':'bad-hotspot'})
            assert rejected.is_error and rejected.structured_content['error']['code']=='placement_hotspot_mismatch',rejected.content
            assert (await client.call_tool('capture_open_edit_result',{**bad_keys,'kind':'placement'})).is_error
            report['checks']['native_wrong_global_hotspots_refused']=True
            pending=await call('capture_plan_placement',{**args,'reference':'R105'});pending_keys={k:pending[k] for k in ('planId','planDigest')}
            await call('capture_cancel_placement',pending_keys)
            assert (await client.call_tool('capture_apply_placement',{**pending_keys,'idempotencyKey':'cancelled'})).is_error
            assert (await client.call_tool('capture_plan_placement',{**args,'eval':'bad'})).is_error
            jobs=await call('capture_placement_jobs',{});assert sorted(j['state'] for j in jobs['jobs'])==['cancelled','failed','verified']
            report['checks']['cancel_jobs_strict_parameters']=True
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            replay=await fresh.call_tool('capture_apply_placement',{**keys,'idempotencyKey':'placed-happy'})
            assert not replay.is_error and replay.structured_content['data']['mutationReplayed'] is False
            assert not (await fresh.call_tool('capture_open_edit_result',{**keys,'kind':'placement'})).is_error
            report['checks']['fresh_server_idempotence_output_open']=True
        report['passed']=True
    except BaseException as error:report['error']=str(error);raise
    finally:
        report.update(sourceHashAfter=sha256(source),libraryHashAfter=sha256(lib))
        if report['sourceHashBefore']!=report['sourceHashAfter'] or report['libraryHashBefore']!=report['libraryHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'tools':report['toolCount'],'checks':report['checks'],'report':str(root/'report.json')}))
asyncio.run(main())
