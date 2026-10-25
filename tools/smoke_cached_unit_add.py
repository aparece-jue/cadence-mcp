"""Actual MCP existing-cache unit restoration, durable lifecycle and preflight guards."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','native-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);native=a.native_root.resolve(strict=True);cases=[]
for name in ('restore-B','restore-P'):
 d=native/name;request=json.loads((d/'request.json').read_text(encoding='utf-8'));expected=json.loads((d/'expected.json').read_text(encoding='utf-8'));old=json.loads((native/'report.json').read_text(encoding='utf-8'));source_hash=next(c['sourceBefore'] for c in old['cases'] if c['case']==name);cases.append({'name':name,'request':request,'expected':expected,'sourceHash':source_hash})
# Authoritative original source path comes from the preceding verified delete ledger, not restored output.
sources={}
for name,oldroot,label in [('restore-B',Path('.local/unit-edits-mcp-20261024'),'delete-B'),('restore-P',Path('.local/unit-edits-final-targeted-20261024'),'delete-power-P')]:
 oldroot=oldroot.resolve(strict=True);report=json.loads((oldroot/'report.json').read_text(encoding='utf-8'));case=next(c for c in report['cases'] if c['case']==label);sources[name]=oldroot/'work'/case['result']['outputWorkspaceRelativePath']/'design.dsn';assert sha256(sources[name])==case['result']['artifact']['sha256']
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--timeout-seconds','60']
for parent in sorted({str(p.parent) for p in sources.values()}):args.extend(['--read-root',parent])
params=StdioServerParameters(command=sys.executable,args=args,env=env)
async def main():
 report={'passed':False,'scope':'same-page existing-cache missing unit tasks, no external OLB import or full flat/cross-page certification','cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=300) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   ts=(await client.list_tools()).tools;assert len(ts)==143;(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   for case in cases:
    req=case['request'];sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(sources[case['name']])}))['workspaceId']}))['sessionId'];parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];owner=None
    for p in parts:
     if p['reference']!='U501':continue
     if (await call('capture_get_part_geometry',{'sessionId':sid,'partId':p['objectId']}))['location']==[1000,700]:owner=p
    assert owner;cacheparts=(await call('capture_query_cache',{'sessionId':sid,'entity':'part','limit':1000}))['items'];cachedevices=(await call('capture_query_cache',{'sessionId':sid,'entity':'device','limit':1000}))['items'];wanted_device=next(d for d in cachedevices if d['designator']==req['deviceDesignator'] and any(p['deviceId']==d['objectId'] and p['name']==req['partName'] for p in cacheparts));cached=next(p for p in cacheparts if p['name']==req['partName'] and p['deviceId']==wanted_device['objectId']);pins=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];existing=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in pins if p['pageId']==owner['pageId']];newpins=[{**p,'net':p['net'] if p['connected'] else None} for p in case['expected']['pins']];arguments={'sessionId':sid,'ownerPartId':owner['objectId'],'cachePartId':cached['objectId'],'location':req['location'],'expectedPins':newpins,'expectedExistingConnections':existing};plan=await call('capture_plan_cached_unit_add',arguments);key={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_multiunit_placement',{**key,'idempotencyKey':case['name']});output=await call('capture_open_edit_result',{**key,'kind':'multiunit_placement'});assert result['operation']=='add_cached_unit' and result['unitOwnershipVerified'] and result['nativePageNetworksVerified'] and result['cachedViewVerified'];report['cases'].append({'case':case['name'],'plan':plan,'result':result,'opened':output});keys.append((case['name'],key));print(case['name'],'passed',flush=True)
    assert (await client.call_tool('capture_plan_cached_unit_add',{**arguments,'expectedExistingConnections':existing[:-1]})).is_error
    foreign=next(p for p in cacheparts if p['packageId']!=cached['packageId']);v=await client.call_tool('capture_plan_cached_unit_add',{**arguments,'cachePartId':foreign['objectId']});assert v.is_error and v.structured_content['error']['code']=='cache_package_mismatch'
    if case['name']=='restore-B':
     bad=copy.deepcopy(newpins);bad[0]['hotSpot']=[0,0];bp=await call('capture_plan_cached_unit_add',{**arguments,'expectedPins':bad});bk={k:bp[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_multiunit_placement',{**bk,'idempotencyKey':'wrong-cache-unit-hotspot'});assert v.is_error and v.structured_content['error']['code']=='cached_unit_hotspot_mismatch';assert (await client.call_tool('capture_open_edit_result',{**bk,'kind':'multiunit_placement'})).is_error;v=await client.call_tool('capture_apply_multiunit_placement',{**bk,'idempotencyKey':'wrong-cache-unit-hotspot'});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed';report['wrongOracleSavedButRefused']=True
    out_sid=output['sessionId'];outparts=(await call('capture_query',{'sessionId':out_sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];outowner=next(p for p in outparts if p['reference']=='U501');outcache=(await call('capture_query_cache',{'sessionId':out_sid,'entity':'part','limit':1000}))['items'];outdevices=(await call('capture_query_cache',{'sessionId':out_sid,'entity':'device','limit':1000}))['items'];outdevice=next(d for d in outdevices if d['designator']==req['deviceDesignator'] and any(p['deviceId']==d['objectId'] and p['name']==req['partName'] for p in outcache));outcached=next(p for p in outcache if p['name']==req['partName'] and p['deviceId']==outdevice['objectId']);v=await client.call_tool('capture_plan_cached_unit_add',{**arguments,'sessionId':out_sid,'ownerPartId':outowner['objectId'],'cachePartId':outcached['objectId']});assert v.is_error and v.structured_content['error']['code']=='unit_already_placed';report['occupiedDeviceRefused']=True
   pending=await call('capture_plan_cached_unit_add',arguments);pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_multiunit_placement',pk);assert (await client.call_tool('capture_apply_multiunit_placement',{**pk,'idempotencyKey':'cancel-cache-unit'})).is_error;report['pendingCancelVerified']=True
  async with Client(params,mode='legacy',read_timeout_seconds=300) as client:
   for name,key in keys:
    v=await client.call_tool('capture_apply_multiunit_placement',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_multiunit_placement',key)).is_error;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'multiunit_placement'})).is_error
   report['freshLifecycleNoReplay']=True
  report['sourcesUnchanged']=all(sha256(sources[c['name']])==c['sourceHash'] for c in cases);report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['sourcesUnchanged'] and report['oracleUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)

