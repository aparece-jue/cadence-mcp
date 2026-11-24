"""Actual MCP pose guards, retained failures, cancellation and legacy edit regressions."""
import argparse,asyncio,copy,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
from accept_bound_symbol_poses import origin

async def run(a,root,report):
    originals={p:sha256(p) for p in [a.fixture_root/k/'design.dsn' for k in ('global','offpage')]}
    definitions=json.loads(a.definitions.read_text(encoding='utf8'))['definitions']
    params=StdioServerParameters(command=sys.executable,args=['-B','-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.fixture_root),'--timeout-seconds','60'],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
    keys=[]
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
            async def call(tool,args,error=None):
                result=await client.call_tool(tool,args)
                if error:
                    assert result.is_error,result.structured_content
                    if error!='any':assert result.structured_content['error']['code']==error,result.structured_content
                else:assert not result.is_error,result.structured_content
                return result.structured_content['data'] if result.structured_content else None
            for kind in ('global','offpage'):
                ws=await call('cadence_create_workspace',{'sourceDesign':str(a.fixture_root/kind/'design.dsn')})
                sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
                target=next(s for s in (await call('capture_query_connections',{'sessionId':sid,'entity':kind,'limit':1000}))['items'] if s['attributes']['name']==('MCP_SUPPLY' if kind=='global' else 'MCP_LINK'))
                wire=next(w for w in (await call('capture_query_connections',{'sessionId':sid,'entity':'wire','limit':1000}))['items'] if w['pageId']==target['pageId'] and w['attributes']['points']==[[240,310],[290,310]])
                base={'sessionId':sid,'symbolId':target['objectId'],'wireId':wire['objectId']}
                definition=next(d for d in definitions if d['kind']==kind)
                pose={**base,'operation':'set_pose','location':origin(definition,1,1,[220,310]),'rotation':1,'mirror':1,'expectedHotSpot':[220,310],'allowSourceCacheRebind':kind=='offpage'}
                before=(await call('capture_net_symbol_edit_jobs',{}))['total']
                if kind=='offpage':await call('capture_plan_net_symbol_edit',{**pose,'allowSourceCacheRebind':False},'offpage_pose_rebind_required')
                await call('capture_plan_net_symbol_edit',{**pose,'location':[True,0]},'any')
                assert (await call('capture_net_symbol_edit_jobs',{}))['total']==before
                report['checks'].append(kind+'-preplan-policy-and-schema-refusal')
                bad=copy.deepcopy(pose);bad['location'][0]+=1
                plan=await call('capture_plan_net_symbol_edit',bad);key={k:plan[k] for k in ('planId','planDigest')};ident=kind+'-wrong-hotspot'
                await call('capture_apply_net_symbol_edit',{**key,'idempotencyKey':ident},'native_write_failed')
                await call('capture_open_edit_result',{**key,'kind':'net_symbol_edit'},'output_unverified')
                await call('capture_apply_net_symbol_edit',{**key,'idempotencyKey':ident},'write_not_replayed')
                job=root/'work/isolated-jobs/capture_net_symbol_edit'/('plan-'+key['planId'])
                receipt=json.loads((job/'native-result.json').read_text());assert not receipt['saved'] and receipt['message']=='expected_hotspot_mismatch',receipt
                assert sha256(job/'design.dsn')==sha256(a.fixture_root/kind/'design.dsn')
                report['checks'].append(kind+'-wrong-hotspot-before-save-no-open-no-replay')
                plan=await call('capture_plan_net_symbol_edit',{**pose,'expectedWireNet':'WRONG_ORACLE'});key={k:plan[k] for k in ('planId','planDigest')};ident=kind+'-wrong-node'
                await call('capture_apply_net_symbol_edit',{**key,'idempotencyKey':ident},'alias_owner_name_mismatch')
                await call('capture_open_edit_result',{**key,'kind':'net_symbol_edit'},'output_unverified')
                await call('capture_apply_net_symbol_edit',{**key,'idempotencyKey':ident},'write_not_replayed')
                report['checks'].append(kind+'-wrong-node-oracle-no-open-no-replay')
                plan=await call('capture_plan_net_symbol_edit',pose);key={k:plan[k] for k in ('planId','planDigest')}
                await call('capture_cancel_net_symbol_edit',key);await call('capture_apply_net_symbol_edit',{**key,'idempotencyKey':kind+'-cancel'},'any')
                assert not (root/'work/isolated-jobs/capture_net_symbol_edit'/('plan-'+key['planId'])/'native-result.json').exists()
                report['checks'].append(kind+'-cancel-before-native')
                for operation in ('set_name','delete'):
                    args={**base,'operation':operation}
                    if operation=='set_name':args['name']='MCP_'+kind.upper()+'_LEGACY'
                    plan=await call('capture_plan_net_symbol_edit',args);key={k:plan[k] for k in ('planId','planDigest')};ident=kind+'-legacy-'+operation
                    result=await call('capture_apply_net_symbol_edit',{**key,'idempotencyKey':ident});assert result['nativePagePartitionsVerified']
                    job=root/'work'/result['outputWorkspaceRelativePath'];keys.append((ident,key,job/'design.dsn',sha256(job/'design.dsn')))
                    report['checks'].append(kind+'-legacy-'+operation)
                await call('capture_close',{'sessionId':sid})
                (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'kind':kind,'checks':len(report['checks'])}),flush=True)
        async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
            for ident,key,path,digest in keys:
                value=await fresh.call_tool('capture_apply_net_symbol_edit',{**key,'idempotencyKey':ident});assert not value.is_error and not value.structured_content['data']['mutationReplayed']
                value=await fresh.call_tool('capture_recover_net_symbol_edit',key);assert not value.is_error
                assert sha256(path)==digest
            _,key,path,digest=keys[-1];blob=path.read_bytes()
            try:
                path.write_bytes(blob+b'owned terminal tamper');value=await fresh.call_tool('capture_open_edit_result',{**key,'kind':'net_symbol_edit'});assert value.is_error and value.structured_content['error']['code']=='target_changed'
            finally:path.write_bytes(blob)
            assert sha256(path)==digest
        report.update(passed=True,freshLegacyRecoveryNoReplay=True,terminalTamperRefusedAndRestored=True)
    finally:
        report['originalInputsUnchanged']=all(sha256(p)==digest for p,digest in originals.items());report['inputSha256']={str(p):digest for p,digest in originals.items()};report['passed']=report['passed'] and report['originalInputsUnchanged']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('install-root','fixture-root','definitions','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();a.fixture_root=a.fixture_root.resolve();a.definitions=a.definitions.resolve();root=a.output.resolve();root.mkdir(exist_ok=False);report={'passed':False,'fullD04Accepted':False,'checks':[]}
    try:asyncio.run(run(a,root,report))
    except BaseException:report['error']=traceback.format_exc()
    finally:(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')}));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
