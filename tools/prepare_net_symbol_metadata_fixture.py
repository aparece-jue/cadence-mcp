"""Create a private bound offpage metadata holdout; all original fixtures remain unchanged."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for name in ('install-root','fixture-root','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.output.resolve();root.mkdir(exist_ok=False);before={p:sha256(p) for p in [a.fixture_root/k/'design.dsn' for k in ('global','offpage')]}
for source in before:
 target=root/source.parent.name/'design.dsn';target.parent.mkdir();shutil.copyfile(source,target)
expected={'user':{'name':'NOTE','value':'保留 Ω 00123'},'display':{'name':'NOTE','location':[-7,13],'rotation':1,'displayType':3,'color':8,'font':['Arial',-13,0,0,0,700,1,1,0,0,7,0,1,16],'fontDefault':0},'kind':'offpage','name':'MCP_LINK','hotspot':[240,310]};(root/'expected-metadata.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2)+'\n',encoding='utf8');oracle=sha256(root/'expected-metadata.json')
code=r'''lassign $argv install design output helper qualified
source $helper
source $qualified
proc cmcp::cs {v} {DboTclHelper_sMakeCString $v}
proc cmcp::str {v} {DboTclHelper_sGetConstCharPtr $v}
proc cmcp::check {s} {if {[$s Failed]} {error "dbo_[$s Code]"}}
set session "";set rc [catch {
 load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
 set session [DboTclHelper_sCreateSession];set st [DboState];set d [$session GetDesignAndSchematics [cmcp::cs $design] $st];cmcp::check $st
 lassign [cmcp::qualifiedPage $d HALFADD MCP_PLACE] sch page
 set st [DboState];set it [$page NewOffPageConnectorsIter $st $::IterDefs_ALL];cmcp::check $st;set found {}
 try {for {set obj [$it NextOffPageConnector $st]} {$obj ne "NULL"} {set obj [$it NextOffPageConnector $st]} {cmcp::check $st;set name [cmcp::cs ""];cmcp::check [$obj GetName $name];if {[cmcp::str $name] eq "MCP_LINK"} {lappend found $obj}}} finally {delete_DboPageOffPageConnectorsIter $it}
 if {[llength $found]!=1} {error ambiguous_fixture_symbol};set obj [lindex $found 0];set st [DboState]
 set prop [$obj NewUserProp [cmcp::cs NOTE] [cmcp::cs "\u4fdd\u7559 \u03a9 00123"] $st];cmcp::check $st;if {$prop eq "NULL"} {error missing_user}
 set font [DboTclHelper_sMakeLOGFONT Arial -13 0 0 0 700 1 1 0 0 7 0 1 16]
 set display [$obj NewDisplayProp $st [cmcp::cs NOTE] [DboTclHelper_sMakeCPoint -7 13] 1 $font 8];cmcp::check $st;if {$display eq "NULL"} {error missing_display};cmcp::check [$display SetDisplayType 3]
 cmcp::check [$page MarkModified];cmcp::check [$sch MarkModified $page];cmcp::check [$sch SavePage $page];cmcp::check [$d SaveSchematic $sch];cmcp::check [$session MarkAllLibForSave $d];cmcp::check [$session SaveDesign $d]
} message]
if {$session ne ""} {catch {delete_DboSession $session}}
set f [open $output {WRONLY CREAT EXCL}];puts $f [cmcp::obj saved [expr {!$rc}] message [cmcp::q $message]];close $f
if {$rc} {exit 1}
'''.replace(chr(92)*2+'u',chr(92)+'u');script=root/'fixture.tcl';script.write_text(code,encoding='utf8');cfg=Config(a.install_root,root/'work',(root,),60);process=run_owned_process([a.install_root/'tcltk/bin/tclsh.exe',script,a.install_root,root/'offpage/design.dsn',root/'native.json',ADAPTERS/'json.tcl',ADAPTERS/'dbo_qualified_page.tcl'],root,process_env(cfg),60);report={'passed':False,'process':process,'native':json.loads((root/'native.json').read_text()),'originalInputsUnchanged':all(sha256(p)==h for p,h in before.items()),'oracleUnchanged':sha256(root/'expected-metadata.json')==oracle}
try:
 assert process['returnCode']==0 and report['native']['saved'];out=root/'metadata.json';run_tcl(cfg,'inspect_net_symbol_metadata.tcl',[str(root/'offpage/design.dsn'),str(out),'HALFADD','MCP_PLACE','offpage','0','MCP_LINK','240','310'],root);metadata=json.loads(out.read_text())['metadata'];user,=[r for r in metadata['user'] if r['name']=='NOTE'];display,=[r for r in metadata['display'] if r['name']=='NOTE'];assert all(user[k]==v for k,v in expected['user'].items());assert all(display[k]==v for k,v in expected['display'].items()),display;report['passed']=report['originalInputsUnchanged'] and report['oracleUnchanged'];report['metadata']=metadata
finally:(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'passed':report['passed'],'native':report['native']}));assert report['passed']
