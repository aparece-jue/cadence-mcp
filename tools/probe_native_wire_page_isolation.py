"""Predeclared V02 multi-page native isolation matrix, no real design writes."""
import json,traceback
from pathlib import Path
from native_editor_probe import run_fixed_probe
from cadence_mcp.core import sha256
from cadence_mcp.environment import run_tcl
r=Path(__file__).resolve().parents[1]
source=r/'.local/editor-hierarchy-scaffold-20261027/design.dsn'
assert sha256(source)=='2ff1dc68ff7197b750e48733b95aaa7ae33d92f653d66fc5c242d3d824c0ee3f'
matrix={'TOP':{'page':'MAIN','segments':[[[100,100],[200,200]],[[100,500],[200,500]],[[150,450],[150,550]]]},
        'CHILD':{'page':'CHILD_PAGE','segments':[[[100,200],[200,100]],[[100,500],[200,500]],[[150,450],[150,550]]]}}
original=sha256(source);roots=[];report={'passed':False,'fullV02Accepted':False,'sourceBefore':original,'stages':[]}
root=r/'.local/native-wire-page-isolation-20261027';root.mkdir(exist_ok=False)
(root/'expected.json').write_text(json.dumps({'matrix':matrix,'perPageCrossings':1,'totalCrossings':2,'crossPageDiagonalCrossings':0,'sameCoordinatesStayPageScoped':True},indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
try:
 for name,case in matrix.items():
  stage=root/name;commands=['   set phase native_page_wires']
  for a,b in case['segments']:commands.extend(['   PlaceWire '+' '.join(str(v/100) for v in a+b),'   EndPlace'])
  cfg,d,dispatch=run_fixed_probe(stage,source,name,case['page'],'\n'.join(commands),case)
  report['stages'].append(dispatch);assert dispatch['nativeAccepted'],dispatch.get('error')
  source=d/'design.dsn';roots.append(stage)
 saved=sha256(source)
 run_tcl(cfg,'inspect.tcl',[str(source),str(root/'definitions.json'),'100000'],root)
 run_tcl(cfg,'inspect_geometry.tcl',[str(source),str(root/'geometry.json'),'100000'],root)
 data=json.loads((root/'geometry.json').read_text(encoding='utf-8'));names={x['objectId']:x['name'] for x in data['page']}
 assert set(names.values())=={'MAIN','CHILD_PAGE'} and len(data['wire'])==6
 canonical=lambda paths:sorted(tuple(sorted((tuple(a),tuple(b)))) for path in paths for a,b in zip(path,path[1:]))
 for case in matrix.values():
  wires=[w['points'] for w in data['wire'] if names[w['pageId']]==case['page']]
  assert canonical(wires)==canonical(case['segments']),case['page']
 assert sha256(source)==saved
 report.update(passed=True,target=str(source),targetSha256=saved,independentNativeGeometryVerified=True)
except BaseException:report['error']=traceback.format_exc()
report['sourceUnchanged']=sha256(r/'.local/editor-hierarchy-scaffold-20261027/design.dsn')==original
report['oracleUnchanged']=sha256(root/'expected.json')==oracle
report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:report.get(k) for k in ('passed','target','error')}),flush=True)
