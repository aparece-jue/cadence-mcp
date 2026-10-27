"""Native 8-bit bus/entry construction via official editor commands, original geometry."""
import json,traceback
from pathlib import Path
from native_editor_probe import run_fixed_probe
from cadence_mcp.core import sha256
from cadence_mcp.environment import run_tcl
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/editor-eight-bit-bus-20261027';source=r/'.local/editor-session-wire-20261026/before.dsn'
assert sha256(source)=='971c4675e25441783520afdd86a898647a39f05f377cc217d5e23c2bfb671dda'
expected={'busPoints':[[600,200],[600,700]],'busName':'DATA[7..0]','memberNames':[f'DATA{i}' for i in range(7,-1,-1)],'entryPoints':[[600,220+50*i] for i in range(8)],'endPoints':[[620,240+50*i] for i in range(8)],'scalarNames':[f'DATA{i}' for i in range(8)]}
mutation=r'''   set phase bus
   PlaceBus 6.0 2.0 6.0 7.0
   EndPlace
   PlaceNetAlias 6.0 2.0 {DATA[7..0]}
   EndPlace
   set seen [dict create]
   for {set i 0} {$i<8} {incr i} {
    set y [expr {220+50*$i}]
    set phase entry_$i
    PlaceBusEntry 6.0 [expr {$y/100.0}] FALSE
    EndPlace
    set st [DboState];set it [$p NewBusEntriesIter $st];ck $st;set fresh {}
    try {
     for {set e [$it NextBusEntry $st]} {$e ne "NULL"} {set e [$it NextBusEntry $st]} {
      ck $st;set id [$e GetId $st];ck $st
      if {![dict exists $seen $id]} {lappend fresh [list $id $e]}
     }
    } finally {delete_DboPageBusEntriesIter $it}
    if {[llength $fresh]!=1} {error ambiguous_native_entry}
    lassign [lindex $fresh 0] id e;dict set seen $id 1
    # Explicit original geometry, not an observed endpoint adopted as oracle.
    ck [$e SetEntryPoint [DboTclHelper_sMakeCPoint 600 $y]]
    ck [$e SetEndPoint [DboTclHelper_sMakeCPoint 620 [expr {$y+20}]]]
    set phase scalar_$i
    PlaceWire 6.2 [expr {($y+20)/100.0}] 8.0 [expr {($y+20)/100.0}]
    EndPlace
    PlaceNetAlias 8.0 [expr {($y+20)/100.0}] "DATA$i"
    EndPlace
   }
'''
cfg,d,dispatch=run_fixed_probe(root,source,'ROOT','MAIN',mutation,expected);report={'passed':False,'dispatch':dispatch,'fullH04Accepted':False}
try:
 assert dispatch['nativeAccepted'],dispatch.get('error');target=d/'design.dsn';before=sha256(target)
 run_tcl(cfg,'inspect.tcl',[str(target),str(root/'definitions.json'),'100000'],root)
 run_tcl(cfg,'inspect_bus.tcl',[str(target),str(root/'bus.json')],root);data=json.loads((root/'bus.json').read_text(encoding='utf-8'));buses=[w for w in data['wires'] if w['isBus']];scalar=[w for w in data['wires'] if not w['isBus']];entries=data['entries'];report.update(busCount=len(buses),scalarCount=len(scalar),entryCount=len(entries))
 assert buses and all(w['width']==8 and not w['isBundle'] for w in buses)
 assert all([m['name'] for m in w['members']]==expected['memberNames'] for w in buses),[w['members'] for w in buses]
 assert len(scalar)==8 and sorted(w['name'] for w in scalar)==sorted(expected['scalarNames'])
 assert len(entries)==8 and sorted(e['entryPoint'] for e in entries)==expected['entryPoints'] and sorted(e['endPoint'] for e in entries)==expected['endPoints']
 wires={w['wireId']:w for w in data['wires']};assert all(e['entryWireId'] in wires and wires[e['entryWireId']]['isBus'] and e['endWireId'] in wires and not wires[e['endWireId']]['isBus'] for e in entries)
 assert sha256(target)==before;report.update(passed=True,independentNewProcessReopen=True,originalEightBitEntryGeometryAccepted=True)
except BaseException:report['error']=traceback.format_exc()
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
