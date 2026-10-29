"""Private native OLB XML diagnostic for the unresolved font quality persistence issue."""
import json,shutil,traceback,xml.etree.ElementTree as ET
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
r=Path(__file__).resolve().parents[1];root=r/'.local/font-xml-v2-20261029';root.mkdir(exist_ok=False);original=r/'.local/COMMENT-FONT-TRACE-V2-20261024.OLB';before=sha256(original);source=root/'input.olb';shutil.copy2(original,source)
expected={'originalRequestedQualities':list(range(7)),'existingReopenedQualities':[1]*7,'fullQualityAcceptance':False,'purpose':'Inspect exchange representation, not certify DSN/OLB or XML roundtrip preservation'};(root/'expected.json').write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8');oracle=sha256(root/'expected.json')
code=r'''lassign $argv install library xml output helper
source $helper
load [file join $install tools bin orDb_Dll_Tcl64.dll] DboTclWriteBasic
set visible [expr {[llength [info commands XMATIC_OLB2XML]]==1}];set failed true;set stateCode null
set rc [catch {if {!$visible} {error documented_global_XMATIC_OLB2XML_not_bound};set s [XMATIC_OLB2XML $library $xml];set stateCode [$s Code];set failed [expr {[$s Failed]?"true":"false"}]} message]
set f [open $output {WRONLY CREAT EXCL}];puts $f [cmcp::obj globalCommandVisible [expr {$visible?"true":"false"}] failed $failed code $stateCode error [cmcp::q [expr {$rc?$message:""}]]];close $f
if {$rc || $failed} {exit 1}
'''
script=root/'probe.tcl';script.write_text(code,encoding='utf-8');cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),45);report={'passed':False,'fontQualityPersistenceAccepted':False,'sourceBefore':before}
try:
 p=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script,cfg.install_root,source,root/'library.xml',root/'native.json',ADAPTERS/'json.tcl'],root,process_env(cfg),45);report['process']=p;report['native']=json.loads((root/'native.json').read_text(encoding='utf-8'));assert p['returnCode']==0 and p['remainingOwnedProcesses']==0
 tree=ET.parse(root/'library.xml');fonts=[{'tag':e.tag,'attributes':e.attrib} for e in tree.iter() if 'font' in e.tag.lower()];assert fonts;report.update(passed=True,fontElements=fonts,xmlBytes=(root/'library.xml').stat().st_size,qualityNamedAttributes=sorted({k for e in tree.iter() for k in e.attrib if 'quality' in k.lower()}))
except BaseException:report['error']=traceback.format_exc()
report['originalSourceUnchanged']=sha256(original)==before;report['copiedSourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['passed']=report['passed'] and report['originalSourceUnchanged'] and report['copiedSourceUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report),flush=True)
