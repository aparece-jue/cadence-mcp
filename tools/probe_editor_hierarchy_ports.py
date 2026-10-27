"""Official native PlacePort/PlaceWire on owned initialized design; original port oracle."""
import json,traceback
from pathlib import Path
from native_editor_probe import run_fixed_probe
from cadence_mcp.core import sha256
from cadence_mcp.environment import run_tcl
from cadence_mcp.gui_loader import tcl_string
r=Path(__file__).resolve().parents[1];root=r/'.local/editor-hierarchy-ports-20261027';source=r/'.local/editor-hierarchy-scaffold-20261027/design.dsn';lib=Path(r'D:\Program Files\Cadence\SPB_24.1\tools\capture\library\capsym.olb');lib_hash=sha256(lib)
expected=dict(ports={'IN':dict(hotSpot=[100,100],pinType=0),'OUT':dict(hotSpot=[300,100],pinType=1)},wire=[[100,100],[300,100]],sourceSymbol='PORTLEFT-L',rule='Both native ports and wire share one DboNet identity; no name-only or intersection inference.')
mutation='''   set phase native_ports
   PlacePort 1 0.9 LIB PORTLEFT-L IN
   EndPlace
   PlacePort 3 0.9 LIB PORTLEFT-L OUT
   EndPlace
   set phase port_types
   source "D:/workspace/git/cadence-mcp/src/cadence_mcp/adapters/dbo_iterator.tcl"
   proc portNext {it} {return [::cmcp::next_object $it NextPort]}
   set state [DboState];set it [$p NewPortsIter $state $::IterDefs_ALL];ck $state;set found {}
   try {
    for {set o [portNext $it]} {$o ne "NULL"} {set o [portNext $it]} {
     ck $state;set name [DboTclHelper_sMakeCString ""];ck [$o GetName $name];set name [DboTclHelper_sGetConstCharPtr $name]
     if {$name ni {IN OUT} || [dict exists $found $name]} {error unexpected_port}
     ck [$o SetPinType [expr {$name eq "IN" ? 0 : 1}]];dict set found $name 1
    };ck $state
   } finally {delete_DboPagePortsIter $it}
   if {[dict size $found]!=2} {error missing_port}
   set phase native_wire
   PlaceWire 1.0 1.0 3.0 1.0
   EndPlace
'''.replace('LIB',tcl_string(lib.as_posix()))
cfg,d,dispatch=run_fixed_probe(root,source,'CHILD','CHILD_PAGE',mutation,expected);report=dict(passed=False,dispatch=dispatch,fullH03Accepted=False,librarySha256=lib_hash)
try:
 assert dispatch['nativeAccepted'],dispatch.get('error');target=d/'design.dsn';saved=sha256(target)
 run_tcl(cfg,'inspect.tcl',[str(target),str(root/'definitions.json'),'100000'],root)
 run_tcl(cfg,str(r/'tools/inspect_native_ports_declared.tcl'),[str(target),str(root/'ports.json')],root)
 data=json.loads((root/'ports.json').read_text(encoding='utf-8'));report['observation']=data;assert data['passed']
 assert len(data['ports'])==2 and len(data['wires'])==1
 observed={p['name']:p for p in data['ports']};assert set(observed)==set(expected['ports'])
 for name,want in expected['ports'].items():
  for key,value in want.items():assert observed[name][key]==value,(name,key,observed[name],value)
  assert observed[name]['sourceSymbol']==expected['sourceSymbol']
 assert observed['IN']['netGroup'] is not None and observed['IN']['netGroup']==observed['OUT']['netGroup']==data['wires'][0]['netGroup']
 assert data['wires'][0]['points']==expected['wire'];assert sha256(target)==saved
 report.update(passed=True,independentReopen=True,portDirectionsAndNativeConnectionVerified=True,originalHotspotOraclePreserved=True)
except BaseException:report['error']=traceback.format_exc()
report['sourceGeometrySha256']='46a7d87167d0cf4c6db566232b1c9582db512f19e6962fca058b278e5412ea17';report['placementOffsetFromSourceOnly']=[0, 10]
report['libraryUnchanged']=sha256(lib)==lib_hash;report['passed']=report['passed'] and report['libraryUnchanged'] and dispatch['sourceUnchanged'] and dispatch['hostUnchanged'] and dispatch['oracleUnchanged']
report['originalHierarchyOracleSha256']=sha256(r/'.local/hierarchy-fresh-ports-v2-20261023/expected.json')
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
