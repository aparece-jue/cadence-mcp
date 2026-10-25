"""Shared NC read ownership and unit-edit preflight refusal on a private fixture."""
import argparse,asyncio,json,os,shutil,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.capture_edit import definition_baseline
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);before=sha256(source);target=root/'design.dsn';shutil.copyfile(source,target);cfg=Config(a.install_root,root,(root,),60)
def inspect(path,label):
 out=root/(label+'.json');run_tcl(cfg,'inspect.tcl',[str(path),str(out),'100000'],root);return json.loads(out.read_text(encoding='utf-8'))
baseline=inspect(source,'baseline');report={'passed':False,'sourceBefore':before,'scope':'shared NC definition reading and edit refusal; no public shared-NC writer'};process=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_shared_unit_nc.tcl'),str(cfg.install_root),str(target),str(root/'receipt.json')],root,process_env(cfg),60);report['process']=process;report['receipt']=json.loads((root/'receipt.json').read_text(encoding='utf-8'));write_json(root/'native-report.json',report)
async def main():
 try:
  assert process['returnCode']==0 and report['receipt']['saved'];saved=sha256(target);after=inspect(target,'after');assert definition_baseline(after)==definition_baseline(baseline);env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(root)],env=env)
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(target)}))['workspaceId']}))['sessionId'];rows=(await call('capture_query_connections',{'sessionId':sid,'entity':'nc','limit':1000}))['items'];assert len(rows)==1;nc=rows[0]['attributes'];assert nc['reference']=='U501' and nc['number']=='8' and nc['hotSpot']==[1000,680];pins=(await call('capture_query',{'sessionId':sid,'entity':'pin','scope':{'kind':'design'},'limit':1000}))['items'];pin=next(p for p in pins if p['objectId']==nc['pinId']);assert pin['partId']==nc['partId'] and pin['number']=='8';pageid=pin['pageId'];remaining=[{'pinId':p['objectId'],'connected':p['connected'],'net':p['net'] if p['connected'] else None} for p in pins if p['pageId']==pageid and p['partId']!=pin['partId']];v=await client.call_tool('capture_plan_part_edit',{'sessionId':sid,'partId':pin['partId'],'operation':'delete','expectedConnections':[],'expectedUnitConnections':remaining});assert v.is_error and v.structured_content['error']['code']=='attached_nc_unsupported';jobs=await call('capture_part_edit_jobs',{});assert len(jobs['jobs'])==0;report.update(sharedNcRows=1,ownerPinIdMatched=True,unitDeleteRefusedBeforePlan=True)
  report['hashesUnchanged']=sha256(source)==before and sha256(target)==saved;report['passed']=report['hashesUnchanged'] and process['remainingOwnedProcesses']==0
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
