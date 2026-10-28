"""Read-only native annotation eligibility diagnostics on the original failed source."""
import json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,run_tcl
from cadence_mcp.gui_loader import tcl_string
r=Path(__file__).resolve().parents[1];root=r/'.local/annotation-validity-20261028';root.mkdir(exist_ok=False)
source=r/'.local/native-incremental-annotation-v2-20261025/reset.dsn';before=sha256(source)
adapter=(ADAPTERS/'inspect_reference_units.tcl').read_text(encoding='utf-8').replace('source [file join [file dirname [info script]] json.tcl]','source '+tcl_string((ADAPTERS/'json.tcl').as_posix()))
anchor='    set rows {};set count 0;set si 0'
setup='''    set manager [$d GetRefDesMgr];$manager RefreshInstanceRefDesMap
    set handler [DboRefDesQueryHandler];set options [RefDesQueryOptions]
    foreach setter {SetFillHolesBetweenDevices SetFillHolesForMultiPartPkg SetFillHolesForSinglePartPkg SetMatchNetsForCommonPins SetPreserveDesForHetero SetPreserveDesForHomo} {$options $setter 1}
    $options SetIncludeNonPrimitive 0
    $handler SetQueryOptions $options;$handler SetQueryMap [$manager GetInstanceRefDesMap]
    set excludeNonPrimitive [$options GetIncludeNonPrimitive]
'''
assert adapter.count(anchor)==1;adapter=adapter.replace(anchor,setup+anchor)
anchor='                            lappend rows [cmcp::obj partId'
extra='''                            set primState [DboState];set primitive [$part IsPrimitive $primState];cmcp::check $primState
                            set valid [$handler IsRefDesValid $part]
                            set value [cmcp::cs ""];set propState [$part GetEffectivePropStringValue [cmcp::cs Primitive] $value]
                            set propertyStatus [expr {[$propState Failed] ? [$propState Code] : 0}]
'''
assert adapter.count(anchor)==1;adapter=adapter.replace(anchor,extra+anchor)
adapter=adapter.replace('partId [cmcp::q $oid] nativeId','isPrimitive $primitive refDesValid [expr {$valid?"true":"false"}] includeNonPrimitive $excludeNonPrimitive effectivePrimitive [cmcp::q [cmcp::str $value]] primitivePropertyStatus $propertyStatus partId [cmcp::q $oid] nativeId')
path=root/'readonly-validity.tcl';path.write_text(adapter,encoding='utf-8')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(source.parent,),45)
report={'passed':False,'annotationAccepted':False,'sourceBefore':before}
try:
 run_tcl(cfg,str(path),[str(source),str(root/'native.json')],root)
 data=json.loads((root/'native.json').read_text(encoding='utf-8'));assert isinstance(data,list)
 selected=[x for x in data if x['reference']=='R?' or x['kind']=='drawn'];assert len(selected)==3
 report.update(passed=True,objects=selected,allObjects=data)
except BaseException as error:report['error']=str(error)
report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','objects','error')},indent=2),flush=True)
