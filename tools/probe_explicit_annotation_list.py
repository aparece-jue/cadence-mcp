"""Original frozen R?->R1 full-state oracle, using a documented explicit-list path."""
import json,shutil,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_references import read_units
from cadence_mcp.capture_cache_replace import read_state,unit_graph,cache_groups
from cadence_mcp.capture_cache_bindings import query_cache_binding
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_wire import inventory,connection_digest
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/explicit-annotation-list-20261028';root.mkdir(exist_ok=False)
original=r/'.local/native-incremental-annotation-v2-20261025';source=original/'reset.dsn';oracle=original/'expected.json'
source_hash=sha256(source);oracle_hash=sha256(oracle);expected=json.loads(oracle.read_text(encoding='utf-8'));target=root/'annotated.dsn';shutil.copy2(source,target)
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45);report={'passed':False,'originalOracleSha256':oracle_hash,'sourceBefore':source_hash,'nativeAnnotationAccepted':False}
try:
 child=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',r/'tools/fixture_explicit_annotation_list.tcl',cfg.install_root,target,root/'native-receipt.json',ADAPTERS/'json.tcl','annotate'],root,process_env(cfg),45)
 report['process']=child;report['receipt']=json.loads((root/'native-receipt.json').read_text(encoding='utf-8'));assert child['returnCode']==0 and child['remainingOwnedProcesses']==0 and report['receipt']['saved'],report['receipt']
 cap=CaptureService(cfg);sid=cap.open(cap.create_workspace(str(target))['workspaceId'])['sessionId'];actual=cap.sessions[sid]['data'];units=read_units(cap,sid)
 report['actualReferences']=[{'nativeId':u['nativeId'],'reference':u['reference'],'fullReference':u['referenceDesignator']} for u in units.values()]
 report['definitionMatches']=definition_baseline(actual)==definition_baseline(expected['definition'])
 state=read_state(cfg,cap.sessions[sid]['design'],cap.sessions[sid]['design'].parent,units);report['stateMatches']=state==expected['state'];report['unitsMatch']=unit_graph(units)==expected['units'];report['connectionsMatch']=connection_digest(actual,inventory(cap,sid))==expected['connectionDigest']
 owner=next(u for u in units.values() if u['nativeId']==2502);query_cache_binding(cap,sid,owner['partId']);report['cacheMatches']=cache_groups(cap.sessions[sid]['qualifiedCache'])==expected['cache'];cap.close(sid)
 report['passed']=all(report[k] for k in ('definitionMatches','stateMatches','unitsMatch','connectionsMatch','cacheMatches'));report['nativeAnnotationAccepted']=report['passed']
except BaseException:report['error']=traceback.format_exc()
report['outputSha256']=sha256(target);report['outputUnchangedOnRejectedCall']=sha256(target)==source_hash
report['sourceUnchanged']=sha256(source)==source_hash;report['originalOracleUnchanged']=sha256(oracle)==oracle_hash
report['passed']=report['passed'] and report['sourceUnchanged'] and report['originalOracleUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','receipt','outputUnchangedOnRejectedCall','error')}),flush=True)
