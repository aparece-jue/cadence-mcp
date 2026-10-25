"""Real MCP unit-aware edits with independently frozen source-symbol pose oracles."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','placement-root','library-root'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--cases',nargs='+')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);oldroot=a.placement_root.resolve(strict=True);old=json.loads((oldroot/'report.json').read_text(encoding='utf-8'));sources={c['case']:oldroot/'work'/c['result']['outputWorkspaceRelativePath']/'design.dsn' for c in old['cases']};before={k:sha256(v) for k,v in sources.items()};libroot=a.library_root.resolve(strict=True);cases=[]
definitions=[('move-A','dual-unbound','hidden','shared_dual','A','set_pose',[1000,900],0,0),('rotate-B','dual-unbound','hidden','shared_dual','B','set_pose',[1200,700],1,0),('mirror-B','dual-unbound','hidden','shared_dual','B','set_pose',[1200,700],0,1),('delete-B','dual-unbound','hidden','shared_dual','B','delete',None,None,None),('move-shared-power-A','hetero-power','visible','heterogeneous_power','A','set_pose',[1000,900],0,0),('delete-power-P','hetero-power','visible','heterogeneous_power','P','delete',None,None,None),('wrong-hotspot','dual-unbound','hidden','shared_dual','A','set_pose',[1000,900],0,0)]
for name,source,mode,kind,device,op,location,rotation,mirror in definitions:
 spec=json.loads((libroot/mode/kind/'spec.json').read_text(encoding='utf-8'));dev=next(d for d in spec['devices'] if d['designator']==device);suffix='.Convert' if device=='B' else '.Normal';symbol=next(s for s in spec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith(suffix));mapping={p['position']:p['number'] for p in dev['mapping']};pins=[]
 if op=='set_pose':
  for pin in symbol['pins']:
   x,y=pin['hotSpot'];x=-x if mirror else x
   for _ in range(rotation):x,y=y,-x
   pins.append({'number':mapping[pin['position']],'name':pin['name'],'hotSpot':[location[0]+x,location[1]+y]})
  if name=='wrong-hotspot':pins[0]['hotSpot'][0]+=1
 cases.append({'name':name,'source':source,'device':device,'operation':op,'location':location,'rotation':rotation,'mirror':mirror,'pins':pins})
if a.cases:cases=[c for c in cases if c['name'] in a.cases]
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');oracle_hash=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--timeout-seconds','60']
for parent in sorted({str(v.parent) for v in sources.values()}):args.extend(['--read-root',parent])
params=StdioServerParameters(command=sys.executable,args=args,env=env)
async def main():
 report={'passed':False,'scope':'single internal unit pose/delete under explicit page definition/native pin oracle; no flat/occurrence certification','cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=300) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   ts=(await client.list_tools()).tools;assert len(ts)==142;(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   for case in cases:
    row={'case':case['name'],'passed':False};report['cases'].append(row)
    try:
     ws=await call('cadence_create_workspace',{'sourceDesign':str(sources[case['source']])});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId'];parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];pins=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];group=[p for p in parts if p['reference']=='U501'];expected_location=[1000+200*('ABP'.index(case['device'])),700];target=None
     for part in group:
      geo=await call('capture_get_part_geometry',{'sessionId':sid,'partId':part['objectId']})
      if geo['location']==expected_location:target=part
     assert target is not None;remaining=[p for p in pins if p['pageId']==target['pageId'] and not (case['operation']=='delete' and p['partId']==target['objectId'])];connections=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in remaining];arguments={'sessionId':sid,'partId':target['objectId'],'operation':case['operation'],'expectedConnections':[],'expectedUnitConnections':connections}
     if case['operation']=='set_pose':arguments.update(location=case['location'],rotation=case['rotation'],mirror=case['mirror'],expectedPins=case['pins'])
     plan=await call('capture_plan_part_edit',arguments);row['plan']=plan;assert plan['preview']['unit']['deviceDesignator']==case['device'];key={k:plan[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_part_edit',{**key,'idempotencyKey':case['name']})
     if case['name']=='wrong-hotspot':
      assert v.is_error and v.structured_content['error']['code']=='unit_edit_geometry_mismatch';assert (await client.call_tool('capture_open_edit_result',{**key,'kind':'part_edit'})).is_error;v=await client.call_tool('capture_apply_part_edit',{**key,'idempotencyKey':case['name']});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed';row['expectedError']='unit_edit_geometry_mismatch';row['passed']=True
     else:
      assert not v.is_error,v.content;result=v.structured_content['data'];assert result['unitAware'] and result['unitIdentityVerified'] and result['nativePageNetworksVerified'] and result['cachePinMetadataVerified'];output=await call('capture_open_edit_result',{**key,'kind':'part_edit'});assert output['counts']['part']==opened['counts']['part']-(case['operation']=='delete');row.update(result=result,opened=output,passed=True);keys.append((case['name'],key))
    except BaseException as e:
     import traceback
     row.update(error=str(e),traceback=traceback.format_exc())
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(case['name'],row['passed'],row.get('error'),flush=True)
  async with Client(params,mode='legacy',read_timeout_seconds=300) as client:
   for name,key in keys:
    v=await client.call_tool('capture_apply_part_edit',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_part_edit',key)).is_error;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'part_edit'})).is_error
   report['freshLifecycleNoReplay']=True
  report['sourceHashesUnchanged']=all(sha256(v)==before[k] for k,v in sources.items());report['oracleUnchanged']=sha256(root/'expected.json')==oracle_hash;report['passed']=all(c['passed'] for c in report['cases']) and report['sourceHashesUnchanged'] and report['oracleUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
