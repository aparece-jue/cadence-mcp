"""Independent declared geometry/style oracles for native non-line alternate views."""
import argparse,copy,json
from pathlib import Path
from cadence_mcp.core import Config,write_json,sha256
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-root'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--kinds',nargs='+',choices=('box','ellipse','arc','polygon','polyline','bezier','fill','text'))
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),60);source=a.source_root/'spec.json';source_hash=sha256(source);original=json.loads(source.read_text(encoding='utf-8'));normal=next(s for s in original['symbols'] if s['partName'].endswith('.Normal'));report={'passed':False,'scope':'declared native vector fields, not rendered layout or public vector creation','cases':[]}
def vector(kind,index):
 k=index;result={'kind':kind,'style':0,'width':0}
 if kind in ('box','ellipse'):result.update(bounds=[-10+2*k,-8+2*k,10-2*k,8-2*k],fill=0,hatch=0)
 elif kind=='arc':result.update(bounds=[-10+2*k,-10+2*k,10-2*k,10-2*k],start=[10-2*k,0],end=[0,-10+2*k])
 elif kind=='polygon':result.update(points=[[-8+k,5-k],[0,-6+k],[8-k,5-k]],fill=0,hatch=0)
 elif kind=='polyline':result.update(points=[[-8+k,5-k],[-8+k,-5+k],[8-k,-5+k],[8-k,5-k]])
 elif kind=='bezier':result.update(points=[[-8+k,5-k],[-4+k,-8+k],[4-k,8-k],[8-k,-5+k]])
 elif kind=='fill':result.update(start=[2*k,2*k],fill=1,hatch=0)
 elif kind=='text':result.update(text='MCP VECTOR '+str(k),location=[0,0],bounds=[0,0,40,14],font=['Arial',-11,0,900*k,900*k,400+300*k,0,0,0,0,7,0,1,16])
 return result
def descriptor(v):
 kind=v['kind']
 if kind in ('box','ellipse'):return [kind,v['bounds'],v['style'],v['width'],v['fill'],v['hatch']]
 if kind=='arc':return [kind,v['bounds'],v['start'],v['end'],v['style'],v['width']]
 if kind in ('polygon','polyline','bezier'):return [kind,v['points'],v['style'],v['width']]+([v['fill'],v['hatch']] if kind=='polygon' else [])
 if kind=='fill':return [kind,v['start'],v['fill'],v['hatch']]
 return [kind,v['text'],v['location'],v['bounds'],v['font'],0]
def stable(rows):return sorted(rows,key=lambda p:json.dumps(p,sort_keys=True))
for kind in (a.kinds or ('box','ellipse','arc','polygon','polyline','bezier','fill','text')):
 d=root/kind;d.mkdir();spec=copy.deepcopy(original)
 for sym in spec['symbols']:sym['pins']=copy.deepcopy(normal['pins']);sym['lines']=copy.deepcopy(normal['lines'])
 write_json(d/'spec.json',spec);additions=[{'partName':s['partName'],'vectors':[vector(kind,int(s['partName'].endswith('.Convert')))]} for s in spec['symbols']];request={'packageName':spec['packageName'],'designator':'A','additions':additions};write_json(d/'request.json',request);expected={s['partName']:[['line',l['start'],l['end'],l['style'],l['width']] for l in s['lines']]+[descriptor(addition['vectors'][0])] for s,addition in zip(spec['symbols'],additions)};write_json(d/'expected.json',expected);row={'case':kind,'passed':False};report['cases'].append(row)
 try:
  row['createProcess']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'create_library.tcl'),str(cfg.install_root),str(d/'spec.json'),str(d/'library.olb'),str(d/'base-receipt.json')],d,process_env(cfg),60);assert row['createProcess']['returnCode']==0
  row['appendProcess']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_append_vectors.tcl'),str(cfg.install_root),str(d/'library.olb'),str(d/'request.json'),str(d/'receipt.json')],d,process_env(cfg),60);row['receipt']=json.loads((d/'receipt.json').read_text(encoding='utf-8'));assert row['appendProcess']['returnCode']==0 and row['receipt']['saved'];saved=sha256(d/'library.olb');run_tcl(cfg,'inspect_library_vectors.tcl',[str(d/'library.olb'),str(d/'actual.json')],d);actual=json.loads((d/'actual.json').read_text(encoding='utf-8'));row['declaredVectorFieldsMatch']=len(actual)==4 and all(stable(v['vectors'])==stable(expected[v['partName']]) for v in actual);row['distinctViewSignatures']=len({v['signature'] for v in actual if v['designator']=='A'})==2;row['sourceAndOutputUnchanged']=sha256(source)==source_hash and sha256(d/'library.olb')==saved;row['savedSha256']=saved;row['passed']=row['declaredVectorFieldsMatch'] and row['distinctViewSignatures'] and row['sourceAndOutputUnchanged'] and row['createProcess']['remainingOwnedProcesses']==0 and row['appendProcess']['remainingOwnedProcesses']==0
 except BaseException as e:
  import traceback
  row.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(kind,row['passed'],row.get('error'),row.get('receipt'),flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(0 if report['passed'] else 1)


