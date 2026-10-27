"""Fault after real native completion; preserve fence, recover existing bytes only."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from unittest.mock import patch
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_bus_create import CaptureBusCreates
from cadence_mcp.editor_wire_host import EditorWireHost
from cadence_mcp.bridge_rpc import GuiBridgeManager
from cadence_mcp.native_host_fence import read_fence
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/bus-observer-loss-v2-20261027';root.mkdir(exist_ok=False)
original=json.loads((r/'.local/design-create-mcp-20261023/work/isolated-jobs/capture_wire_add/plan-4c588c62149c485491006523e9b80218/plan.json').read_text(encoding='utf-8'))['plan']['payload']
source=r/'.local/editor-wire-original-pins-mcp-20261027/work/isolated-jobs/capture_wire_add/plan-53c20e2f539d46738249f4c5902f9fc7/design.dsn';before=sha256(source);assert before=='8f5e2b644060e80907b79201805028c58f520971d4c25e419b2d767282ae47c9';project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';bindings=r/'.local/editor-wire-fresh-binding-20261027'
config=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(source.parent,project.parent),30,gui_bridge_roots=(bindings,))
capture=CaptureService(config);gui=GuiBridgeManager((),(bindings,));writer=CaptureBusCreates(config,capture,gui)
report={'passed':False,'sourceBefore':before,'checks':{}}
def attach():return gui.attach(gui.discover()['instances'][0]['instanceId'])['sessionId']
try:
 sid=capture.open(capture.create_workspace(str(source))['workspaceId'])['sessionId'];page=capture.sessions[sid]['data']['page'][0]['objectId'];gsid=attach()
 def plan(g):return writer.plan(sid,g,str(project),page,'FAULT',1,0,[200,600],[200,900],[{'index':i,'entryPoint':[200,620+50*i],'endPoint':[220,640+50*i],'wireEnd':[400,640+50*i],'expectedBusAttached':True} for i in range(2)],original['expectedConnections'])
 planned=plan(gsid);key={k:planned[k] for k in ('planId','planDigest')};d,_,row=writer._load(key['planId']);binding=writer.editor_host.binding(row['plan']['payload']['editorHost'])
 with patch.object(writer.editor_host,'observe',side_effect=CadenceError('injected_observer_loss','After real adapter receipt, before restored-host observation')):
  try:writer.apply(**{'plan_id':key['planId'],'plan_digest':key['planDigest'],'idempotency_key':'observer-loss'});raise AssertionError('injection not reached')
  except CadenceError as error:assert error.code=='injected_observer_loss',error.code
 receipt=json.loads((d/'native-result.json').read_text(encoding='utf-8'));assert receipt['saved'] and receipt['hostRestored'] and receipt['invocationReturned']
 assert read_fence(binding)['jobId']==key['planId'];assert not (d/'host-after.json').exists()
 fixed={p.name:sha256(p) for p in d.iterdir() if p.is_file() and p.name!='plan.json'}
 try:writer.apply(key['planId'],key['planDigest'],'observer-loss');raise AssertionError('native replay allowed')
 except CadenceError as error:assert error.code=='write_not_replayed'
 try:plan(attach());raise AssertionError('unresolved host fence ignored')
 except CadenceError as error:assert error.code=='bridge_busy',error.code
 report['checks'].update(realNativeCompletionBeforeInjectedObserverLoss=True,fenceRetained=True,mutationReplayRefused=True,newHostDispatchBlocked=True)
 async def recover():
  env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(config.install_root),'--workspace-root',str(config.workspace_root),'--read-root',str(source.parent),'--read-root',str(project.parent),'--gui-bridge-root',str(bindings),'--timeout-seconds','30'],env=env)
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   result=await client.call_tool('capture_recover_bus_create',key);assert not result.is_error,result.structured_content;data=result.structured_content['data'];assert data['state']=='verified_recovered' and not data['mutationReplayed']
   result=await client.call_tool('capture_open_edit_result',{**key,'kind':'bus_create'});assert not result.is_error,result.structured_content
   return data
 report['recovered']=asyncio.run(recover());assert read_fence(binding) is None
 assert all(sha256(d/name)==fingerprint for name,fingerprint in fixed.items())
 report['checks'].update(freshMcpVerifyOnlyRecover=True,originalNativeFilesUnchanged=True,fenceReleasedAfterRestoredHostProof=True)
 report['passed']=True
except BaseException:report['error']=traceback.format_exc()
report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='recovered'}),flush=True)
