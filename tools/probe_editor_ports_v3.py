"""Official native PlacePort/PlaceWire on owned initialized design; original port oracle."""
import json,traceback
from pathlib import Path
from native_editor_probe import run_fixed_probe
from cadence_mcp.core import sha256
from cadence_mcp.environment import run_tcl
from cadence_mcp.gui_loader import tcl_string
r=Path(__file__).resolve().parents[1];root=r/'.local/editor-ports-v3-20261027';source=r/'.local/editor-session-wire-20261026/before.dsn';lib=Path(r'D:\Program Files\Cadence\SPB_24.1\tools\capture\library\capsym.olb');lib_hash=sha256(lib)
expected=dict(ports={'IN':dict(hotSpot=[100,100],pinType=0),'OUT':dict(hotSpot=[300,100],pinType=1)},wire=[[100,100],[300,100]],sourceSymbol='PORTLEFT-L',rule='Both native ports and wire share one DboNet identity; no name-only or intersection inference.')
mutation='''   set phase native_ports
   PlacePort 1.0 1.0 LIB PORTLEFT-L IN
   EndPlace
   PlacePort 3.0 1.0 LIB PORTLEFT-L OUT
   EndPlace
   set phase port_types
   proc portNext {it} {set nextState [DboState];set o [$it NextPort $nextState];if {$o eq "NULL" && [$nextState Failed] && [$nextState Code]==1022} {return NULL};ck $nextState;return $o}
   set state [DboState];set it [$p NewPortsIter $state $::IterDefs_ALL];ck $state;set found {}
   try {
    for {set o [portNext $it]} {$o ne "NULL"} {set o [portNext $it]} {
     ck $state;set nameState [DboState];set name [DboNetSymbolInstance_sGetNetName $o $nameState];ck $nameState;set name [DboTclHelper_sGetConstCharPtr $name]
     if {$name ni {IN OUT} || [dict exists $found $name]} {error unexpected_port}
     ck [$o SetPinType [expr {$name eq "IN" ? 0 : 1}]];dict set found $name 1
    };ck $state
   } finally {delete_DboPagePortsIter $it}
   if {[dict size $found]!=2} {error missing_port}
   set phase native_wire
   PlaceWire 1.0 1.0 3.0 1.0
   EndPlace
'''.replace('LIB',tcl_string(lib.as_posix()))
cfg,d,dispatch=run_fixed_probe(root,source,'ROOT','MAIN',mutation,expected);report=dict(passed=False,dispatch=dispatch,fullH03Accepted=False,librarySha256=lib_hash)
try:
 assert dispatch['nativeAccepted'],dispatch.get('error');target=d/'design.dsn';saved=sha256(target)
 run_tcl(cfg,'inspect.tcl',[str(target),str(root/'definitions.json'),'100000'],root)
 run_tcl(cfg,str(r/'tools/inspect_native_ports_qualified.tcl'),[str(target),str(root/'ports.json')],root)
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
report['libraryUnchanged']=sha256(lib)==lib_hash;report['passed']=report['passed'] and report['libraryUnchanged'] and dispatch['sourceUnchanged'] and dispatch['hostUnchanged'] and dispatch['oracleUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
