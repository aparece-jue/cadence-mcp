"""Real MCP terminal-bitmap pixel replacement with full DIB and untouched-view checks."""
import argparse,asyncio,copy,hashlib,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

async def run(a,root,report):
 prior=a.fixture_root;old=json.loads((prior/'expected.json').read_text(encoding='utf8'));history=json.loads((prior/'report.json').read_text(encoding='utf8'));params=StdioServerParameters(command=sys.executable,args=['-B','-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(prior),'--timeout-seconds','60'],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')});keys=[];sources={prior/'expected.json':sha256(prior/'expected.json')}
 async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
  async def call(name,args):
   r=await client.call_tool(name,args);assert not r.is_error,r.structured_content;return r.structured_content['data']
  for source_name,dest_name in [('rgb24','rgb32'),('rgb32','rgb24')]:
   previous=next(c for c in history['cases'] if c['name']==source_name);source=prior/'work/isolated-jobs/capture_library_create'/('plan-'+previous['plan']['planId'])/'library.olb';assert sha256(source)==previous['result']['artifact']['sha256'];sources[source]=sha256(source)
   dest=next(c for c in old if c['name']==dest_name);replacement=copy.deepcopy(next(v for s in dest['spec']['symbols'] if s['partName']=='GATE.Normal' for v in s['vectors'] if v['kind']=='bitmap'));replacement['sourceBmp']=dest['source'];bmp=Path(dest['source']);blob=bmp.read_bytes();assert hashlib.sha256(blob[14:]).hexdigest()==replacement['expectedDibSha256'];sources[bmp]=sha256(bmp)
   lid=(await call('capture_library_open',{'sourceLibrary':str(source)}))['libraryId'];parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'];before={}
   for part in parts:before[part['objectId']]=(await call('capture_query_library_vectors',{'libraryId':lid,'partId':part['objectId'],'limit':1000}))['items']
   part=next(p for p in parts if p['name']=='GATE.Normal');target=before[part['objectId']][-1];assert target['kind']=='bitmap'
   args={'libraryId':lid,'partId':part['objectId'],'vectorId':target['objectId'],'operation':'update','replacement':replacement};plan=await call('capture_plan_library_vector_edit',args);key={k:plan[k] for k in ('planId','planDigest')};assert len(plan['preview']['affectedScopes'])==2
   asset=Path(plan['preview']['replacement']['sourceBmp']);asset_hash=sha256(asset);asset_bytes=asset.read_bytes();asset.write_bytes(b'bad frozen asset')
   try:
    bad=await client.call_tool('capture_apply_library_vector_edit',{**key,'idempotencyKey':source_name});assert bad.is_error
   finally:asset.write_bytes(asset_bytes)
   assert sha256(asset)==asset_hash
   result=await call('capture_apply_library_vector_edit',{**key,'idempotencyKey':source_name});assert result['declaredVectorEditVerified'] and result['modeledLibraryPreservationVerified'];out=(await call('capture_open_edited_library',{**key,'kind':'vector'}))['libraryId'];saved=(await call('capture_library_query',{'libraryId':out,'entity':'part','limit':1000}))['items']
   expected=['bitmap',replacement['bounds'],replacement['location'],replacement['expectedDimensions'],len(blob)-14,hashlib.sha256(blob[14:]).hexdigest()]
   for prior_part in parts:
    new_part=next(p for p in saved if p['objectId']==prior_part['objectId']);rows=(await call('capture_query_library_vectors',{'libraryId':out,'partId':new_part['objectId'],'limit':1000}))['items'];want=[copy.deepcopy(v['descriptor']) for v in before[prior_part['objectId']]]
    if prior_part['name']=='GATE.Normal':want[-1]=expected
    assert [v['descriptor'] for v in rows]==want
   cancel=await call('capture_plan_library_vector_edit',args);await call('capture_cancel_library_vector_edit',{k:cancel[k] for k in ('planId','planDigest')})
   bad_args=copy.deepcopy(args);bad_args['replacement']['expectedBmpSha256']='0'*64;bad=await client.call_tool('capture_plan_library_vector_edit',bad_args);assert bad.is_error
   job=root/'work'/result['outputWorkspaceRelativePath'];hashes={p:sha256(p) for p in job.rglob('*.olb')};keys.append((source_name,key,hashes));report['cases'].append({'source':source_name,'replacement':dest_name,'passed':True,'plan':key,'result':result,'expectedDescriptor':expected,'allViewsAndDrawOrderMatched':True,'frozenAssetTamperRefused':True,'invalidAssetRefused':True,'cancelledBeforeApply':True});await call('capture_library_close',{'libraryId':lid});await call('capture_library_close',{'libraryId':out});print(json.dumps({'case':source_name,'passed':True}),flush=True)
 async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
  for name,key,hashes in keys:
   for tool,args in [('capture_apply_library_vector_edit',{**key,'idempotencyKey':name}),('capture_recover_library_vector_edit',key)]:
    r=await fresh.call_tool(tool,args);assert not r.is_error,r.structured_content
    if tool=='capture_apply_library_vector_edit':assert not r.structured_content['data']['mutationReplayed']
   assert all(sha256(p)==h for p,h in hashes.items())
 report['freshRecoveryNoReplay']=True;report['originalInputsUnchanged']=all(sha256(p)==h for p,h in sources.items());report['inputSha256']={str(p):h for p,h in sources.items()};assert report['originalInputsUnchanged']

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('install-root','fixture-root','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();a.fixture_root=a.fixture_root.resolve();root=a.output.resolve();root.mkdir(exist_ok=False);report={'passed':False,'fullL02Accepted':False,'cases':[]}
 try:asyncio.run(run(a,root,report));report['passed']=True
 finally:(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
