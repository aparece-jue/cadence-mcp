"""Accept an exact unnumbered reference map against the original frozen annotation oracle."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_references import read_units
from cadence_mcp.capture_cache_replace import read_state,unit_graph,cache_groups
from cadence_mcp.capture_cache_bindings import query_cache_binding
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_wire import inventory,connection_digest

async def run(args,root,report):
    source=args.fixture_root/'reset.dsn';oracle=args.fixture_root/'expected.json'
    expected=json.loads(oracle.read_text(encoding='utf8'))
    before={p:sha256(p) for p in (source,oracle)}
    config=Config(args.install_root,root/'verify',(root,),60)
    params=StdioServerParameters(command=sys.executable,args=['-B','-m','cadence_mcp.server','--install-root',str(args.install_root),'--workspace-root',str(root/'work'),'--read-root',str(args.fixture_root)],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
    async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
        async def call(tool,values):
            result=await client.call_tool(tool,values)
            assert not result.is_error,result.content
            return result.structured_content['data']
        ws=await call('cadence_create_workspace',{'sourceDesign':str(source)})
        sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
        parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items']
        target,=[p for p in parts if p['reference']=='R?']
        plan=await call('capture_plan_package_reference_map',{'sessionId':sid,'mappings':[{'partId':target['objectId'],'newReference':'R1'}]})
        assert len(plan['preview']['changes'])==1
        change,=plan['preview']['changes']
        assert change['nativeId']==2502 and change['oldReference']=='R?' and change['newReference']=='R1'
        key={k:plan[k] for k in ('planId','planDigest')}
        result=await call('capture_apply_reference_map',{**key,'idempotencyKey':'exact-unnumbered'})
        assert result['oldNewNodeTableVerified'] and result['packageOwnershipVerified']
        await call('capture_open_edit_result',{**key,'kind':'reference'})
        output=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn'
        cap=CaptureService(config)
        verify_sid=cap.open(cap.create_workspace(str(output))['workspaceId'])['sessionId']
        data=cap.sessions[verify_sid]['data'];units=read_units(cap,verify_sid)
        state=read_state(config,cap.sessions[verify_sid]['design'],cap.sessions[verify_sid]['design'].parent,units)
        report['checks']={
            'originalDefinitionOracle':definition_baseline(data)==definition_baseline(expected['definition']),
            'allInstanceState':state==expected['state'],
            'allUnits':unit_graph(units)==expected['units'],
            'allConnectionObjects':connection_digest(data,inventory(cap,verify_sid))==expected['connectionDigest']}
        owner=next(u for u in units.values() if u['nativeId']==2502)
        query_cache_binding(cap,verify_sid,owner['partId'])
        report['checks']['allCacheGroups']=cache_groups(cap.sessions[verify_sid]['qualifiedCache'])==expected['cache']
        assert all(report['checks'].values()),report['checks']
        report.update(plan=plan,result=result)
    async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
        replay=await fresh.call_tool('capture_apply_reference_map',{**key,'idempotencyKey':'exact-unnumbered'})
        assert not replay.is_error and not replay.structured_content['data']['mutationReplayed']
        recovered=await fresh.call_tool('capture_recover_reference_map',key)
        assert not recovered.is_error
    report['freshRecoveryNoReplay']=True
    report['originalInputsUnchanged']=all(sha256(p)==digest for p,digest in before.items())
    assert report['originalInputsUnchanged']
    report['inputSha256']={p.name:digest for p,digest in before.items()}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('install-root','fixture-root','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();args.fixture_root=args.fixture_root.resolve();root=args.output.resolve();root.mkdir(exist_ok=False)
    report={'passed':False,'nativeAutomaticAnnotationAccepted':False}
    try:
        asyncio.run(run(args,root,report));report['passed']=True
    finally:write_json(root/'report.json',report)
    print(json.dumps({'passed':report['passed']}))

if __name__=='__main__':main()
