"""Fixed original V02 diagonal matrix on an owned native Capture copy."""
import json, traceback
from pathlib import Path
from native_editor_probe import run_fixed_probe
from cadence_mcp.core import sha256
from cadence_mcp.environment import run_tcl

r=Path(__file__).resolve().parents[1]
root=r/'.local/native-diagonal-20261027'
source=r/'.local/editor-session-wire-20261026/before.dsn'
assert sha256(source)=='971c4675e25441783520afdd86a898647a39f05f377cc217d5e23c2bfb671dda'
# Inputs and exact rational intersection are frozen before native dispatch.
segments=[[[100,100],[140,120]],[[100,120],[130,100]],
          [[300,100],[400,200]],[[375,175],[325,125]],
          [[500,100],[600,200]],[[550,150],[600,150]],
          [[100,400],[150,450]],[[150,450],[200,400]],
          [[300,400],[340,440]],[[350,450],[400,500]]]
expected={'segments':segments,'rationalCrossing':[[820,7],[760,7]],
          'overlap':[[325,125],[375,175]],'tContact':[550,150],
          'sharedEndpoint':[150,450],'gap':[[340,440],[350,450]],
          'scope':'V02 geometry prerequisite; no electrical connection assertion'}
commands=['   set phase diagonal_wires']
for a,b in segments:
 commands.extend(['   PlaceWire '+' '.join(str(v/100) for v in a+b),'   EndPlace'])
cfg,d,dispatch=run_fixed_probe(root,source,'ROOT','MAIN','\n'.join(commands),expected)
report={'passed':False,'dispatch':dispatch,'fullV02Accepted':False}
try:
 assert dispatch['nativeAccepted'],dispatch.get('error')
 target=d/'design.dsn';before=sha256(target)
 run_tcl(cfg,'inspect.tcl',[str(target),str(root/'definitions.json'),'100000'],root)
 run_tcl(cfg,'inspect_page_objects.tcl',[str(target),str(root/'connections.json'),'connections'],root)
 data=json.loads((root/'connections.json').read_text(encoding='utf-8'))
 wires=[o['attributes'] for o in data['objects'] if o['kind']=='wire']
 report['nativeWires']=wires
 # Exact segment preservation is deliberately strict. A routed/bent replacement
 # cannot count as native diagonal acceptance just because it uses the same ends.
 normalize=lambda paths:sorted(tuple(sorted((tuple(a),tuple(b)))) for points in paths for a,b in zip(points,points[1:]))
 assert normalize([w['points'] for w in wires])==normalize(segments),'native_segment_matrix_differs'
 assert sha256(target)==before
 report.update(passed=True,target=str(target),targetSha256=before,independentReopen=True)
except BaseException:report['error']=traceback.format_exc()
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:report.get(k) for k in ('passed','target','error')}),flush=True)
