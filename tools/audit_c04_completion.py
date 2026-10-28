"""Audit original C04 read scope against actual native and public MCP evidence."""
import collections,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/c04-completion-audit-20261028';root.mkdir(exist_ok=False)
def read(p):return json.loads((r/p).read_text(encoding='utf-8'))
data=read('docs/implementation/cadence-acceptance.json');feature=next(f for f in data['features'] if f['id']=='C04')
assert feature['dependencies']==['C01'] and next(f for f in data['features'] if f['id']=='C01')['status']=='passed'
expected=read('.local/c04-wire-first-20261028/expected.json');actual=read('.local/c04-wire-first-mcp-20261028/report.json');native=read('.local/c04-wire-first-20261028/report.json')
assert native['passed'] and actual['passed'] and all(actual['checks'].values()) and not actual['differences']
assert actual['sourceHashesBefore']==actual['sourceHashesAfter']
assert len(expected['objects'])==len(actual['matrixObjects'])==40
assert collections.Counter(x['kind'] for x in actual['matrixObjects'])=={'global':16,'offpage':16,'wire':4,'alias':4}
assert len(actual['ports'])==9 and len(actual['nc'])==1
assert actual['sourceHashesBefore']['expected']=='7a149b2739f4a522e95fe2a0051c3bcca116c82f9c15f522e206b2e248ba2124'
historical={}
for p,h in read('docs/implementation/batch-114-evidence.json')['evidenceSha256'].items():
 if p.startswith(('.local/c04-','.local/net-symbol-frame-calibration-')):
  assert sha256(r/p)==h,p;historical[p]=h
failed=read('.local/connection-inventory-mcp-20261025/report.json');assert failed['passed'] is False
source=r/'.local/connection-inventory-matrix-v2-20261025/design.dsn';before=sha256(source)
assert before==failed['sourceHashesBefore']['matrix']==failed['sourceHashesAfter']['matrix']
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,source.parent),45)
proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'probe_page_status.tcl',cfg.install_root,source,root/'original-failed-source-status.json'],root,process_env(cfg),45)
assert proc['returnCode']==0 and proc['remainingOwnedProcesses']==0
status=json.loads((root/'original-failed-source-status.json').read_text(encoding='utf-8'))
assert not status['probeError'] and status['rows'][-1]['stage']=='next_page' and status['rows'][-1]['code']==3969 and status['rows'][-1]['failed']==1
assert sha256(source)==before
report={'passed':True,'scope':'Original C04 definition-level read inventory, not arbitrary fixture construction or connectivity semantics','requirements':{'dependencyC01':True,'allSixObjectKinds':True,'fortyObjectOriginalMatrix':True,'allEightPosesOnBothPages':True,'coordinatesAndNames':True,'emptyPage':True,'pageScopedDuplicateNames':True,'aliasWireParent':True,'allNineOriginalPorts':True,'sharedNcOwnerAndHotspot':True,'pagingAndCursorIsolation':True,'sixAdditionalOpenReadClose':True,'cachedSourceTamperAndClosedSessionRefused':True},'fullC04Accepted':True,'standaloneNewWireScalarFixed':False,'arbitraryEditorOrderFixed':False,'oldOracleRewritten':False,'oldFailureStillRejected':True,'oldSourceSha256':before,'historicalEvidenceSha256':historical,'originalFailureReprobeProcess':proc,'latestFullRegressionReusedFromBatch128':True,'newFullRegressionRun':False}
(root/'audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ['historicalEvidenceSha256','originalFailureReprobeProcess']}),flush=True)
