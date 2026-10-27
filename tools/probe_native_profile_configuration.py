"""Inspect native merged profile/design/global configuration on a private snapshot."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture_pspice_project import describe_project
from cadence_mcp.environment import process_env,ADAPTERS
from cadence_mcp.gui_loader import tcl_string
from cadence_mcp.process_tree import run_owned_process

p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','source-project','source-profile','source-ini'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);project=a.source_project.resolve(strict=True);profile=a.source_profile.resolve(strict=True);ini=a.source_ini.resolve(strict=True)
desc,opj=describe_project(project.read_bytes(),profile.read_bytes(),project.name)
design=(project.parent/desc['designTarget']).resolve(strict=True)
assert profile==(project.parent/desc['profileTarget']).resolve(strict=True)
before={str(x):sha256(x) for x in (project,profile,design,ini)}
for relative,raw in [(desc['projectTarget'],opj),(desc['profileTarget'],profile.read_bytes()),(desc['designTarget'],design.read_bytes())]:
 target=root/'project'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
private_ini=root/'selected.ini';private_ini.write_bytes(ini.read_bytes());cfg=Config(a.install_root,root/'work',(root,),30)
code='''source @HELPER@
foreach {dll init} {orPSpiceExplorer64.dll orPSpiceExplorer orCommonTcl64.dll orCommonTcl orSimSrvr64.dll orSimSrvr} {load [file join @INSTALL@ tools bin $dll] $init}
set obj {};set phase construct
set caught [catch {
 set empty {};set obj [new_CorSimSrvr $empty 2]
 set phase ini;CorSimSrvr_setIniFile $obj @INI@
 set phase load_profile;set loaded [$obj loadProfile @PROFILE@]
 set before {};set beforeStatus [$obj readSettingsToJSON before]
 set phase read_libinc;set libraries [$obj readSettingsLibinc @PROJECT@ @PROFILE@]
 set after {};set afterStatus [$obj readSettingsToJSON after]
 set phase returned
 set result [cmcp::obj pid [pid] returned true loadResult [cmcp::q $loaded] libincResult [cmcp::q $libraries] beforeStatus [cmcp::q $beforeStatus] afterStatus [cmcp::q $afterStatus] beforeJSON [cmcp::q $before] afterJSON [cmcp::q $after]]
} message]
if {$obj ne {}} {catch {delete_CorSimSrvr $obj}}
if {$caught} {set result [cmcp::obj returned false phase [cmcp::q $phase] error [cmcp::q $message]]}
set f [open @OUTPUT@ {WRONLY CREAT EXCL}];fconfigure $f -encoding utf-8;puts $f $result;close $f
if {$caught} {exit 1}
'''
for k,v in {'HELPER':ADAPTERS/'json.tcl','INSTALL':cfg.install_root,'INI':private_ini,'PROFILE':root/'project'/desc['profileTarget'],'PROJECT':root/'project'/desc['projectTarget'],'OUTPUT':root/'native-result.json'}.items():code=code.replace('@'+k+'@',tcl_string(v.as_posix()))
script=root/'inspect.tcl';script.write_text(code,encoding='utf-8');process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script],root,process_env(cfg),30)
raw=json.loads((root/'native-result.json').read_text(encoding='utf-8')) if (root/'native-result.json').exists() else None
report={'passed':False,'process':process,'sourceFingerprints':before,'sourcesUnchanged':all(sha256(Path(x))==h for x,h in before.items()),'selectedIniCopiedByteForByte':sha256(private_ini)==before[str(ini)],'native':raw}
if raw and raw.get('returned'):
 for when in ('before','after'):
  settings=json.loads(raw[when+'JSON']);report[when+'ConfigFiles']=settings.get('ConfigFiles')
 report['passed']=process['state']=='exited' and process['returnCode']==0 and raw['loadResult']=='0' and raw['libincResult']=='0' and report['sourcesUnchanged'] and report['selectedIniCopiedByteForByte']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:report.get(k) for k in ('passed','sourcesUnchanged','beforeConfigFiles','afterConfigFiles')}))
if not report['passed']:raise SystemExit(1)
