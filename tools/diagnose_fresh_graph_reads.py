"""Trace failing reader calls on saved graphs without editing source/readers."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--initialize',choices=('none','root','occurrence','both'),default='none')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);before=sha256(source);cfg=Config(a.install_root,root,(source.parent,),60)
s=(ADAPTERS/'inspect_net_symbol_bindings.tcl').read_text(encoding='utf-8')
initialization=''
if a.initialize in ('root','both'):initialization+=' set state [DboState];set phase initialize_root;set initialized [$d GetRootSchematic $state];cmcp::check $state\n'
if a.initialize in ('occurrence','both'):initialization+=' set state [DboState];set phase initialize_occurrence;set initialized [$d GetRootOccurrence $state];cmcp::check $state\n'
s=s.replace(' set vi [$d NewViewsIter',initialization+' set state [DboState];set vi [$d NewViewsIter')
for needle,label in [('set vi [$d NewViewsIter','view_iterator'),('set pi [$s NewPagesIter','page_iterator'),('set pn [cmcp::cs','page_name'),('set sn [cmcp::cs','schematic_name'),('set it [$p NewPartInstsIter','part_iterator'),('set pins [$part NewPinsIter','pin_iterator')]:s=s.replace(needle,'set phase '+label+';'+needle)
s=s.replace('set phase symbol_bindings','set phase "symbol_${kind}_iterator"')
s=s.replace('cmcp::check $state;cmcp::tick\n        set name', 'cmcp::check $state;cmcp::tick;set phase "symbol_${kind}_name"\n        set name')
s=s.replace('lassign [cmcp::group $obj]', 'set phase "symbol_${kind}_net";lassign [cmcp::group $obj]')
s=s.replace('set h [$obj GetOffsetHotSpot', 'set phase "symbol_${kind}_hotspot";set h [$obj GetOffsetHotSpot')
# Make parent iterator advance boundaries observable after child iterator EOF.
s=s.replace('{set p [$pi NextPage $state]}', '{set phase next_page;set p [$pi NextPage $state]}')
s=s.replace('{set v [$vi NextView $state]}', '{set phase next_view;set v [$vi NextView $state]}')
s=s.replace('2047','8191').replace('source [file join [file dirname [info script]] json.tcl]', 'source {'+str(ADAPTERS/'json.tcl').replace('\\','/')+'}')
script=root/'traced_reader.tcl';script.write_text(s,encoding='utf-8');out=root/'bindings.json'
process=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(script),str(cfg.install_root),str(source),str(out)],root,process_env(cfg),60)
report={'passed':process['returnCode']==0,'initialize':a.initialize,'process':process,'sourceBefore':before,'sourceAfter':sha256(source),'sourceUnchanged':before==sha256(source),'tracedReaderSha256':sha256(script)}
if Path(str(out)+'.error.json').exists():report['nativeError']=json.loads(Path(str(out)+'.error.json').read_text())
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
