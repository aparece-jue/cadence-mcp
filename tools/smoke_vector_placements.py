"""Actual MCP alternate views differing only in one declared non-line vector."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','baseline','vector-root','text-root'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--kinds',nargs='+',choices=('box','ellipse','arc','polygon','polyline','bezier','fill','text'),required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);before=sha256(source);baseline=json.loads(a.baseline.read_text(encoding='utf-8'));pageid=next(p['objectId'] for p in baseline['page'] if p['name']=='MCP_PLACE');existing=[{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':p['reference'],'pinNumber':p['number'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in baseline['pin'] if p['pageId']==pageid];cases=[]
for kind in a.kinds:
 d=(a.text_root/'text' if kind=='text' else a.vector_root/kind).resolve(strict=True);spec=json.loads((d/'spec.json').read_text(encoding='utf-8'))
 for devname,variant in [('A','Normal'),('B','Convert')]:
  dev=next(v for v in spec['devices'] if v['designator']==devname);sym=next(s for s in spec['symbols'] if s['cellName']==dev['cellName'] and s['partName'].endswith('.'+variant));mapping={p['position']:p['number'] for p in dev['mapping']};pins=[{'number':mapping[p['position']],'name':p['name'],'hotSpot':[700+p['hotSpot'][0],300+p['hotSpot'][1]],'connected':False,'net':None} for p in sym['pins']];cases.append({'name':kind+'-'+variant,'library':str(d/'library.olb'),'libraryHash':sha256(d/'library.olb'),'device':devname,'partName':sym['partName'],'pins':pins,'reference':'U'+str(701+len(cases))})
(root/'expected.json').write_text(json.dumps({'existing':existing,'cases':cases},indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60']
for parent in sorted({str(Path(c['library']).parent) for c in cases}):args.extend(['--read-root',parent])
params=StdioServerParameters(command=sys.executable,args=args,env=env)
async def main():
 report={'passed':False,'scope':'source/cached/actual instance typed geometry/style/font/order identity; not rendered appearance or arbitrary vector creation','cases':[]};keys=[];lastgood=None
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   ts=(await client.list_tools()).tools;assert len(ts)==143;(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8');sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId'];page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'] if p['name']=='MCP_PLACE')
   for case in cases:
    row={'case':case['name'],'passed':False};report['cases'].append(row)
    try:
     lid=(await call('capture_library_open',{'sourceLibrary':case['library']}))['libraryId'];dev=next(d for d in (await call('capture_library_query',{'libraryId':lid,'entity':'device','limit':1000}))['items'] if d['designator']==case['device']);part=next(p for p in (await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'] if p['deviceId']==dev['objectId'] and p['name']==case['partName']);arguments={'sessionId':sid,'pageId':page['objectId'],'libraryId':lid,'libraryPartId':part['objectId'],'reference':case['reference'],'location':[700,300],'value':'MCP_VECTOR','expectedPins':case['pins'],'expectedExistingConnections':existing};plan=await call('capture_plan_placement',arguments);row['plan']=plan;key={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_placement',{**key,'idempotencyKey':case['name']});assert result['sourceVectorGeometryVerified'];opened=await call('capture_open_edit_result',{**key,'kind':'placement'});compare=root/'work'/result['outputWorkspaceRelativePath']/'verified-view.json';view=json.loads(compare.read_text(encoding='utf-8'));assert view=={'matches':True,'pinCount':3,'lineCount':4,'vectorCount':5};row.update(result=result,opened=opened,viewComparison=view,passed=True);keys.append((case['name'],key));lastgood=(arguments,case)
    except BaseException as e:
     import traceback
     row.update(error=str(e),traceback=traceback.format_exc())
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(case['name'],row['passed'],row.get('error'),flush=True)
   if lastgood:
    arguments,case=lastgood;bad=[{**p,'hotSpot':[0,0]} for p in case['pins']];bp=await call('capture_plan_placement',{**arguments,'reference':'U899','expectedPins':bad});bk={k:bp[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_placement',{**bk,'idempotencyKey':'wrong-vector-hotspot'});assert v.is_error and v.structured_content['error']['code']=='placement_hotspot_mismatch';assert (await client.call_tool('capture_open_edit_result',{**bk,'kind':'placement'})).is_error;v=await client.call_tool('capture_apply_placement',{**bk,'idempotencyKey':'wrong-vector-hotspot'});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed';report['wrongOracleSavedButRefused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   for name,key in keys:
    v=await client.call_tool('capture_apply_placement',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_placement',key)).is_error;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'placement'})).is_error
   report['freshLifecycleNoReplay']=True
  report['sourceAndLibrariesUnchanged']=sha256(source)==before and all(sha256(Path(c['library']))==c['libraryHash'] for c in cases);report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=all(c['passed'] for c in report['cases']) and report['sourceAndLibrariesUnchanged'] and report['oracleUnchanged'] and bool(keys)
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
