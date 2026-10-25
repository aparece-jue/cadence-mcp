"""Actual MCP OLB creation: positive per-device swap IDs and shared power maps."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
from library_create_fixtures import pin,symbol,mapping
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
def gate(cell,name,wide=30,ground=False):
 pins=[pin(0,'IN0',0,[-10,-10],[-wide,-10]),pin(3,'IN1',0,[-10,10],[-wide,10]),pin(7,'OUT',2,[10,0],[wide,0]),pin(12,'VCC',7,[0,-10],[0,-30],False)]
 if ground:pins.append(pin(15,'GND',7,[0,10],[0,30],False))
 return symbol(cell,name,pins)
def dev(designator,position,cell,first,swap,ground=False):
 items=[{**mapping(0,first),'swapId':swap},{**mapping(3,first+1),'swapId':swap},mapping(7,first+2),mapping(12,8,True)]
 if ground:items.append(mapping(15,7,True))
 return {'designator':designator,'position':position,'cellName':cell,'mapping':items}
hom={'packageName':'MCP_SWAP_DUAL','referenceTemplate':'U?','footprint':'MCP_SWAP_DUAL_FP','expectedHomogeneous':True,'symbols':[gate('GATE_CELL','GATE.Normal')],'devices':[dev('A',0,'GATE_CELL',1,7),dev('B',1,'GATE_CELL',4,11)]}
hetero={'packageName':'MCP_SWAP_HETERO','referenceTemplate':'U?','footprint':'MCP_SWAP_HETERO_FP','expectedHomogeneous':False,'symbols':[gate('A_CELL','A.Normal',30,True),gate('B_CELL','B.Normal',40,True),{'cellName':'POWER_CELL','partName':'POWER.Normal','pins':[pin(0,'VCC',7,[0,-10],[0,-30]),pin(1,'GND',7,[0,10],[0,30])],'lines':[]}],'devices':[dev('A',0,'A_CELL',1,101,True),dev('B',1,'B_CELL',4,202,True),{'designator':'P','position':2,'cellName':'POWER_CELL','mapping':[mapping(0,8,True),mapping(1,7,True)]}]}
cases={'homogeneous':hom,'heterogeneous':hetero};expected_path=root/'expected.json';expected_path.write_text(json.dumps(cases,indent=2),encoding='utf-8');expected_sha=sha256(expected_path);env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(root),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'scope':'declared OLB swapId metadata/shared power/device pin maps only; not a physical pin-swap or multiunit DSN placement acceptance','cases':[],'checks':{}};plans=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;return v.structured_content['data']
   report['tools']=len((await client.list_tools()).tools);assert report['tools']==137
   for name,spec in cases.items():
    row={'name':name,'passed':False};report['cases'].append(row);plan=await call('capture_plan_library_create',{'spec':spec});key={k:plan[k] for k in ('planId','planDigest')};plans.append((name,key));result=await call('capture_apply_library_create',{**key,'idempotencyKey':name});opened=await call('capture_open_created_library',key);pins=(await call('capture_library_query',{'libraryId':opened['libraryId'],'entity':'pin','limit':1000}))['items'];assert result['declaredGraphVerified'] and result['independentReopenVerified'];assert len(pins)==(8 if name=='homogeneous' else 12) and result['uniquePhysicalPadCount']==(7 if name=='homogeneous' else 8)
    row.update(passed=True,plan=plan,result=result,pins=pins,logicalRows=len(pins),physicalPads=result['uniquePhysicalPadCount']);await call('capture_library_close',{'libraryId':opened['libraryId']})
   # Repeated physical pads must explicitly agree on shared/electrical/swap metadata.
   bad=copy.deepcopy(hetero);bad['devices'][2]['mapping'][0]['swapId']=999
   v=await client.call_tool('capture_plan_library_create',{'spec':bad});assert v.is_error and v.structured_content['error']['code']=='invalid_library_spec';report['checks']['conflicting_shared_swap_group_refused']=True
   bad=copy.deepcopy(hom);bad['devices'][1]['mapping'][0]['position']=12
   assert (await client.call_tool('capture_plan_library_create',{'spec':bad})).is_error;report['checks']['duplicate_logical_position_refused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   for name,key in plans:
    v=await client.call_tool('capture_apply_library_create',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_library_create',key)).is_error;v=await client.call_tool('capture_open_created_library',key);assert not v.is_error
   report['checks']['fresh_idempotent_recover_open_without_replay']=True
  report['passed']=sha256(expected_path)==expected_sha
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
