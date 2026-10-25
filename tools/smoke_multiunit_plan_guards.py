"""Real MCP physical-pad consistency and complete pinId preflight guards."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','library-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);libroot=a.library_root.resolve(strict=True);lib=libroot/'library.olb';spec=json.loads((libroot/'spec.json').read_text(encoding='utf-8'));before=(sha256(source),sha256(lib));env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(libroot)],env=env)
async def main():
 report={'passed':False,'scope':'preflight guards, no native group mutation'}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId'];page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'] if p['name']=='MCP_PLACE');lid=(await call('capture_library_open',{'sourceLibrary':str(lib)}))['libraryId'];devices=(await call('capture_library_query',{'libraryId':lid,'entity':'device','limit':1000}))['items'];parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'];pins=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];existing=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in pins if p['pageId']==page['objectId']];units=[]
   for i,device in enumerate(spec['devices']):
    suffix='.Convert' if device['designator']=='B' else '.Normal';sym=next(s for s in spec['symbols'] if s['cellName']==device['cellName'] and s['partName'].endswith(suffix));dev=next(d for d in devices if d['designator']==device['designator']);part=next(p for p in parts if p['deviceId']==dev['objectId'] and p['name']==sym['partName']);mapping={p['position']:p['number'] for p in device['mapping']};location=[1000+200*i,700];units.append({'libraryPartId':part['objectId'],'location':location,'expectedPins':[{'number':mapping[p['position']],'name':p['name'],'hotSpot':[location[j]+p['hotSpot'][j] for j in (0,1)],'connected':False,'net':None} for p in sym['pins']]})
   args={'sessionId':sid,'pageId':page['objectId'],'libraryId':lid,'reference':'U501','value':'GROUP','units':units,'expectedExistingConnections':existing};failures=[]
   for name,nets in [('conflicting-nets',('VCC','GND')),('mixed-unresolved-binding',('VCC',None))]:
    rows=copy.deepcopy(units)
    for unit,net in zip(rows,nets):next(p for p in unit['expectedPins'] if p['number']=='8').update(connected=net is not None,net=net)
    v=await client.call_tool('capture_plan_multiunit_placement',{**args,'units':rows});assert v.is_error and v.structured_content['error']['code']=='shared_pin_binding_conflict';failures.append(name)
   for name,change,code in [('duplicate-device',{'units':[units[0]]*2},'invalid_group'),('missing-existing-pin',{'expectedExistingConnections':existing[:-1]},'incomplete_expectations'),('existing-reference',{'reference':'R101'},'reference_conflict')]:
    v=await client.call_tool('capture_plan_multiunit_placement',{**args,**change});assert v.is_error and v.structured_content['error']['code']==code;failures.append(name)
   assert (await client.call_tool('capture_plan_multiunit_placement',{**args,'eval':'forbidden'})).is_error
   jobs=await call('capture_multiunit_placement_jobs',{});assert len(jobs['jobs'])==0;report['refusedBeforeDurablePlan']=failures+['extra-field'];plan=await call('capture_plan_multiunit_placement',args);key={k:plan[k] for k in ('planId','planDigest')};await call('capture_cancel_multiunit_placement',key);report['validConsistentGroupPlansAndCancels']=True
  report['hashesUnchanged']=before==(sha256(source),sha256(lib));report['passed']=report['hashesUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
