"""Verify the fixed native-profile script refuses existing CIR without overwriting."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env,ADAPTERS
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.process_tree import run_owned_process

p=argparse.ArgumentParser()
for name in ('accepted-root','workspace-root','install-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();source=a.accepted_root.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
cfg=Config(a.install_root,root/'work',(source,),15)
before={str(p):sha256(p) for p in source.rglob('*') if p.is_file()}
report={'passed':False,'cases':{}}
for label in ('before','after'):
 case=source/(label+'-native');accepted=json.loads((case/'report.json').read_text());assert accepted['passed']
 receipt=root/(label+'-refusal.json');script=root/(label+'-replay.tcl')
 code='source '+tcl_string((ADAPTERS/'json.tcl').as_posix())+'\n'
 code+='set refused [catch {source '+tcl_string((case/'probe.tcl').as_posix())+'} reason]\n'
 code+='set ack [open '+tcl_string(receipt.as_posix())+' {WRONLY CREAT EXCL}];puts $ack [cmcp::obj refused $refused reason [cmcp::q $reason]];close $ack\nif {$refused} {exit 1}\n'
 script.write_text(code,encoding='utf-8')
 result=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script],root,process_env(cfg),15)
 report['cases'][label]=result
 assert result['state']=='exited' and result['returnCode']==1,result
 refusal=json.loads(receipt.read_text());assert refusal=={'refused':1,'reason':'preexisting_profile_output'},refusal
 report['cases'][label]['refusal']=refusal
 assert {str(p):sha256(p) for p in source.rglob('*') if p.is_file()}==before,'Replay changed accepted native artifacts'
report['passed']=True;report['acceptedArtifactsUnchanged']=True
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
