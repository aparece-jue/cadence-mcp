"""Public MCP OLB creation/query with frozen field expectations and old-plan compatibility."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
source=a.source_root/'spec.json';source_hash=sha256(source);base=json.loads(source.read_text(encoding='utf-8'))
normal=next(s for s in base['symbols'] if s['partName'].endswith('.Normal'))
for s in base['symbols']:s['pins']=copy.deepcopy(normal['pins']);s['lines']=copy.deepcopy(normal['lines'])
vectors=[
 {'kind':'box','bounds':[-10,-8,10,8],'fill':2,'hatch':3,'style':1,'width':1},
 {'kind':'ellipse','bounds':[-9,-7,9,7],'fill':1,'hatch':0,'style':2,'width':0},
 {'kind':'line','start':[-11,0],'end':[11,0],'style':3,'width':2},
 {'kind':'arc','bounds':[-10,-10,10,10],'start':[10,0],'end':[0,-10],'style':0,'width':0},
 {'kind':'polygon','points':[[-8,5],[0,-6],[8,5]],'style':0,'width':0,'fill':0,'hatch':0},
 {'kind':'polyline','points':[[-8,5],[-8,-5],[8,-5],[8,5]],'style':0,'width':0},
 {'kind':'bezier','points':[[-8,5],[-4,-8],[4,8],[8,-5]],'style':0,'width':0},
 {'kind':'fill','start':[2,2],'fill':1,'hatch':0},
 {'kind':'text','text':'MCP PUBLIC VECTOR','bounds':[0,0,100,14]},
]
# Oracle arrays are declared separately; do not derive these from production canonicalization.
declared=[['box',[-10,-8,10,8],1,1,2,3],['ellipse',[-9,-7,9,7],2,0,1,0],
 ['line',[-11,0],[11,0],3,2],['arc',[-10,-10,10,10],[10,0],[0,-10],0,0],
 ['polygon',[[-8,5],[0,-6],[8,5]],0,0,0,0],['polyline',[[-8,5],[-8,-5],[8,-5],[8,5]],0,0],
 ['bezier',[[-8,5],[-4,-8],[4,8],[8,-5]],0,0],['fill',[2,2],1,0],
 ['text','MCP PUBLIC VECTOR',[0,0],[0,0,100,14],['Arial',-11,0,0,0,400,0,0,0,0,7,0,1,16]]]
mixed=copy.deepcopy(base);expected={}
for s in mixed['symbols']:
 is_alt=s['partName'].endswith('.Convert');vs=copy.deepcopy(vectors);want=copy.deepcopy(declared)
 if is_alt:
  vs.reverse();want.reverse();font={'faceName':'Arial','height':-11,'weight':700,'escapement':900,'orientation':900,'italic':True,'underline':True}
  next(v for v in vs if v['kind']=='text')['font']=font
  want[0][4]=['Arial',-11,0,900,900,700,1,1,0,0,7,0,1,16]
 s['vectors']=vs
 expected[s['partName']]=[['line',l['start'],l['end'],l['style'],l['width']] for l in s['lines']]+want
only_line=copy.deepcopy(base)
for s in only_line['symbols']:s['vectors']=[copy.deepcopy(vectors[2])]
specs={'mixed':mixed,'typed_line':only_line,'legacy':base}
(root/'declared-specs.json').write_text(json.dumps(specs,indent=2),encoding='utf-8')
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(root),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,(name,v.content);return v.structured_content['data']
   tools=(await client.list_tools()).tools;assert len(tools)==144
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
   for label,spec in specs.items():
    row={'case':label,'passed':False};report['cases'].append(row)
    plan=await call('capture_plan_library_create',{'spec':spec});key={k:plan[k] for k in ('planId','planDigest')};row['plan']=plan
    result=await call('capture_apply_library_create',{**key,'idempotencyKey':label});row['result']=result
    opened=await call('capture_open_created_library',key);lid=opened['libraryId'];row['opened']=opened
    parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'];assert len(parts)==4
    observed=[]
    for part in parts:
     args={'libraryId':lid,'partId':part['objectId'],'limit':3};page=await call('capture_query_library_vectors',args);items=list(page['items'])
     if page['nextCursor']:
      wrong=await client.call_tool('capture_query_library_vectors',{**args,'limit':2,'cursor':page['nextCursor']})
      assert wrong.is_error and wrong.structured_content['error']['code']=='stale_cursor'
     while page['nextCursor']:
      page=await call('capture_query_library_vectors',{**args,'cursor':page['nextCursor']});items.extend(page['items'])
     actual=[v['descriptor'][:-1] if v['kind']=='text' else v['descriptor'] for v in items]
     legacy=[['line',l['start'],l['end'],l['style'],l['width']] for l in normal['lines']]
     wanted=expected[part['name']] if label=='mixed' else legacy+([declared[2]] if label=='typed_line' else [])
     assert actual==wanted,(label,part['name'],actual,wanted)
     assert [v['index'] for v in items]==list(range(len(items)))
     assert len({v['objectId'] for v in items})==len(items)
     assert page['order']=='native_draw_order' and page['renderedAppearanceVerified'] is False
     observed.append({'partId':part['objectId'],'name':part['name'],'vectors':items})
    bad=await client.call_tool('capture_query_library_vectors',{'libraryId':lid,'partId':'not-in-this-library'})
    assert bad.is_error and bad.structured_content['error']['code']=='object_not_found'
    await call('capture_library_close',{'libraryId':lid})
    bad=await client.call_tool('capture_query_library_vectors',{'libraryId':lid,'partId':parts[0]['objectId']})
    assert bad.is_error and bad.structured_content['error']['code']=='session_lost'
    row.update(passed=True,observed=observed,wrongPartAndClosedSessionRefused=True);keys.append((label,key))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(label,True,flush=True)
   bad=copy.deepcopy(mixed);bad['expectedHomogeneous']=False
   plan=await call('capture_plan_library_create',{'spec':bad});key={k:plan[k] for k in ('planId','planDigest')}
   v=await client.call_tool('capture_apply_library_create',{**key,'idempotencyKey':'wrong-oracle'})
   assert v.is_error and v.structured_content['error']['code']=='library_creation_mismatch'
   assert (await client.call_tool('capture_open_created_library',key)).is_error
   v=await client.call_tool('capture_apply_library_create',{**key,'idempotencyKey':'wrong-oracle'})
   assert v.is_error and v.structured_content['error']['code']=='write_not_replayed'
   report['wrongOracleSavedButRefused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   for label,key in keys:
    v=await client.call_tool('capture_apply_library_create',{**key,'idempotencyKey':label});assert not v.is_error and not v.structured_content['data']['mutationReplayed']
    assert not (await client.call_tool('capture_recover_library_create',key)).is_error
    assert not (await client.call_tool('capture_open_created_library',key)).is_error
   report['freshLifecycleNoReplay']=True
  report['sourceAndOracleUnchanged']=sha256(source)==source_hash and sha256(root/'expected.json')==oracle
  report['passed']=len(keys)==3 and report['sourceAndOracleUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)

