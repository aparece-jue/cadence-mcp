"""Read-only qualification of native bounds; does not certify rendered clearance."""
import json,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,run_tcl
from cadence_mcp.gui_loader import tcl_string
r=Path(__file__).resolve().parents[1];root=r/'.local/clearance-bound-frames-20261027';root.mkdir(exist_ok=False)
source=r/'.local/noncentered-pose-rectangle-a-20261026/r0-m0/design.dsn';before=sha256(source)
expected={'sourceLocation':[600,400],'declaredDefinitionBox':[[-10,10],[70,50]],'zeroPoseDefinitionCornersOnPage':[[590,410],[670,410],[670,450],[590,450]],'acceptance':'Record distinct native bounds and transformed declaration; no rendered glyph/body clearance certification'}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
base=(ADAPTERS/'probe_part_coordinate_frame.tcl').read_text(encoding='utf-8')
base=base.replace('source [file join [file dirname [info script]] json.tcl]','source '+tcl_string((ADAPTERS/'json.tcl').as_posix()))
anchor='                            set actualPins {}'
assert base.count(anchor)==1
code='''                            set transformedCorners {}
                            set box [$definition GetBoundingBox]
                            set a [DboTclHelper_sGetCRectTopLeft $box];set b [DboTclHelper_sGetCRectBottomRight $box]
                            set left [DboTclHelper_sGetCPointX $a];set top [DboTclHelper_sGetCPointY $a]
                            set right [DboTclHelper_sGetCPointX $b];set bottom [DboTclHelper_sGetCPointY $b]
                            foreach xy [list [list $left $top] [list $right $top] [list $right $bottom] [list $left $bottom]] {
                              set point [$part GetOffsetGraphicPoint [DboTclHelper_sMakeCPoint {*}$xy]]
                              lappend transformedCorners [cmcp::point $point]
                            }
'''
base=base.replace(anchor,code+anchor).replace('set found [cmcp::obj boxes [cmcp::arr $boxes]','set found [cmcp::obj definitionCornersOnPage [cmcp::arr $transformedCorners] boxes [cmcp::arr $boxes]')
adapter=root/'readonly-bound-frames.tcl';adapter.write_text(base,encoding='utf-8')
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(source.parent,),45)
report={'readContractPassed':False,'automaticClearanceAccepted':False,'sourceBefore':before}
try:
 run_tcl(cfg,str(adapter),[str(source),str(root/'frames.json'),'schematic-1/page-1/part-1','100000','10000'],root)
 frames=json.loads((root/'frames.json').read_text(encoding='utf-8'));report['observation']=frames
 assert frames['location']==expected['sourceLocation'] and frames['boxes'][2]==expected['declaredDefinitionBox']
 assert frames['rotationCode']==0 and frames['mirrorCode']==0
 assert frames['definitionCornersOnPage']==expected['zeroPoseDefinitionCornersOnPage']
 assert len(frames['boxes'])==3
 report.update(readContractPassed=True,rawCachedBoxDiffersFromOffsetBox=frames['boxes'][0]!=frames['boxes'][1],offsetBoxDiffersFromTransformedDeclaration=frames['boxes'][1]!=[[590,410],[670,450]],nextAction='Qualify actual defining graphic extents and display-property font/render bounds before any automatic avoidance verdict. Do not infer native API defect from an artificially overridden definition box.')
except BaseException:report['error']=traceback.format_exc()
report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:report.get(k) for k in ('readContractPassed','automaticClearanceAccepted','rawCachedBoxDiffersFromOffsetBox','offsetBoxDiffersFromTransformedDeclaration','sourceUnchanged','error')}),flush=True)
