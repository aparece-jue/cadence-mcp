"""Actual MCP atomic same-reference package placement, preservation and refusal gates."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','wire-frame','library-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);frame=a.wire_frame.resolve(strict=True);libroot=a.library_root.resolve(strict=True);cases=[]
for name,mode,kind,path in [('dual-unbound','hidden','shared_dual',source),('hetero-unbound','hidden','heterogeneous_power',source),('hetero-power','visible','heterogeneous_power',frame)]:
 libdir=libroot/mode/kind;spec=json.loads((libdir/'spec.json').read_text(encoding='utf-8'));declarations=[]
 for i,dev in enumerate(spec['devices']):
  variant='Convert' if dev['designator']=='B' else 'Normal';sym=next(s for s in spec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith('.'+variant));loc=[1000+200*i,700];mapping={m['position']:m['number'] for m in dev['mapping']};pins=[{'number':mapping[p['position']],'name':p['name'],'hotSpot':[loc[j]+p['hotSpot'][j] for j in (0,1)],'connected':name=='hetero-power' and p['name'] in ('VCC','GND'),'net':p['name'] if name=='hetero-power' and p['name'] in ('VCC','GND') else None} for p in sym['pins']];declarations.append({'partName':sym['partName'],'device':dev['designator'],'location':loc,'pins':pins})
 cases.append({'name':name,'source':str(path),'sourceHash':sha256(path),'library':str(libdir/'library.olb'),'libraryHash':sha256(libdir/'library.olb'),'units':declarations})
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--timeout-seconds','60']
for parent in sorted({str(Path(c[k]).parent) for c in cases for k in ('source','library')}):args.extend(['--read-root',parent])
params=StdioServerParameters(command=sys.executable,args=args,env=env)
async def main():
 report={'passed':False,'scope':'complete same-page source package tasks; no incremental unit edits or flat/occurrence/DRC','cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   ts=(await client.list_tools()).tools;assert len(ts)==142;(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   for case in cases:
    ws=await call('cadence_create_workspace',{'sourceDesign':case['source']});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId'];page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'] if p['name']=='MCP_PLACE');lid=(await call('capture_library_open',{'sourceLibrary':case['library']}))['libraryId'];devices=(await call('capture_library_query',{'libraryId':lid,'entity':'device','limit':1000}))['items'];parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'];allpins=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];existing=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in allpins if p['pageId']==page['objectId']];units=[]
    for unit in case['units']:
     dev=next(d for d in devices if d['designator']==unit['device']);part=next(p for p in parts if p['name']==unit['partName'] and p['deviceId']==dev['objectId']);units.append({'libraryPartId':part['objectId'],'location':unit['location'],'expectedPins':unit['pins']})
    arguments={'sessionId':sid,'pageId':page['objectId'],'libraryId':lid,'reference':'U501','value':'MCP_GROUP_VALUE','units':units,'expectedExistingConnections':existing};plan=await call('capture_plan_multiunit_placement',arguments);key={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_multiunit_placement',{**key,'idempotencyKey':case['name']});output=await call('capture_open_edit_result',{**key,'kind':'multiunit_placement'});assert output['counts']['part']==opened['counts']['part']+len(units) and output['counts']['pin']==opened['counts']['pin']+sum(len(u['pins']) for u in case['units']);assert result['unitOwnershipVerified'] and result['nativePageNetworksVerified'] and result['sourcePinLineViewsVerified'];row={'case':case['name'],'plan':plan,'result':result,'opened':output};report['cases'].append(row);keys.append((case['name'],key));print(case['name'],'passed',flush=True)
    assert (await client.call_tool('capture_plan_multiunit_placement',{**arguments,'units':[units[0]]*len(units)})).is_error
    if case['name']=='dual-unbound':
     bad_units=copy.deepcopy(units);bad_units[0]['expectedPins'][0]['hotSpot']=[0,0];bad=await call('capture_plan_multiunit_placement',{**arguments,'reference':'U599','units':bad_units});bk={k:bad[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_multiunit_placement',{**bk,'idempotencyKey':'wrong-group-hotspot'});assert v.is_error and v.structured_content['error']['code']=='group_hotspot_mismatch';assert (await client.call_tool('capture_open_edit_result',{**bk,'kind':'multiunit_placement'})).is_error;v=await client.call_tool('capture_apply_multiunit_placement',{**bk,'idempotencyKey':'wrong-group-hotspot'});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed';report['wrongOracleSavedButRefused']=True
     out_sid=output['sessionId'];out_page=next(p for p in (await call('capture_query',{'sessionId':out_sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'] if p['name']=='MCP_PLACE');outpins=(await call('capture_query',{'sessionId':out_sid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];old=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in outpins if p['pageId']==out_page['objectId']];next_units=copy.deepcopy(units)
     for u in next_units:
      u['location'][0]+=600
      for pin in u['expectedPins']:pin['hotSpot'][0]+=600
     next_args={**arguments,'sessionId':out_sid,'pageId':out_page['objectId'],'reference':'U502','units':next_units,'expectedExistingConnections':old};assert (await client.call_tool('capture_plan_multiunit_placement',{**next_args,'reference':'U501'})).is_error
     second=await call('capture_plan_multiunit_placement',next_args);sk={k:second[k] for k in ('planId','planDigest')};sr=await call('capture_apply_multiunit_placement',{**sk,'idempotencyKey':'second-group'});assert sr['originalPageGeometryVerified'];report['secondGroupPreservesRepeatedReferences']={'plan':second,'result':sr};keys.append(('second-group',sk))
   pending=await call('capture_plan_multiunit_placement',{**arguments,'reference':'U598'});pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_multiunit_placement',pk);assert (await client.call_tool('capture_apply_multiunit_placement',{**pk,'idempotencyKey':'pending-cancel'})).is_error;report['pendingCancelVerified']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   for name,key in keys:
    v=await client.call_tool('capture_apply_multiunit_placement',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_multiunit_placement',key)).is_error;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'multiunit_placement'})).is_error
   report['freshLifecycleNoReplay']=True
  report['sourcesUnchanged']=all(sha256(Path(c[k]))==c[k+'Hash'] for c in cases for k in ('source','library'));report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['sourcesUnchanged'] and report['oracleUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
