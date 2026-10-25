import argparse,asyncio,copy,hashlib,json,os,struct,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
from library_create_fixtures import specs
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);repo=Path(__file__).resolve().parents[1]
base=specs();one=copy.deepcopy(base['resistor']);two=copy.deepcopy(one);two.update(packageName='MCP_RES_QFN',footprint='QFN_CUSTOM_2');two['symbols'][0].update(cellName='RES_QFN_CELL',partName='RES_QFN.Normal');two['symbols'][0]['pins'][0]['name']='A中文[x]$;';two['devices'][0]['cellName']='RES_QFN_CELL';two['devices'][0]['mapping'][0]['number']='A1';two['devices'][0]['mapping'][1]['number']='A2'
cases={'two_footprints':{'packages':[one,two]},'dual_and_heterogeneous':{'packages':[base['homogeneous_shared'],base['heterogeneous_power']]},'old_single':base['resistor']}
pixels=bytes([3,8,20,255,45,70,90,255,100,120,130,255,160,180,200,255]);dib=struct.pack('<IiiHHIIiiII',40,2,2,1,32,0,16,0,0,0,0)+pixels;bmp=struct.pack('<2sIHHI',b'BM',70,0,0,54)+dib;asset=root/'family.bmp';asset.write_bytes(bmp)
mixed=copy.deepcopy(cases['two_footprints']);mixed['packages'][1]['symbols'][0]['vectors']=[{'kind':'ellipse','bounds':[-8,-6,8,6],'style':0,'width':0,'fill':1,'hatch':0},{'kind':'bitmap','bounds':[30,0,50,20],'location':[30,0],'sourceBmp':str(asset),'expectedDimensions':[2,2],'expectedDibSize':56,'expectedBmpSha256':hashlib.sha256(bmp).hexdigest(),'expectedDibSha256':hashlib.sha256(dib).hexdigest()}];cases['mixed_bitmap_and_plain']=mixed
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');oracle_hash=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(root),'--timeout-seconds','60'],env=env)
report={'passed':False,'fullL03Accepted':False,'cases':[],'checks':{}};keys=[]
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as c:
   schemas={t.name:t.output_schema for t in (await c.list_tools()).tools};report['toolCount']=len(schemas)
   async def call(name,args,error=None):
    response=await c.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content);return
    assert not response.is_error,(name,response.structured_content);return response.structured_content['data']
   for name,spec in cases.items():
    plan=await call('capture_plan_library_create',{'spec':spec});key={k:plan[k] for k in ('planId','planDigest')};keys.append((name,key))
    if name=='mixed_bitmap_and_plain':asset.unlink()
    try:result=await call('capture_apply_library_create',{**key,'idempotencyKey':name})
    finally:
     if name=='mixed_bitmap_and_plain':asset.write_bytes(bmp)
    opened=await call('capture_open_created_library',key);lib=opened['libraryId'];pkgs=spec.get('packages',[spec]);expected_pad_count=0
    for pkg in pkgs:
     data=await call('capture_library_query',{'libraryId':lib,'entity':'package','packageName':pkg['packageName'],'limit':1000});assert len(data['items'])==1 and data['items'][0]['footprint']==pkg['footprint']
     pins=(await call('capture_library_query',{'libraryId':lib,'entity':'pin','packageName':pkg['packageName'],'limit':1000}))['items'];expected=[]
     for dev in pkg['devices']:
      for symbol in pkg['symbols']:
       if symbol['cellName']!=dev['cellName']:continue
       geom={p['position']:p for p in symbol['pins']}
       for mapping in dev['mapping']:
        g=geom[mapping['position']];expected.append((mapping['position'],mapping['number'],g['name'],g['pinType'],g['visible'],mapping['shared'],mapping['swapId'],g['hotSpot']))
     actual=[(p['position'],p['number'],p['name'],p['pinType'],p['visible'],p['shared'],p['swapId'],p['hotSpot']) for p in pins];assert sorted(actual)==sorted(expected),(pkg['packageName'],actual,expected);expected_pad_count+=len({m['number'] for d in pkg['devices'] for m in d['mapping']})
    if name=='mixed_bitmap_and_plain':
     partrows=(await call('capture_library_query',{'libraryId':lib,'entity':'part','packageName':two['packageName'],'limit':1000}))['items'];assert len(partrows)==1
     vectorrows=(await call('capture_query_library_vectors',{'libraryId':lib,'partId':partrows[0]['objectId'],'limit':1000}))['items'];assert vectorrows[-1]['descriptor']==['bitmap',[30,0,50,20],[30,0],[2,2],56,hashlib.sha256(dib).hexdigest()];assert vectorrows[-2]['kind']=='ellipse';report['checks']['family_bitmap_frozen_bytes_and_mixed_vector_order']=True
    assert result['uniquePhysicalPadCount']==expected_pad_count;report['cases'].append({'name':name,'plan':plan,'result':result,'passed':True});await call('capture_library_close',{'libraryId':lib})
   report['checks']['native_reopen_package_scoped_maps_and_footprints']=True
   bad=copy.deepcopy(cases['two_footprints']);bad['packages'][1]['packageName']=bad['packages'][0]['packageName'].lower();await call('capture_plan_library_create',{'spec':bad},'invalid_library_spec')
   bad=copy.deepcopy(cases['two_footprints']);bad['packages'][1]['expectedHomogeneous']=False;plan=await call('capture_plan_library_create',{'spec':bad});key={k:plan[k] for k in ('planId','planDigest')};await call('capture_apply_library_create',{**key,'idempotencyKey':'wrong-oracle'},'library_creation_mismatch');await call('capture_open_created_library',key,'output_unverified');report['checks']['wrong_package_oracle_and_conflicting_names_refused']=True
   plan=await call('capture_plan_library_create',{'spec':cases['two_footprints']});key={k:plan[k] for k in ('planId','planDigest')};await call('capture_cancel_library_create',key);response=await c.call_tool('capture_apply_library_create',{**key,'idempotencyKey':'cancel'});assert response.is_error;report['checks']['pending_cancel']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for name,key in keys:
    response=await fresh.call_tool('capture_apply_library_create',{**key,'idempotencyKey':name});assert not response.is_error and response.structured_content['data']['mutationReplayed'] is False
    response=await fresh.call_tool('capture_open_created_library',key);assert not response.is_error
   report['checks']['fresh_server_no_replay_and_reopen']=True
   name,key=keys[0];target=root/'work/isolated-jobs/capture_library_create'/('plan-'+key['planId'])/'library.olb';(root/'valid-first-output.olb').write_bytes(target.read_bytes());target.write_bytes(target.read_bytes()+b'owned terminal tamper')
   for method,args in [('capture_open_created_library',key),('capture_apply_library_create',{**key,'idempotencyKey':name}),('capture_recover_library_create',key)]:
    response=await fresh.call_tool(method,args);assert response.is_error and response.structured_content['error']['code']=='target_changed',response.structured_content
   report['checks']['terminal_hash_tamper_refused']=True
  report['checks']['oracle_unchanged']=oracle_hash==sha256(root/'expected.json');report['passed']=all(report['checks'].values())
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')},ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
