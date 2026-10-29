"""Read-only native titleblock dynamic-field diagnostic on the fixed private design."""
import json,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/titleblock-fields-20261029';root.mkdir(exist_ok=False)
source=r/'.local/titleblock-curves-20261029/design.dsn';before=sha256(source)
expected={'pages':['MAIN','OTHER','EMPTY'],'titleblocks':9,'designPageCount':3,'designFileStem':'design','semanticsNeedIndependentVerification':['designName','pageNumber','pageSize','effectiveProperties']}
(root/'expected.json').write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8');oracle=sha256(root/'expected.json')
code=r'''lassign $argv install design output helper
source $helper
proc cs {v} {DboTclHelper_sMakeCString $v}
proc str {v} {DboTclHelper_sGetConstCharPtr $v}
proc ck {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set session [DboTclHelper_sCreateSession];set rows {};set rc [catch {
 set st [DboState];set d [$session GetDesignAndSchematics [cs $design] $st];ck $st;set s [$d GetRootSchematic $st];ck $st
 foreach pageName {MAIN OTHER EMPTY} {
  set p [$s GetPage [cs $pageName] $st];ck $st;set it [$p NewTitleBlocksIter $st];ck $st
  try {for {set obj [$it NextTitleBlock $st]} {$obj ne "NULL"} {set obj [$it NextTitleBlock $st]} {
   ck $st;set fields {};set name [cs ""];ck [$obj GetName $name]
   foreach method {GetDesignName GetDesignFileName GetSourceSymbolName GetPageSize} {
    set value [cs ""];set status [$obj $method $value]
    lappend fields [cmcp::obj method [cmcp::q $method] code [$status Code] failed [$status Failed] value [cmcp::q [str $value]]]
   }
   foreach method {GetPageCount GetPageNumber} {
    set status [DboState];set value [$obj $method $status]
    lappend fields [cmcp::obj method [cmcp::q $method] code [$status Code] failed [$status Failed] value $value]
   }
   lappend rows [cmcp::obj page [cmcp::q $pageName] name [cmcp::q [str $name]] fields [cmcp::arr $fields]]
  }} finally {delete_DboPageTitleBlocksIter $it}
  if {[$st Failed] && [$st Code]!=1022} {error unexpected_iterator_end}
 }
} message]
catch {delete_DboSession $session}
set f [open $output {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts $f [cmcp::obj rows [cmcp::arr $rows] error [cmcp::q [expr {$rc?$message:""}]]];close $f
if {$rc} {exit 1}
'''
script=root/'probe.tcl';script.write_text(code,encoding='utf-8');cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(source.parent,),45)
report={'passed':False,'fullC05Accepted':False,'dynamicFieldSemanticsAccepted':False,'sourceBefore':before}
try:
 p=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script,cfg.install_root,source,root/'native.json',ADAPTERS/'json.tcl'],root,process_env(cfg),45);report['process']=p;assert p['returnCode']==0 and p['remainingOwnedProcesses']==0
 data=json.loads((root/'native.json').read_text(encoding='utf-8'));assert not data['error'] and len(data['rows'])==9
 report['allMethodsSucceeded']=all(not f['failed'] for row in data['rows'] for f in row['fields']);report['pageCountMatchesFrozenThree']=all(next(f['value'] for f in row['fields'] if f['method']=='GetPageCount')==3 for row in data['rows']);report['observedByPage']={name:data['rows'][next(i for i,x in enumerate(data['rows']) if x['page']==name)]['fields'] for name in ['MAIN','OTHER']};report['passed']=report['allMethodsSucceeded'] and report['pageCountMatchesFrozenThree']
except BaseException:report['error']=traceback.format_exc()
report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report),flush=True)
