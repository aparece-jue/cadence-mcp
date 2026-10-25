"""Actual MCP declared RGB24/RGB32 bitmap creation and independently frozen byte oracles."""
import argparse,asyncio,copy,hashlib,json,os,struct,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','base-spec','source-bmp'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
base=json.loads(a.base_spec.read_text(encoding='utf-8'));source_hash=sha256(a.base_spec);image_hash=sha256(a.source_bmp)
rgb24=a.source_bmp.read_bytes();pixels=bytes([3,8,20,255,45,70,90,255,100,120,130,255,160,180,200,255])
dib32=struct.pack('<IiiHHIIiiII',40,2,2,1,32,0,16,0,0,0,0)+pixels
rgb32=struct.pack('<2sIHHI',b'BM',70,0,0,54)+dib32
images={'rgb24':rgb24,'rgb32':rgb32};cases=[]
for label,blob in images.items():
    path=root/(label+'.bmp');path.write_bytes(blob)
    spec=copy.deepcopy(base);expected=[]
    for index,symbol in enumerate(spec['symbols']):
        bounds=[index*30,0,index*30+20,20];location=bounds[:2]
        vector={'kind':'bitmap','bounds':bounds,'location':location,'sourceBmp':str(path),
                'expectedDimensions':[2,2],'expectedDibSize':56,
                'expectedBmpSha256':hashlib.sha256(blob).hexdigest(),'expectedDibSha256':hashlib.sha256(blob[14:]).hexdigest()}
        symbol.setdefault('vectors',[]).append(vector)
        expected.append({'partName':symbol['partName'],'descriptor':['bitmap',bounds,location,[2,2],56,vector['expectedDibSha256']]})
    cases.append({'name':label,'spec':spec,'expected':expected,'source':str(path)})
cases.append({'name':'legacy','spec':base,'expected':[]})
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(root),'--timeout-seconds','60'],env=os.environ.copy())
async def main():
    report={'passed':False,'scope':'declared frozen BI_RGB24/32 BMP creation, not replacement/rendering/all BMP formats','cases':[]};keys=[]
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
            async def call(name,args):
                value=await client.call_tool(name,args);assert not value.is_error,(name,value.structured_content)
                return value.structured_content['data']
            assert len((await client.list_tools()).tools)==155
            for case in cases:
                row={'name':case['name'],'passed':False};report['cases'].append(row)
                try:
                    plan=await call('capture_plan_library_create',{'spec':case['spec']});row['plan']=plan
                    key={k:plan[k] for k in ('planId','planDigest')}
                    original=Path(case['source']) if 'source' in case else None
                    retained=original.read_bytes() if original else None
                    if original:original.unlink()
                    try:result=await call('capture_apply_library_create',{**key,'idempotencyKey':case['name']})
                    finally:
                        if original:original.write_bytes(retained)
                    row['result']=result;assert result['declaredGraphVerified'] and result['independentReopenVerified']
                    opened=await call('capture_open_created_library',key);row['opened']=opened
                    parts=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'part','limit':1000}))['items']
                    observed=[]
                    for part in parts:
                        items=(await call('capture_query_library_vectors',{'libraryId':opened['libraryId'],'partId':part['objectId'],'limit':1000}))['items']
                        bitmap=[v['descriptor'] for v in items if v['kind']=='bitmap']
                        wanted=[v['descriptor'] for v in case['expected'] if v['partName']==part['name']]
                        assert bitmap==wanted,(part['name'],bitmap,wanted)
                        observed.append({'partName':part['name'],'bitmaps':bitmap,'vectorCount':len(items)})
                    assert len(parts)==4
                    row.update(passed=True,observed=observed,originalImageAbsentDuringNativeCreate=bool(original))
                    keys.append((case['name'],key))
                except BaseException as error:
                    import traceback
                    row.update(error=str(error),traceback=traceback.format_exc())
                print(case['name'],row['passed'],row.get('error'),flush=True)
        async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
            for name,key in keys:
                value=await client.call_tool('capture_apply_library_create',{**key,'idempotencyKey':name})
                assert not value.is_error and value.structured_content['data']['mutationReplayed'] is False
                assert not (await client.call_tool('capture_recover_library_create',key)).is_error
                assert not (await client.call_tool('capture_open_created_library',key)).is_error
            report['fresh_lifecycle_no_replay']=True
        report['sources_and_oracle_unchanged']=sha256(a.base_spec)==source_hash and sha256(a.source_bmp)==image_hash and sha256(root/'expected.json')==oracle
        report['passed']=len(keys)==len(cases) and report['sources_and_oracle_unchanged']
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
