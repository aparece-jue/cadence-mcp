"""Native H02 expansion diagnostic after iterator-based page loading, without saving."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser();p.add_argument('--install-root',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=a.source.resolve();before=sha256(source);assert before=='1baf1c3e652a8d806801f098b4d14dc4fc8189d5f3b2472c513529c0235063b7';root=a.output.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(root,),40);reader=(ADAPTERS/'inspect_occurrence_nets.tcl').read_text();report={'sourceSha256':before,'saveCalled':False,'cases':{}}
base='''
    set pf [open [file join [file dirname $output] phases.log] {WRONLY CREAT EXCL}]
    proc hphase {name} {global pf;puts $pf $name;flush $pf}
    hphase iterate_schematics
    set vs [DboState];set vi [$d NewViewsIter $vs $::IterDefs_SCHEMATICS];cmcp::check $vs
    set hs {}
    try {
      for {set v [$vi NextView $vs]} {$v ne "NULL"} {set v [$vi NextView $vs]} {
        cmcp::check $vs;set sch [DboViewToDboSchematic $v];lappend hs $sch
        set name [cmcp::cs ""];cmcp::check [$sch GetName $name];hphase "load_pages:[cmcp::str $name]"
        set ps [DboState];set pi [$sch NewPagesIter $ps];cmcp::check $ps
        try {for {set page [$pi NextPage $ps]} {$page ne "NULL"} {set page [$pi NextPage $ps]} {cmcp::check $ps;set pn [cmcp::cs ""];cmcp::check [$page GetName $pn];hphase "page:[cmcp::str $pn]"}} finally {delete_DboSchematicPagesIter $pi}
      }
    } finally {delete_DboLibViewsIter $vi}
'''
for mode in ('pages-only','expand-after-pages'):
 case=root/mode;case.mkdir();target=case/'design.dsn';shutil.copyfile(source,target);output=case/'native.json';extra=base
 if mode=='expand-after-pages':extra+='''
    foreach sch $hs {hphase "expand:[$sch IsExpanded]";cmcp::check [$sch Expand];hphase expanded}
'''
 extra+='    hphase occurrence_reader\n    close $pf\n'
 marker='    set ro [$d GetRootOccurrence $state]';assert reader.count(marker)==1
 text=reader.replace('source [file join [file dirname [info script]] json.tcl]','source '+tcl_string((ADAPTERS/'json.tcl').as_posix())).replace(marker,extra+marker);script=case/'probe.tcl';script.write_text(text,encoding='utf8')
 process=run_owned_process([a.install_root/'tcltk/bin/tclsh.exe',script,a.install_root,target,output],case,process_env(cfg),40)
 row={'process':process,'phases':(case/'phases.log').read_text() if (case/'phases.log').exists() else '', 'sourceAndCopyUnchanged':sha256(source)==before and sha256(target)==before}
 if output.exists():
  data=json.loads(output.read_text());row.update(occurrenceCount=data['occurrenceCount'],flatNetCount=data['flatNetCount'],pinCount=len(data['pins']))
 if Path(str(output)+'.error.json').exists():row['nativeError']=json.loads(Path(str(output)+'.error.json').read_text())
 report['cases'][mode]=row;print(json.dumps({mode:row}),flush=True)
report['sourceUnchanged']=sha256(source)==before;(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');assert report['sourceUnchanged'] and all(r['sourceAndCopyUnchanged'] for r in report['cases'].values())
