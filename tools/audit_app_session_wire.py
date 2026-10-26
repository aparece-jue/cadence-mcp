"""Independent status audit of the app-owned wire experiment; no mutation/replay."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root','experiment-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);fixture=a.fixture_root.resolve();experiment=a.experiment_root.resolve();source=fixture/'MCP_HOST_WIRE.dsn';before=sha256(source);old=json.loads((experiment/'report.json').read_text(encoding='utf-8'));assert old['acknowledged'] and old['receipt']['saved'] and not old['passed'];cfg=Config(a.install_root,root/'work',(fixture,),60);output=root/'page-status.json';proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'probe_page_status.tcl',cfg.install_root,source,output],root,process_env(cfg),60);result={'passed':False,'process':proc,'sourceSha256':before,'experimentSha256':sha256(experiment/'report.json'),'noReplay':True}
if output.exists():result['pageStatus']=json.loads(output.read_text(encoding='utf-8'))
result['sourceUnchanged']=sha256(source)==before;result['controlSources']={n:sha256(Path(n)) for n in [str(fixture.parent/'capture-host-design-20261024/lowpassfilters.dsn'),str(fixture.parent/'drc-definition-fixture-20261026/MCP_DRC_ERROR.dsn')]};(root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
