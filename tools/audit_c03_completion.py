"""Requirement-by-requirement C03 acceptance audit; preserves rejected old oracles."""
import hashlib,json
from pathlib import Path
r=Path(__file__).resolve().parents[1];root=r/'.local/c03-completion-audit-20261028';root.mkdir(exist_ok=False)
def read(p):return json.loads((r/p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256((r/p).read_bytes()).hexdigest()
acceptance=read('docs/implementation/cadence-acceptance.json');feature=next(x for x in acceptance['features'] if x['id']=='C03');assert feature['required'] and feature['dependencies']==['C01']
assert next(x for x in acceptance['features'] if x['id']=='C01')['status']=='passed'
native=read('.local/c03-general-frames-v2-20261028/report.json');public=read('.local/c03-general-frames-mcp-20261028/report.json');expected=read('.local/c03-general-frames-v2-20261028/expected.json')
assert native['passed'] and public['passed'] and len(native['cases'])==len(public['cases'])==len(expected['cases'])==24
assert all(native[k] for k in ('sourcesUnchanged','originalEvidenceUnchanged','oracleUnchanged'))
assert all(public[k] for k in ('duplicateReferencePartIdIsolationAccepted','sourcesUnchanged','originalInputsUnchanged','oldFailedOraclesUnchanged','oracleUnchanged','wrongTargetStaleClosedAndFreshServerGuardsAccepted'))
for label in ('original','resistor','imported_mixed'):
 for report in (native,public):assert {(c['rotation'],c['mirror']) for c in report['cases'] if c['label']==label and c['passed']}=={(a,b) for a in range(4) for b in (0,1)}
assert all(c['independentFrameMatches'] and c['nativeConversionAgrees'] and c['poseMatches'] for c in native['cases'])
for source in expected['sources']:
 assert hashlib.sha256(Path(source['source']).read_bytes()).hexdigest()==source['sourceSha256']
assert {tuple(s['sourceDefinitionBox'][1]) for s in expected['sources']}=={(40,40),(20,20),(0,0)}
# Same historical observed/native behavior, not an old failed oracle retroactively passed.
old=read('.local/pose-matrix-1fc81bf46d/report.json');assert not old['passed']
o=next(c for c in old['cases'] if c['rotationCode']==1 and c['mirrorCode']==0)
n=next(c['actual'] for c in public['cases'] if c['label']=='original' and c['rotation']==1 and c['mirror']==0)
normalize=lambda pins,loc:sorted((p[0],p[1],[p[2][0]-loc[0],p[2][1]-loc[1]]) for p in pins)
assert normalize(o['observedPins'],o['observedLocation'])==normalize([(p['number'],p['name'],p['hotSpot']) for p in n['pins']],n['location'])
assert o['expectedPins']!=o['observedPins']
holdout=read('.local/noncentered-pose-rectangle-b-20261026/report.json');old_public=read('.local/pose-frame-mcp-20261026/report.json');assert holdout['passed'] and old_public['passed']
assert read('.local/noncentered-pose-rectangle-a-20261026/report.json')['passed'] is False
shared=[]
for name,old_name,units,pins in [('c03-shared-homogeneous-20261028','shared-pin-reads-mcp-v2-20261024',2,6),('c03-shared-heterogeneous-20261028','shared-pin-heterogeneous-mcp-20261024',3,8)]:
 current=read('.local/'+name+'/report.json');prior=read('.local/'+old_name+'/report.json')
 assert current['passed'] and current['geometryVerified'] and current['unitCount']==units and current['pinDefinitionRows']==pins
 assert current['sourceBefore']==current['sourceAfter']==prior['sourceBefore']==prior['sourceAfter']
 shared.append({'case':name,'units':units,'pinDefinitionRows':pins,'sourceUnchanged':True,'geometryVerified':True})
drawn=read('.local/c03-drawn-geometry-20261028/report.json');assert drawn['passed'] and drawn['sourceUnchanged'] and drawn['oracleUnchanged'] and not drawn['fullH03Accepted']
log=(r/'.local/regression-c03-geometry-20261028.txt').read_text(encoding='utf-8');assert 'Ran 5 tests' in log and 'OK' in log and 'skipped' not in log
paths=['docs/implementation/cadence-plan.md','src/cadence_mcp/capture_geometry.py','src/cadence_mcp/adapters/inspect_part_geometry.tcl','tests/test_part_geometry.py','.local/c03-general-frames-v2-20261028/expected.json','.local/c03-general-frames-v2-20261028/report.json','.local/c03-general-frames-mcp-20261028/report.json','.local/c03-shared-homogeneous-20261028/report.json','.local/c03-shared-heterogeneous-20261028/report.json','.local/c03-drawn-geometry-20261028/report.json','.local/regression-c03-geometry-20261028.txt','.local/pose-matrix-1fc81bf46d/report.json','.local/noncentered-pose-rectangle-a-20261026/report.json','.local/noncentered-pose-rectangle-b-20261026/report.json','.local/pose-frame-mcp-20261026/report.json']
criteria=[{'requirement':'Original C03: position/rotation/mirror plus actual pin hotspots, original four directions and mirror fixtures','proof':'24 independent source-frozen/native save-reopen cases and actual public API reads across original failed source, real resistor and imported mixed symbol; all pin numbers/names/hotspots and poses match. Native graphic point agrees independently.','accepted':True},
{'requirement':'Broader original source/frame integration, without replacing old failures with only a centered small fixture','proof':'Actual original first failed object re-tested in all8 poses; separate100x60 offset holdout/native/MCP retained; 0/20/40 source definition-box sizes, drawn hierarchy block manual hotspots, and current shared2/3-unit6/8-pin queries.','accepted':True},
{'requirement':'Target/source/revision/identity/lifecycle guards and dependency','proof':'C01 passed; duplicateU3 correctly separated by partId, all pinIds source-bound, wrong target/stale/closed/fresh-server refused. Five dedicated malformed-output/pin/parent/source-during-worker tests passed; every source and old oracle retained.','accepted':True},
{'requirement':'Explain and preserve old failed local-zero/center hypotheses','proof':'Original r1 native normalized observed coordinates exactly match fresh public output; old wrong expectedPins remain unequal. Width/height source dimensions and defining local pins are frozen before new mutations; older non-square holdout falsified center model. Old reports are not changed to passed.','accepted':True}]
report={'gate':'C03','accepted':all(c['accepted'] for c in criteria),'scopeUnchanged':'Design-definition position/rotation/mirror/native physical pin hotspot read API. This does not accept writes/electrical behavior or occurrence/render geometry.','criteria':criteria,'sharedReadCases':shared,'oldFailedOracleStillFalse':True,'oldObservedBehaviorStillMatches':True,'notPromoted':['L03/D04/L05 shared-power wiring/cache-copy acceptance','D02 pose-write electrical preservation','H02/H03 occurrence and cross-boundary connectivity','C05/V02 rendered glyph/stroke clearance'],'evidenceSha256':{p:sha(p) for p in paths}}
(root/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'gate':'C03','accepted':report['accepted'],'nativePoseCases':24,'publicPoseCases':24,'sharedReadCases':2,'drawnReadCases':1,'oldFailedOraclesPreserved':True}))
