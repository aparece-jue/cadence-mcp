"""Predeclared noncentered rotation hypothesis; preserve the original failed origin oracle."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','original-root'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument("--definition-bounds",type=int,nargs=4)
p.add_argument("--frame-model",choices=("center","size"),default="center")
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);original=a.original_root.resolve();source=original/'r0-m0/design.dsn'
cfg=Config(a.install_root,root,(original,),45)
bounds=a.definition_bounds or [0,0,40,40];left,top,right,bottom=bounds;assert left<right and top<bottom and (left+right)%2==0 and (top+bottom)%2==0
cx=(left+right)//2;cy=(top+bottom)//2
local=[('1','I',[-30,20]),('2','O',[70,20]),('14','VCC',[0,0]),('7','GND',[0,40])]
cases=[]
for mirror in (0,1):
 for rotation in range(4):
  pins=[]
  for number,name,(x,y) in local:
   if a.frame_model=='center':
    x-=cx;y-=cy
    if mirror:x=-x
    for _ in range(rotation):x,y=y,-x
    x+=cx;y+=cy
   else:
    w=right-left;h=bottom-top
    if mirror:x=w-x
    for _ in range(rotation):x,y=y,w-x;w,h=h,w
   pins.append({'number':number,'name':name,'hotSpot':[600+x,400+y]})
  cases.append({'mirror':mirror,'rotation':rotation,'location':[600,400],'pins':pins})
expected={'hypothesis':a.frame_model,'modelDescription':'center: mirror/rotate around declared bounding center; size: mirror/rotate using width/height compensation with zero local anchor','definitionBody':[[left,top],[right,bottom]],'center':[cx,cy],'localPins':local,'cases':cases}
write_json(root/'expected.json',expected);oracle=sha256(root/'expected.json')
original_hashes={str(p.relative_to(original)):sha256(p) for p in [original/'report.json',source,original/'r1-m0/design.dsn',original/'r1-m0/oracle.json']}
report={'passed':False,'scope':'new predeclared frame hypothesis, not replacement of original failed oracle; native definition geometry only','originalSha256':original_hashes,'oracleSha256':oracle,'cases':[]}
for expected in cases:
 d=root/f"r{expected['rotation']}-m{expected['mirror']}";d.mkdir();target=d/'design.dsn';shutil.copy2(source,target);row={'rotation':expected['rotation'],'mirror':expected['mirror'],'passed':False};report['cases'].append(row)
 try:
  proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_name('fixture_part_pose_bounds.tcl' if a.definition_bounds else 'fixture_part_pose.tcl'),cfg.install_root,target,d/'definition-oracle.json','schematic-1/page-1/part-1','100000',str(expected['rotation']),str(expected['mirror']),'600','400']+([str(v) for v in bounds] if a.definition_bounds else []),d,process_env(cfg),45);row['process']=proc
  assert proc['returnCode']==0 and proc['remainingOwnedProcesses']==0
  before=sha256(target)
  run_tcl(cfg,'probe_part_coordinate_frame.tcl',[str(target),str(d/'frame.json'),'schematic-1/page-1/part-1','100000','10000'],d)
  data=json.loads((d/'frame.json').read_text(encoding='utf-8'));row['frame']=data
  actual=sorted((p['number'],p['name'],p['hotSpot']) for p in data['pins']);wanted=sorted((p['number'],p['name'],p['hotSpot']) for p in expected['pins'])
  row['declaredFrameMatches']=actual==wanted
  row['nativePointConversionMatchesPins']=all(p['hotSpot']==p['converted'] for p in data['pins'])
  row['definitionUnchanged']=sorted((p['number'],p['name'],p['localHotSpot']) for p in data['pins'])==sorted(local) and data['boxes'][2]==[[left,top],[right,bottom]]
  row['sourceUnchanged']=sha256(target)==before
  row['passed']=all(row[k] for k in ('declaredFrameMatches','nativePointConversionMatchesPins','definitionUnchanged','sourceUnchanged')) and data['location']==expected['location'] and data['rotationCode']==expected['rotation'] and data['mirrorCode']==expected['mirror']
 except Exception as e:row['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('rotation','mirror','passed','declaredFrameMatches','error')}),flush=True)
report['originalUnchanged']=all(sha256(original/p)==h for p,h in original_hashes.items());report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=all(c['passed'] for c in report['cases']) and report['originalUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
