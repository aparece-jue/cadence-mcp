from pathlib import Path
import argparse,json,shutil
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-dat'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source_dat.resolve(strict=True);before=sha256(source);cfg=Config(a.install_root,root/'work',(source.parent,),45)
base=(ADAPTERS/'probe_digital_dat.tcl').read_text(encoding='utf-8').replace('[file dirname [info script]]','{'+ADAPTERS.as_posix()+'}')
needle=' set closeAttempted 1;reader close'
assert needle in base
base=base.replace(needle,''' set header [reader getJSON]
 if {[string length $header]>16777216} {error header_limit}
 set hf [open [file join [file dirname $output] native-header.json] {WRONLY CREAT EXCL}];fconfigure $hf -encoding utf-8 -translation lf;puts -nonewline $hf $header;close $hf
'''+needle)
rows=[]
for mode in ('single_trace','single_no_trace','double_trace'):
 directory=root/mode;directory.mkdir();copied=directory/'copied.dat';shutil.copyfile(source,copied);text=base
 if mode=='single_no_trace':text=text.replace('trace add execution reader {enter leave} traceReader','')
 if mode=='double_trace':text=text.replace('close $traceLog\nset f','puts $traceLog before_second_close;flush $traceLog\ncatch {reader close}\nclose $traceLog\nset f')
 script=directory/'probe.tcl';script.write_text(text,encoding='utf-8')
 process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script,cfg.install_root,copied,directory/'native.json'],directory,process_env(cfg),45)
 row={'mode':mode,'process':process,'sourceUnchanged':sha256(source)==before,'copyUnchanged':sha256(copied)==before}
 if (directory/'native-header.json').exists():
  raw=(directory/'native-header.json').read_text(encoding='utf-8');row['headerLength']=len(raw)
  try:header=json.loads(raw);row['validHeaderJson']=True;row['headerShape']=list(header)[:12] if isinstance(header,dict) else [type(header).__name__,len(header)]
  except ValueError as error:row.update(validHeaderJson=False,headerError=str(error),headerPrefix=raw[:200])
 if (directory/'trace.log').exists():row['lastTrace']=(directory/'trace.log').read_text(encoding='utf-8').splitlines()[-3:]
 rows.append(row);print(json.dumps(row),flush=True)
(root/'report.json').write_text(json.dumps({'scope':'controlled close lifecycle/native header comparison','rows':rows},indent=2),encoding='utf-8')
