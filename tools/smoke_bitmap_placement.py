"""Actual MCP source-qualified Normal/Convert placement and durable verification."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','baseline','canonical-library-root','arbitrary-library-root'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--diagram-library-root',type=Path)
p.add_argument('--diagram-only',action='store_true')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);before=sha256(source);baseline=json.loads(a.baseline.read_text(encoding='utf-8'));oldpage=next(p for p in baseline['page'] if p['name']=='MCP_PLACE');part_ids={p['objectId'] for p in baseline['part'] if p['pageId']==oldpage['objectId']};existing=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':p['reference'],'pinNumber':p['number'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in baseline['pin'] if p['partId'] in part_ids]
cases=[]
groups=[] if a.diagram_only else [('canonical',a.canonical_library_root.resolve(strict=True)),('arbitrary',a.arbitrary_library_root.resolve(strict=True))]
if a.diagram_library_root:groups.append(('diagram',a.diagram_library_root.resolve(strict=True)))
for group,libroot in groups:
 spec=json.loads((libroot/'spec.json').read_text(encoding='utf-8'))
 for device_name,variant in [('A','Normal'),('B','Convert')]:
  dev=next(d for d in spec['devices'] if d['designator']==device_name);sym=next(s for s in spec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith('.'+variant));mapping={p['position']:p['number'] for p in dev['mapping']};pins=[{'number':mapping[p['position']],'name':p['name'],'hotSpot':[700+p['hotSpot'][0],300+p['hotSpot'][1]],'connected':False,'net':None} for p in sym['pins']];cases.append({'name':group+'-'+variant,'library':str(libroot/'library.olb'),'libraryHash':sha256(libroot/'library.olb'),'partName':sym['partName'],'device':device_name,'reference':'U'+str(601+len(cases)),'pins':pins})
(root/'expected.json').write_text(json.dumps({'existing':existing,'cases':cases},indent=2),encoding='utf-8');oracle_hash=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60']
for parent in sorted({str(Path(c['library']).parent) for c in cases}):args.extend(['--read-root',parent])
params=StdioServerParameters(command=sys.executable,args=args,env=env)
async def main():
 report={'passed':False,'scope':'bitmap-capable fixed-worker placement and legacy Convert; source/cache/actual-view full DIB signature, no rendered appearance verdict','cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   ts=(await client.list_tools()).tools;assert len(ts)==155;(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId'];page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE')
   for case in cases:
    lib=await call('capture_library_open',{'sourceLibrary':case['library']});lid=lib['libraryId'];dev=next(d for d in (await call('capture_library_query',{'libraryId':lid,'entity':'device','limit':1000}))['items'] if d['designator']==case['device']);part=next(p for p in (await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'] if p['name']==case['partName'] and p['deviceId']==dev['objectId']);arguments={'sessionId':sid,'pageId':page['objectId'],'libraryId':lid,'libraryPartId':part['objectId'],'reference':case['reference'],'location':[700,300],'value':'MCP_VIEW','expectedPins':case['pins'],'expectedExistingConnections':existing};plan=await call('capture_plan_placement',arguments);key={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_placement',{**key,'idempotencyKey':case['name']});output=await call('capture_open_edit_result',{**key,'kind':'placement'});assert output['counts']['part']==opened['counts']['part']+1 and output['counts']['pin']==opened['counts']['pin']+len(case['pins']);assert result['expectedDefinitionsVerified'] and result['expectedGlobalHotspotsVerified'] and result['sourceVectorGeometryVerified'];view=json.loads((root/'work'/result['outputWorkspaceRelativePath']/'verified-view.json').read_text(encoding='utf-8'));assert view=={'matches':True,'pinCount':3,'lineCount':5,'vectorCount':14 if case['partName']=='GATE.Normal' else 13};keys.append((case['name'],key));report['cases'].append({'case':case['name'],'plan':plan,'result':result,'opened':output});print(case['name'],'passed',flush=True)
   wrong=[{**pin,'hotSpot':[1400-pin['hotSpot'][0],pin['hotSpot'][1]]} for pin in cases[-1]['pins']];bad=await call('capture_plan_placement',{**arguments,'reference':'U699','expectedPins':wrong});bk={k:bad[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_placement',{**bk,'idempotencyKey':'wrong-view-oracle'});assert v.is_error and v.structured_content['error']['code']=='placement_hotspot_mismatch';assert (await client.call_tool('capture_open_edit_result',{**bk,'kind':'placement'})).is_error;v=await client.call_tool('capture_apply_placement',{**bk,'idempotencyKey':'wrong-view-oracle'});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed';report['wrongViewOracleSavedButRefused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   for name,key in keys:
    v=await client.call_tool('capture_apply_placement',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_placement',key)).is_error;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'placement'})).is_error
   report['freshLifecycleNoReplay']=True
  report['sourceUnchanged']=sha256(source)==before;report['librariesUnchanged']=all(sha256(Path(c['library']))==c['libraryHash'] for c in cases);report['oracleUnchanged']=sha256(root/'expected.json')==oracle_hash;report['passed']=report['sourceUnchanged'] and report['librariesUnchanged'] and report['oracleUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)

