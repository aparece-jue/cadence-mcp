"""Read native DRC configuration through actual authenticated MCP; no rule execution or saves."""
import argparse,asyncio,json,os,subprocess,sys,time
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.bridge_rpc import RpcConnection
from cadence_mcp.gui_loader import prepare_loader
from cadence_mcp.core import sha256
p=argparse.ArgumentParser();p.add_argument('--binding',type=Path,required=True);p.add_argument('--workspace-root',type=Path,required=True);a=p.parse_args();r=Path(__file__).resolve().parents[1];root=a.workspace_root.resolve();root.mkdir(parents=True,exist_ok=False);binding=a.binding.resolve();cfg=json.loads(binding.read_text(encoding='utf-8'));source=Path(cfg['expectedDesign']);before=sha256(source);report={'passed':False,'sourceBefore':before};hello=RpcConnection(binding).call('hello',{});assert not hello['data']['bindingLost'] and hello['data']['dirtyState']=='clean' and hello['data']['propertyPlanCount']==0
config,wrapper,receipt=prepare_loader(binding);startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0;child=subprocess.Popen([config['expectedExecutable'],str(wrapper)],startupinfo=startup);deadline=time.monotonic()+20
while not receipt.exists() and time.monotonic()<deadline:time.sleep(.1)
report['reloadAcknowledged']=receipt.exists();report['forwarderPid']=child.pid
if child.poll() is None:
 assert child.pid!=cfg['expectedPid'];child.terminate();child.wait(timeout=5);report['ownedForwarderTerminated']=True
else:report['forwarderExitCode']=child.returncode
assert receipt.exists(), 'No loader receipt; do not replay'
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(Path(cfg['expectedExecutable']).parents[2]),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--gui-bridge-config',str(binding)],env=env)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=60) as client:
   async def call(name,args):
    out=await client.call_tool(name,args)
    if out.is_error:raise AssertionError((name,out.structured_content))
    return out.structured_content['data']
   found=await call('capture_gui_instances',{});instance=next(x for x in found['instances'] if x['pid']==cfg['expectedPid']);assert 'drc_configuration' in instance['capabilities'];attached=await call('capture_gui_attach',{'instanceId':instance['instanceId'],'access':'read'});sid=attached['sessionId'];report['sessionId']=sid
   report['configuration']=await call('capture_gui_query',{'sessionId':sid,'entity':'drc_configuration'});again=await call('capture_gui_query',{'sessionId':sid,'entity':'drc_configuration'});assert again==report['configuration'];assert not again['rulesExecuted'] and not again['coverageVerified'];assert again['onlineElectricalRuleCount']==7;assert again['onlineElectricalEnabledCount']==0;assert again['ercMatrix']['OUT_PIN'][2]=='E'
   report['detached']=await call('capture_gui_detach',{'sessionId':sid});out=await client.call_tool('capture_gui_query',{'sessionId':sid,'entity':'drc_configuration'});assert out.is_error and out.structured_content['error']['code']=='session_lost';report['detachedSessionRefused']=True;report['repeatReadStable']=True;report['passed']=True
 except Exception as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error'),'sourceUnchanged':report['sourceUnchanged']}),flush=True)
asyncio.run(main())
