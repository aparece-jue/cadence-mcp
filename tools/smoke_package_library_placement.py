"""Edited package footprint names, including explicit empty, on newly placed instances."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','edit-root','symbol-spec','source','baseline'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);before=sha256(source)
edits=json.loads((a.edit_root/'report.json').read_text(encoding='utf-8'));spec=json.loads(a.symbol_spec.read_text(encoding='utf-8'));base=json.loads(a.baseline.read_text(encoding='utf-8'))
pageid=next(p['objectId'] for p in base['page'] if p['name']=='MCP_PLACE');existing=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':p['reference'],'pinNumber':p['number'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in base['pin'] if p['pageId']==pageid]
cases=[]
for name,devname,variant,ref,footprint in [('create-and-fixed','A','Normal','J851','PKG_51'),('clear-fixed-and-last-user','B','Convert','Q852','')]:
 case=next(c for c in edits['cases'] if c['case']==name);assert case['passed'];library=a.edit_root/'work'/case['result']['outputWorkspaceRelativePath']/'library.olb'
 dev=next(d for d in spec['devices'] if d['designator']==devname);sym=next(s for s in spec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith('.'+variant));mapping={p['position']:p['number'] for p in dev['mapping']}
 pins=[{'number':mapping[p['position']],'name':p['name'],'hotSpot':[700+p['hotSpot'][0],300+p['hotSpot'][1]],'connected':False,'net':None} for p in sym['pins']]
 cases.append({'name':name,'library':str(library),'libraryHash':sha256(library),'device':devname,'partName':sym['partName'],'reference':ref,'footprint':footprint,'pins':pins})
(root/'expected.json').write_text(json.dumps({'existing':existing,'cases':cases},ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60']
for case in cases:args.extend(['--read-root',str(Path(case['library']).parent)])
params=StdioServerParameters(command=sys.executable,args=args,env=env)
async def main():
 report={'passed':False,'scope':'newly placed instance effective footprint name; not existing cache update or external PCB geometry','cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.content);return r.structured_content['data']
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId']
   page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'] if p['name']=='MCP_PLACE')
   for case in cases:
    row={'case':case['name'],'passed':False};report['cases'].append(row)
    try:
     lid=(await call('capture_library_open',{'sourceLibrary':case['library']}))['libraryId'];packages=(await call('capture_library_query',{'libraryId':lid,'entity':'package','limit':1000}))['items'];pkg=next(p for p in packages if p['name']=='MCP_SECOND');assert pkg['footprint']==case['footprint']
     dev=next(d for d in (await call('capture_library_query',{'libraryId':lid,'entity':'device','packageName':'MCP_SECOND','limit':1000}))['items'] if d['designator']==case['device'])
     part=next(p for p in (await call('capture_library_query',{'libraryId':lid,'entity':'part','packageName':'MCP_SECOND','limit':1000}))['items'] if p['deviceId']==dev['objectId'] and p['name']==case['partName'])
     plan=await call('capture_plan_placement',{'sessionId':sid,'pageId':page['objectId'],'libraryId':lid,'libraryPartId':part['objectId'],'reference':case['reference'],'location':[700,300],'value':'MCP_PACKAGE','expectedPins':case['pins'],'expectedExistingConnections':existing});row['plan']=plan;key={k:plan[k] for k in ('planId','planDigest')}
     result=await call('capture_apply_placement',{**key,'idempotencyKey':case['name']});row['result']=result;assert result['sourceVectorGeometryVerified']
     opened=await call('capture_open_edit_result',{**key,'kind':'placement'});row['opened']=opened
     saved=next(p for p in (await call('capture_query',{'sessionId':opened['sessionId'],'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'] if p['reference']==case['reference'])
     props=(await call('capture_get_part_properties',{'sessionId':opened['sessionId'],'partId':saved['objectId']}))['items'];footprints=[p['value'] for p in props if p['name']=='PCB Footprint'];assert footprints==[case['footprint']],footprints
     row.update(passed=True,footprintValues=footprints);keys.append((case['name'],key))
    except BaseException as e:
     import traceback
     row.update(error=str(e),traceback=traceback.format_exc())
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(case['name'],row['passed'],row.get('error'),flush=True)
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for name,key in keys:
    r=await fresh.call_tool('capture_apply_placement',{**key,'idempotencyKey':name});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
    assert not (await fresh.call_tool('capture_recover_placement',key)).is_error
    assert not (await fresh.call_tool('capture_open_edit_result',{**key,'kind':'placement'})).is_error
   report['freshLifecycleNoReplay']=True
  report['sourcesAndOracleUnchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle and all(sha256(Path(c['library']))==c['libraryHash'] for c in cases)
  report['passed']=len(keys)==2 and report['sourcesAndOracleUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
