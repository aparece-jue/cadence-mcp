"""Rebuild the entire original40 object matrix via existing typed editor wire jobs."""
import asyncio,json,os,sys,traceback,shutil
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
r=Path(r'D:\workspace\git\cadence-mcp');base=r/'.local/c04-editor-matrix-base-20261027';root=r/'.local/c04-editor-matrix-build-mcp-20261027';root.mkdir(exist_ok=False);fixture=r/'.local/c04-editor-matrix-final-20261027';fixture.mkdir(exist_ok=False)
calibration=r/'.local/net-symbol-frame-calibration-20261027';proof=json.loads((calibration/'report.json').read_text(encoding='utf-8'));assert proof['passed'] and proof['positiveAttachments']==16 and proof['negativeOldHypothesisPoints']==12
source=base/'design.dsn';before=sha256(source);original=base/'expected.json';original_hash=sha256(original);assert original_hash=='d31c2041a595af1fb15e8af5813febf04376a0ba612bf8016c8651ebabcd4560';shutil.copy2(original,fixture/'expected-original-hypothesis.json')
expected=json.loads(original.read_text(encoding='utf-8'));defs=json.loads((calibration/'expected.json').read_text(encoding='utf-8'))['definitionsFromIndependentOlb'];by_kind={d['kind']:d for d in defs};changes=[]
def rotate(pt,rotation,mirror):
 x,y=pt
 if mirror:x=-x
 return ((x,y),(y,-x),(-x,-y),(-y,x))[rotation]
for item in expected['objects']:
 if item['kind'] not in by_kind:continue
 attr=item['attributes'];d=by_kind[item['kind']];left,top,right,bottom=d['bounds'];rotation=attr['rotationCode'];mirror=attr['mirrorCode'];corners=[rotate((x,y),rotation,mirror) for x in (left,right) for y in (top,bottom)];pin=rotate(d['pins'][0],rotation,mirror);hot=[attr['location'][i]+pin[i]-min(c[i] for c in corners) for i in (0,1)]
 if attr['hotSpot']!=hot:changes.append({'pageName':item['pageName'],'kind':item['kind'],'location':attr['location'],'oldHypothesis':attr['hotSpot'],'sourceGeometryPrediction':hot})
 attr['hotSpot']=hot
assert len(changes)==24
expected['poseHypothesis']='Independent source-library box/pin transform, rebased by transformed box minimum; validated separately by16native attachments and12old-hypothesis nonattachments. No instance readout enters oracle.'
(fixture/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle_hash=sha256(fixture/'expected.json')
(fixture/'oracle-provenance.json').write_text(json.dumps({'originalHypothesisSha256':original_hash,'sourceLibrarySha256':sha256(base/'library.olb'),'electricalCalibrationReportSha256':sha256(calibration/'report.json'),'definitions':defs,'changes':changes},indent=2),encoding='utf-8')
project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';bindings=r/'.local/editor-wire-fresh-binding-20261027';env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(base),'--read-root',str(project.parent),'--gui-bridge-root',str(bindings),'--timeout-seconds','30'],env=env)
def files():return {p.relative_to(root/'work').as_posix():sha256(p) for p in (root/'work').rglob('*') if p.is_file()}
async def main():
 report={'passed':False,'sourceBefore':before,'originalHypothesisPreservedSha256':original_hash,'newOracleSha256':oracle_hash,'steps':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    res=await client.call_tool(name,args);assert not res.is_error,res.structured_content or res.content;return res.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   for page_name in ('PAGE_A','PAGE_B'):
    for y in (800,900):
     instance=(await call('capture_gui_instances',{}))['instances'][0];gui=(await call('capture_gui_attach',{'instanceId':instance['instanceId']}))['sessionId'];page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']==page_name)
     plan=await call('capture_plan_wire_add',{'sessionId':sid,'pageId':page['objectId'],'start':[100,y],'end':[200,y],'netName':'LOCAL_DUP','aliasLocation':[140,y],'expectedConnections':[],'guiSessionId':gui,'hostProject':str(project)})
     key={k:plan[k] for k in ('planId','planDigest')};keyname=page_name+'-'+str(y);keys.append((key,keyname));result=await call('capture_apply_wire_add',{**key,'idempotencyKey':keyname});assert result['outputProjectCloseVerified'] and result['expectedConnectionObjectsVerified']
     sid=(await call('capture_open_edit_result',{**key,'kind':'wire_add'}))['sessionId'];report['steps'].append({'page':page_name,'y':y,'key':key,'result':result});print(json.dumps({'page':page_name,'wireY':y,'verified':True}),flush=True)
   target=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn';shutil.copy2(target,fixture/'design.dsn');report['matrixSha256']=sha256(target)
  frozen=files()
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   for key,keyname in keys:
    for name,args in [('capture_apply_wire_add',{**key,'idempotencyKey':keyname}),('capture_recover_wire_add',key)]:
     res=await client.call_tool(name,args);assert not res.is_error,res.structured_content;assert not res.structured_content['data']['mutationReplayed']
  assert files()==frozen;report.update(passed=True,fourPublicMcpWireAliasAddsAccepted=True,freshServiceNoReplayAndAllFilesUnchanged=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['originalHypothesisUnchanged']=sha256(original)==original_hash and sha256(fixture/'expected-original-hypothesis.json')==original_hash;report['newOracleUnchanged']=sha256(fixture/'expected.json')==oracle_hash;report['passed']=report['passed'] and report['sourceUnchanged'] and report['originalHypothesisUnchanged'] and report['newOracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='steps'}),flush=True)
asyncio.run(main())
