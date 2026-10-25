"""Read-only native definition unit identity; validates against the snapshot."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
config=Config(a.install_root,root/'work',(a.source.parent,),60);cap=CaptureService(config)
report={'passed':False,'sourceHashBefore':sha256(a.source)}
try:
    opened=cap.open(cap.create_workspace(str(a.source))['workspaceId']);session=cap.sessions[opened['sessionId']]
    process=run_owned_process([str(config.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'inspect_reference_units.tcl'),str(config.install_root),str(session['design']),str(root/'native.json')],root,process_env(config),60);report['process']=process
    actual=json.loads((root/'native.json').read_text(encoding='utf-8'))
    assert process['state']=='exited' and process['returnCode']==0,actual
    assert {r['partId']:r['reference'] for r in actual}=={r['objectId']:r['reference'] for r in session['data']['part']}
    assert all(r['packageSize']>=1 and r['packageName'] for r in actual if r['kind']=='placed')
    report.update(passed=True,rows=actual,definitionOnly=True,occurrenceUnitOverridesVerified=False)
except BaseException as error:report.update(errorType=type(error).__name__,error=str(error))
report['sourceHashAfter']=sha256(a.source);report['passed']=report['passed'] and report['sourceHashBefore']==report['sourceHashAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
raise SystemExit(0 if report['passed'] else 1)
