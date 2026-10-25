"""Real MCP update/delete matrix with separately frozen descriptor expectations."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','library-root','oracle-path'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--kinds',nargs='+',choices=('line','box','ellipse','arc','polygon','polyline','bezier','fill','text'))
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=(a.library_root/'library.olb').resolve(strict=True);source_hash=sha256(source)
old=json.loads(a.oracle_path.read_text(encoding='utf-8'));normal=next(k for k in old if k.endswith('.Normal'))
replacements={
 'line':({'kind':'line','start':[-15,3],'end':[15,3],'style':1,'width':2},['line',[-15,3],[15,3],1,2]),
 'box':({'kind':'box','bounds':[-12,-9,12,9],'style':2,'width':1,'fill':2,'hatch':4},['box',[-12,-9,12,9],2,1,2,4]),
 'ellipse':({'kind':'ellipse','bounds':[-16,-6,16,6],'style':4,'width':2,'fill':2,'hatch':2},['ellipse',[-16,-6,16,6],4,2,2,2]),
 'arc':({'kind':'arc','bounds':[-12,-12,12,12],'start':[12,0],'end':[-12,0],'style':1,'width':1},['arc',[-12,-12,12,12],[12,0],[-12,0],1,1]),
 'polygon':({'kind':'polygon','points':[[-9,6],[-2,-7],[3,-8],[9,6]],'style':1,'width':2,'fill':2,'hatch':1},['polygon',[[-9,6],[-2,-7],[3,-8],[9,6]],1,2,2,1]),
 'polyline':({'kind':'polyline','points':[[-12,8],[0,-8],[12,8]],'style':3,'width':1},['polyline',[[-12,8],[0,-8],[12,8]],3,1]),
 'bezier':({'kind':'bezier','points':[[-12,9],[-6,-9],[6,9],[12,-9]],'style':2,'width':2},['bezier',[[-12,9],[-6,-9],[6,9],[12,-9]],2,2]),
 'fill':({'kind':'fill','start':[-2,3],'fill':2,'hatch':5},['fill',[-2,3],2,5]),
 'text':({'kind':'text','text':'更新 Ω $[x];\nSecond line','bounds':[1,2,160,40],
          'font':{'faceName':'Arial','height':-13,'weight':600,'italic':True,'strikeOut':True,'escapement':900,'orientation':900}},
         ['text','更新 Ω $[x];\nSecond line',[1,2],[1,2,160,40],['Arial',-13,0,900,900,600,1,0,1,0,7,0,1,16]])}
cases=[]
for kind in (a.kinds or replacements):
 index=next(i for i,v in enumerate(old[normal]) if v[0]==kind)
 for operation in ('update','delete'):
  expected=copy.deepcopy(old)
  if operation=='update':expected[normal][index]=copy.deepcopy(replacements[kind][1])
  else:expected[normal].pop(index)
  cases.append({'name':kind+'-'+operation,'kind':kind,'index':index,'operation':operation,
                'replacement':replacements[kind][0] if operation=='update' else None,'expected':expected})
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');oracle_hash=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'scope':'nine basic native vector classes; modeled definitions/graphics/template/pin-start preservation, not all library properties or rendering','cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.content);return r.structured_content['data']
   ts=(await client.list_tools()).tools;assert len(ts)==149
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   lid=(await call('capture_library_open',{'sourceLibrary':str(source)}))['libraryId']
   parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items']
   devices=(await call('capture_library_query',{'libraryId':lid,'entity':'device','limit':1000}))['items']
   dev=next(d for d in devices if d['designator']=='A');part=next(p for p in parts if p['deviceId']==dev['objectId'] and p['name']==normal)
   vectors=(await call('capture_query_library_vectors',{'libraryId':lid,'partId':part['objectId'],'limit':1000}))['items']
   before=[v['descriptor'][:-1] if v['kind']=='text' else v['descriptor'] for v in vectors];assert before==old[normal]
   for case in cases:
    row={'case':case['name'],'passed':False};report['cases'].append(row);opened_id=None
    try:
     arguments={'libraryId':lid,'partId':part['objectId'],'vectorId':vectors[case['index']]['objectId'],
        'operation':case['operation'],'replacement':case['replacement']}
     plan=await call('capture_plan_library_vector_edit',arguments);row['plan']=plan
     assert len(plan['preview']['affectedScopes'])==2
     key={k:plan[k] for k in ('planId','planDigest')}
     result=await call('capture_apply_library_vector_edit',{**key,'idempotencyKey':case['name']});row['result']=result
     assert result['declaredVectorEditVerified'] and result['modeledLibraryPreservationVerified']
     opened=await call('capture_open_edited_library',{**key,'kind':'vector'});opened_id=opened['libraryId'];row['opened']=opened
     saved_parts=(await call('capture_library_query',{'libraryId':opened_id,'entity':'part','limit':1000}))['items'];assert len(saved_parts)==4
     observed=[]
     for saved_part in saved_parts:
      response=await call('capture_query_library_vectors',{'libraryId':opened_id,'partId':saved_part['objectId'],'limit':1000})
      items=response['items'];actual=[v['descriptor'][:-1] if v['kind']=='text' else v['descriptor'] for v in items]
      assert actual==case['expected'][saved_part['name']],(case['name'],saved_part['name'],actual)
      observed.append({'partId':saved_part['objectId'],'name':saved_part['name'],'vectors':items})
     row.update(passed=True,observed=observed);keys.append((case['name'],key))
    except BaseException as e:
     import traceback
     row.update(error=str(e),traceback=traceback.format_exc())
    finally:
     if opened_id:await call('capture_library_close',{'libraryId':opened_id})
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(case['name'],row['passed'],row.get('error'),flush=True)
   initial=(await call('capture_library_vector_edit_jobs',{}))['total']
   for name,args,code in [
    ('wrong-owner',{'libraryId':lid,'partId':part['objectId'],'vectorId':'foreign/vector-1','operation':'delete'},'object_not_found'),
    ('kind-change',{'libraryId':lid,'partId':part['objectId'],'vectorId':next(v for v in vectors if v['kind']=='box')['objectId'],'operation':'update','replacement':replacements['line'][0]},'vector_kind_change'),
    ('delete-replacement',{'libraryId':lid,'partId':part['objectId'],'vectorId':vectors[0]['objectId'],'operation':'delete','replacement':replacements['line'][0]},'invalid_vector_edit')]:
    v=await client.call_tool('capture_plan_library_vector_edit',args);assert v.is_error and v.structured_content['error']['code']==code,(name,v.content)
   assert (await call('capture_library_vector_edit_jobs',{}))['total']==initial;report['invalidPlansCreateNoDurableJobs']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for name,key in keys:
    v=await fresh.call_tool('capture_apply_library_vector_edit',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed']
    assert not (await fresh.call_tool('capture_recover_library_vector_edit',key)).is_error
    v=await fresh.call_tool('capture_open_edited_library',{**key,'kind':'vector'});assert not v.is_error
    assert not (await fresh.call_tool('capture_library_close',{'libraryId':v.structured_content['data']['libraryId']})).is_error
   report['freshLifecycleNoReplay']=True
  report['sourceAndOracleUnchanged']=sha256(source)==source_hash and sha256(root/'expected.json')==oracle_hash
  report['passed']=len(keys)==len(cases) and report['sourceAndOracleUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
