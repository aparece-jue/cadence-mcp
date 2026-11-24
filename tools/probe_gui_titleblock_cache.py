"""Host-only, read-only Capture titleblock cache diagnostic on an already bound copy.

Does not open a design, activate a page, save, or create/delete a Dbo session.
The caller must establish the private editor context first.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

from cadence_mcp.bridge_rpc import process_image
from cadence_mcp.core import sha256
from cadence_mcp.gui_loader import tcl_string

SCRIPT = r'''
namespace eval ::cmcpGuiTitleProbe {
 proc run {} {
  if {[pid] != EXPECTED_PID} {error wrong_process}
  set ini [file normalize [GetIniPath]]
  if {[file isdirectory $ini]} {set ini [file join $ini Capture.ini]}
  if {![string equal -nocase $ini EXPECTED_INI]} {error wrong_ini}
  set d [GetActivePMDesign]
  if {$d eq "NULL" || $d eq ""} {error missing_active_design}
  set name [cs ""];ck [$d GetName $name]
  if {![string equal -nocase [file normalize [str $name]] EXPECTED_DESIGN]} {error wrong_design}
  set rows {};set pages {};set count 0;set titles 0
  set st [DboState];set vi [$d NewViewsIter $st $::IterDefs_SCHEMATICS];ck $st
  try {for {set view [$vi NextView $st]} {$view ne "NULL"} {set view [$vi NextView $st]} {
   ck $st;set sch [DboViewToDboSchematic $view];set sn [cs ""];ck [$sch GetName $sn]
   set pi [$sch NewPagesIter $st];ck $st
   try {for {set page [$pi NextPage $st]} {$page ne "NULL"} {set page [$pi NextPage $st]} {
    ck $st;if {[incr count]>64} {error page_limit}
    set pn [cs ""];ck [$page GetName $pn]
    lappend pages [cmcp::obj schematic [cmcp::q [str $sn]] page [cmcp::q [str $pn]]]
    set it [$page NewTitleBlocksIter $st];ck $st
    try {for {set t [$it NextTitleBlock $st]} {$t ne "NULL"} {set t [$it NextTitleBlock $st]} {
     ck $st;if {[incr titles]>4096} {error title_limit}
     set id [$t GetId $st];ck $st;set sym [$t GetSymbol $st];ck $st
     if {$sym eq "NULL"} {error missing_symbol}
     set offset [$t GetOffsetBoundingBox $st];ck $st
     set fields [list schematic [cmcp::q [str $sn]] page [cmcp::q [str $pn]] nativeId $id dirty [$t IsBoundingBoxDirty] local [rect [$t GetBoundingBox]] offset [rect $offset] symbol [rect [$sym GetBoundingBox]]]
     foreach {key method} {name GetName designName GetDesignName designFileName GetDesignFileName pageSize GetPageSize} {
      set v [cs ""];ck [$t $method $v];lappend fields $key [cmcp::q [str $v]]
     }
     foreach {key method} {pageNumber GetPageNumber pageCount GetPageCount} {set v [$t $method $st];ck $st;lappend fields $key $v}
     lappend rows [cmcp::obj {*}$fields]
    }} finally {delete_DboPageTitleBlocksIter $it}
   }} finally {delete_DboSchematicPagesIter $pi}
  }} finally {delete_DboLibViewsIter $vi}
  set activePage "NULL";set ap "";set pageError ""
  catch {set activePage [GetActivePage]} pageError
  if {$activePage ne "NULL" && $activePage ne ""} {set v [cs ""];ck [$activePage GetName $v];set ap [str $v];set pageError ""}
  return [cmcp::obj activePage [cmcp::q $ap] activePageError [cmcp::q $pageError] pages [cmcp::arr $pages] rows [cmcp::arr $rows]]
 }
 proc cs {v} {DboTclHelper_sMakeCString $v}
 proc str {v} {DboTclHelper_sGetConstCharPtr $v}
 proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
 proc pt {p} {list [DboTclHelper_sGetCPointX $p] [DboTclHelper_sGetCPointY $p]}
 proc rect {r} {cmcp::arr [concat [pt [DboTclHelper_sGetCRectTopLeft $r]] [pt [DboTclHelper_sGetCRectBottomRight $r]]]}
}
source JSON_HELPER
set ::cmcpGuiTitleProbeRc [catch {::cmcpGuiTitleProbe::run} ::cmcpGuiTitleProbeResult]
set ::cmcpGuiTitleProbeFile [open RECEIPT_PART {WRONLY CREAT EXCL}]
try {
 fconfigure $::cmcpGuiTitleProbeFile -encoding utf-8 -translation lf
 if {$::cmcpGuiTitleProbeRc} {set ::cmcpGuiTitleProbeData null;set ::cmcpGuiTitleProbeError $::cmcpGuiTitleProbeResult} else {set ::cmcpGuiTitleProbeData $::cmcpGuiTitleProbeResult;set ::cmcpGuiTitleProbeError ""}
 puts $::cmcpGuiTitleProbeFile [cmcp::obj pid [pid] caught $::cmcpGuiTitleProbeRc error [cmcp::q $::cmcpGuiTitleProbeError] saveCalled false data $::cmcpGuiTitleProbeData]
} finally {close $::cmcpGuiTitleProbeFile}
file rename RECEIPT_PART RECEIPT
'''


def probe(binding: Path, expected_ini: Path, output: Path, wait_seconds=15):
    config = json.loads(binding.read_text(encoding='utf-8'))
    executable = Path(config['expectedExecutable']).resolve(strict=True)
    design = Path(config['expectedDesign']).resolve(strict=True)
    if process_image(config['expectedPid']) != executable or sha256(executable) != config['executableFingerprint']:
        raise ValueError('Capture process identity changed')
    before = sha256(design)
    if before != config['sourceFingerprint']:
        raise ValueError('Bound source changed')
    expected_ini = expected_ini.resolve(strict=True)
    output = output.resolve()
    output.mkdir(exist_ok=False)
    receipt = output/'native.json'
    substitutions = {
        'EXPECTED_PID': str(config['expectedPid']),
        'EXPECTED_INI': tcl_string(expected_ini.as_posix()),
        'EXPECTED_DESIGN': tcl_string(design.as_posix()),
        'JSON_HELPER': tcl_string((Path(__file__).resolve().parents[1]/'src/cadence_mcp/adapters/json.tcl').as_posix()),
        'RECEIPT': tcl_string(receipt.as_posix()),
        'RECEIPT_PART': tcl_string((output/'native.json.part').as_posix()),
    }
    import re
    code = re.sub(r'\b('+'|'.join(substitutions)+r')\b', lambda m: substitutions[m[0]], SCRIPT)
    payload = output/'probe.tcl'
    payload.write_text(code, encoding='utf-8')
    wrapper = output/'invoke.tcl'
    wrapper.write_text('source '+tcl_string(payload.as_posix())+'\n', encoding='utf-8')
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    child = subprocess.Popen([str(executable), str(wrapper)], startupinfo=startup)
    end = time.monotonic()+wait_seconds
    while not receipt.exists():
        if time.monotonic() >= end:
            raise TimeoutError('No editor receipt; inspect modal/context state before any retry')
        time.sleep(.1)
    native = json.loads(receipt.read_text(encoding='utf-8'))
    report = {'native': native, 'sourceSha256': before, 'sourceUnchanged': sha256(design) == before,
              'saveCalled': False, 'appOwnedSessionPreserved': True, 'launcherPid': child.pid}
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('binding', 'expected-ini', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--wait-seconds', type=int, choices=range(1, 61), default=15)
    args = parser.parse_args()
    result = probe(args.binding, args.expected_ini, args.output, args.wait_seconds)
    print(json.dumps({'caught': result['native']['caught'], 'sourceUnchanged': result['sourceUnchanged'],
                      'output': str(args.output)}, ensure_ascii=False))
    raise SystemExit(0 if not result['native']['caught'] and result['sourceUnchanged'] else 1)
