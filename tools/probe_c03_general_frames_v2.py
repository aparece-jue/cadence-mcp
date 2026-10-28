"""Source-frozen independent frame oracle on original and imported native parts."""
import json,shutil,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/c03-general-frames-v2-20261028';root.mkdir(exist_ok=False)
original=r/'.local/pose-matrix-1fc81bf46d/r0-m0/design.dsn'
prior_root=r/'.local/public-vector-placement-20261024';prior=json.loads((prior_root/'report.json').read_text(encoding='utf-8'));c=prior['cases'][0];mixed=prior_root/'work'/c['result']['outputWorkspaceRelativePath']/'design.dsn';assert sha256(mixed)==c['result']['artifact']['sha256']
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(r/'.local',),45)
declarations=[('original',original,'U3'),('resistor',mixed,'R101'),('imported_mixed',mixed,c['plan']['preview']['reference'])]
old_files=[r/'.local/pose-matrix-1fc81bf46d/report.json',r/'.local/pose-matrix-1fc81bf46d/r0-m0/oracle.json',r/'.local/pose-matrix-1fc81bf46d/r1-m0/oracle.json']
old_hashes={str(p.relative_to(r)):sha256(p) for p in old_files}
sources=[];cases=[]
for label,source,reference in declarations:
 run_tcl(cfg,'inspect.tcl',[str(source),str(root/(label+'-definitions.json')),'100000'],root)
 definitions=json.loads((root/(label+'-definitions.json')).read_text(encoding='utf-8'));parts=[p for p in definitions['part'] if p['reference']==reference and (label!='original' or p['objectId']=='schematic-1/page-1/part-1')];assert len(parts)==1
 part=parts[0];frame_path=root/(label+'-source-frame.json')
 run_tcl(cfg,'probe_part_coordinate_frame.tcl',[str(source),str(frame_path),part['objectId'],'100000','10000'],root)
 frame=json.loads(frame_path.read_text(encoding='utf-8'));box=frame['boxes'][2];width=box[1][0]-box[0][0];height=box[1][1]-box[0][1];assert width>=0 and height>=0
 # Input-only fields: never use observed/converted target hotspots as expectations.
 local=[{'number':p['number'],'name':p['name'],'point':p['localHotSpot']} for p in frame['pins']]
 record={'label':label,'source':str(source),'sourceSha256':sha256(source),'partId':part['objectId'],'reference':reference,'sourceDefinitionBox':box,'sourceLocalPins':local,'sourceFrameSha256':sha256(frame_path)};sources.append(record)
 for mirror in (0,1):
  for rotation in range(4):
   pins=[]
   for pin in local:
    x,y=pin['point'];w,h=width,height
    if mirror:x=w-x
    for _ in range(rotation):x,y=y,w-x;w,h=h,w
    pins.append({'number':pin['number'],'name':pin['name'],'hotSpot':[800+x,600+y]})
   cases.append({'label':label,'rotation':rotation,'mirror':mirror,'location':[800,600],'partId':part['objectId'],'pins':pins})
(root/'expected.json').write_text(json.dumps({'model':'Prior independently qualified width/height compensation; source defining-box dimensions and local defining pins frozen before new pose mutations. Original failed local-zero/center hypotheses retained, not rewritten.','sources':sources,'cases':cases,'originalEvidenceSha256':old_hashes},indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
report={'passed':False,'cases':[],'fullC03Accepted':False,'oracleSha256':oracle,'sourceDeclarations':sources}
for case in cases:
 label=case['label'];source=Path(next(s['source'] for s in sources if s['label']==label));d=root/(label+f'-r{case["rotation"]}-m{case["mirror"]}');d.mkdir();target=d/'design.dsn';shutil.copy2(source,target);row={k:case[k] for k in ('label','rotation','mirror','partId')};row['passed']=False;report['cases'].append(row)
 try:
  child=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',r/'tools/fixture_part_pose.tcl',cfg.install_root,target,d/'fixture-receipt.json',case['partId'],'100000',str(case['rotation']),str(case['mirror']),'800','600'],d,process_env(cfg),45)
  row['fixtureProcess']=child;assert child['returnCode']==0 and child['remainingOwnedProcesses']==0
  saved=sha256(target);run_tcl(cfg,'probe_part_coordinate_frame.tcl',[str(target),str(d/'native-frame.json'),case['partId'],'100000','10000'],d);actual=json.loads((d/'native-frame.json').read_text(encoding='utf-8'))
  key=lambda p:(p['number'],p['name'],p['hotSpot'])
  row['independentFrameMatches']=sorted(map(key,actual['pins']))==sorted(map(key,case['pins']))
  row['nativeConversionAgrees']=all(p['hotSpot']==p['converted'] for p in actual['pins'])
  row['poseMatches']=actual['location']==case['location'] and actual['rotationCode']==case['rotation'] and actual['mirrorCode']==case['mirror']
  row['savedUnchanged']=sha256(target)==saved;row['target']=str(target);row['targetSha256']=saved
  row['passed']=all(row[k] for k in ('independentFrameMatches','nativeConversionAgrees','poseMatches','savedUnchanged'))
 except BaseException:row['error']=traceback.format_exc()
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('label','rotation','mirror','passed','error')}),flush=True)
report['sourcesUnchanged']=all(sha256(Path(s['source']))==s['sourceSha256'] for s in sources)
report['originalEvidenceUnchanged']=all(sha256(r/p)==h for p,h in old_hashes.items());report['oracleUnchanged']=sha256(root/'expected.json')==oracle
report['passed']=all(c['passed'] for c in report['cases']) and report['sourcesUnchanged'] and report['originalEvidenceUnchanged'] and report['oracleUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'acceptedCases':sum(c['passed'] for c in report['cases']),'totalCases':len(cases)}),flush=True)
