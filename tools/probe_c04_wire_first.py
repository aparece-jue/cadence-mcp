"""Fixed original C04 forty-object construction-order contrast; private fixtures only."""
import json,shutil,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
from native_editor_probe import run_fixed_probe
r=Path(__file__).resolve().parents[1];root=r/'.local/c04-wire-first-20261028';root.mkdir(exist_ok=False)
old=r/'.local/c04-editor-matrix-final-20261027';base=r/'.local/c04-editor-matrix-base-20261027'
oracle=old/'expected.json';oracle_hash=sha256(oracle);assert oracle_hash=='7a149b2739f4a522e95fe2a0051c3bcca116c82f9c15f522e206b2e248ba2124'
shutil.copy2(oracle,root/'expected.json');shutil.copy2(old/'expected-original-hypothesis.json',root/'expected-original-hypothesis.json')
shutil.copy2(base/'library.olb',root/'library.olb');libhash=sha256(base/'library.olb')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45)
fixture=(r/'tools/fixture_connection_inventory_no_wires.tcl').read_text(encoding='utf-8')
start=fixture.index('  if {$name ne "EMPTY"} {');end=fixture.index('\n  ck [$page MarkModified]',start)
empty=fixture[:start]+fixture[end:];emptyfile=root/'empty-pages.tcl';emptyfile.write_text(empty,encoding='utf-8')
report={'passed':False,'fullC04Accepted':False,'originalFortyObjectScopePreserved':True,'originalOracleSha256':oracle_hash,'stages':[]}
try:
 source=root/'empty.dsn';proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',emptyfile,cfg.install_root,root/'library.olb',source,root/'empty-receipt.json',ADAPTERS/'json.tcl'],root,process_env(cfg),45)
 assert proc['returnCode']==0 and proc['remainingOwnedProcesses']==0
 run_tcl(cfg,'inspect.tcl',[str(source),str(root/'empty-definitions.json'),'100000'],root)
 defs=json.loads((root/'empty-definitions.json').read_text(encoding='utf-8'));assert sorted(p['name'] for p in defs['page'])==['EMPTY','PAGE_A','PAGE_B'] and not defs['part'] and not defs['pin']
 mutation=r'''   foreach pageName {PAGE_A PAGE_B} {
    OPage TOP $pageName
    set st [DboState];set p [$s GetPage [DboTclHelper_sMakeCString $pageName] $st];ck $st
    if {[GetActivePage] ne $p || [GetActiveView] eq "NULL"} {error wrong_output_editor}
    foreach y {800 900} {
     set phase wire_${pageName}_$y
     PlaceWire 1.0 [expr {$y/100.0}] 2.0 [expr {$y/100.0}]
     EndPlace
     PlaceNetAlias 1.4 [expr {$y/100.0}] LOCAL_DUP
     EndPlace
    }
    ck [$p MarkModified];ck [$s MarkModified $p];ck [$s SavePage $p]
   }
'''
 dispatchroot=root/'editor';_,job,dispatch=run_fixed_probe(dispatchroot,source,'TOP','PAGE_A',mutation,{'wires':4,'aliases':4,'pages':['PAGE_A','PAGE_B','EMPTY'],'points':[[[100,800],[200,800]],[[100,900],[200,900]]]})
 report['dispatch']=dispatch;assert dispatch['nativeAccepted'],dispatch.get('error')
 target=job/'design.dsn';run_tcl(cfg,'inspect_page_objects.tcl',[str(target),str(root/'wires-first.json'),'connections'],root)
 objects=json.loads((root/'wires-first.json').read_text(encoding='utf-8'))['objects'];assert sum(o['kind']=='wire' for o in objects)==4 and sum(o['kind']=='alias' for o in objects)==4
 report['stages'].append({'stage':'four_wires_and_aliases_independent_reopen','passed':True})
 # The same source OLB, object names and pose loops; no target readouts enter expectations.
 text=fixture.replace('set d [$session CreateDesign $st [cs $target] [cs TOP]]','set d [$session GetDesignAndSchematics [cs $target] $st]')
 text=text.replace('set page [$sch NewPage $st [cs $name]]','set page [$sch GetPage [cs $name] $st]')
 # Symbol definitions are already copied in the blank fixture; reuse them.
 a=text.index(' set copy [$d CopySymbol');b=text.index(' set global [$d GetGlobalSymbol',a);text=text[:a]+text[b:]
 script=root/'add-original-symbols.tcl';script.write_text(text,encoding='utf-8');final=root/'design.dsn';shutil.copy2(target,final)
 proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script,cfg.install_root,root/'library.olb',final,root/'symbols-receipt.json',ADAPTERS/'json.tcl'],root,process_env(cfg),45);report['symbolProcess']=proc
 assert proc['returnCode']==0 and proc['remainingOwnedProcesses']==0
 run_tcl(cfg,'inspect.tcl',[str(final),str(root/'definitions.json'),'100000'],root)
 run_tcl(cfg,'inspect_page_objects.tcl',[str(final),str(root/'connections.json'),'connections'],root)
 report.update(passed=True,wireFirstFullMatrixIndependentlyReadable=True)
except BaseException:report['error']=traceback.format_exc()
report['originalOracleUnchanged']=sha256(oracle)==oracle_hash and sha256(root/'expected.json')==oracle_hash
report['sourceLibraryUnchanged']=sha256(base/'library.olb')==libhash
report['passed']=report['passed'] and report['originalOracleUnchanged'] and report['sourceLibraryUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report),flush=True)
raise SystemExit(0 if report['passed'] else 1)
