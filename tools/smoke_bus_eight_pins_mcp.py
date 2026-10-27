"""Four real resistors: eight predeclared pins, member order and negative routing cases."""
import asyncio,copy,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
r=Path(__file__).resolve().parents[1];root=r/'.local/bus-eight-pins-mcp-20261027';root.mkdir(exist_ok=False)
source=r/'.local/editor-session-wire-20261026/before.dsn';before=sha256(source)
libplan=json.loads((r/'.local/design-create-mcp-20261023/work/isolated-jobs/capture_placement/plan-d2513d885dda4930b5213f7b3c8f9c91/plan.json').read_text(encoding='utf-8'))['plan']['payload'];library=Path(libplan['sourceLibrary']);lib_before=sha256(library)
project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';host_before=sha256(project)
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');install=Path(r'D:\Program Files\Cadence\SPB_24.1')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(install),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(library.parent),'--read-root',str(project.parent),'--gui-bridge-root',str(r/'.local/editor-wire-fresh-binding-20261027'),'--timeout-seconds','30'],env=env)
mapping=[dict(reference='R'+str(501+i//2),pinNumber='2' if i%2==0 else '1',index=i,hotSpot=[800,280+100*(i//2)+40*(i%2)]) for i in range(8)]
cases={}
for mode in ('descending','ascending','missing_member','detached_entry'):
 branches=[dict(index=m['index'],entryPoint=[590 if mode=='detached_entry' and m['index']==7 else 600,m['hotSpot'][1]-20],endPoint=[620,m['hotSpot'][1]],wireEnd=m['hotSpot'],expectedBusAttached=not(mode=='detached_entry' and m['index']==7)) for m in mapping if not(mode=='missing_member' and m['index']==7)]
 cases[mode]=dict(firstIndex=0 if mode=='ascending' else 7,lastIndex=7 if mode=='ascending' else 0,branches=branches)
(root/'expected.json').write_text(json.dumps(dict(mapping=mapping,cases=cases),indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
async def main():
 report=dict(passed=False,sourceBefore=before,oracleSha256=oracle,placements=[],cases=[])
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content or reply.content
    return reply.structured_content['data']
   async def attach():return (await call('capture_gui_attach',dict(instanceId=(await call('capture_gui_instances',{}))['instances'][0]['instanceId'])))['sessionId']
   ws=await call('cadence_create_workspace',dict(sourceDesign=str(source)));sid=(await call('capture_open',dict(workspaceId=ws['workspaceId'])))['sessionId']
   lib=await call('capture_library_open',dict(sourceLibrary=str(library)));part=(await call('capture_library_query',dict(libraryId=lib['libraryId'],entity='part',packageName='MCP_RES')))['items'][0]
   existing=[]
   for i in range(4):
    page=(await call('capture_query',dict(sessionId=sid,entity='page',scope=dict(kind='design'))))['items'][0]
    ms=[m for m in mapping if m['reference']=='R'+str(501+i)]
    pins=[dict(number=m['pinNumber'],name='A' if m['pinNumber']=='1' else 'B',hotSpot=m['hotSpot'],connected=False,net=None) for m in ms]
    plan=await call('capture_plan_placement',dict(sessionId=sid,pageId=page['objectId'],libraryId=lib['libraryId'],libraryPartId=part['objectId'],reference='R'+str(501+i),location=[800,300+100*i],rotationCode=1,value='1k',expectedPins=pins,expectedExistingConnections=existing))
    key={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_placement',dict(**key,idempotencyKey='place-'+str(i)));report['placements'].append(dict(plan=key,result=result))
    sid=(await call('capture_open_edit_result',dict(**key,kind='placement')))['sessionId']
    existing.extend([dict(schematicName='ROOT',pageName='MAIN',reference=m['reference'],pinNumber=m['pinNumber'],connected=False,net=None) for m in ms])
   page=(await call('capture_query',dict(sessionId=sid,entity='page',scope=dict(kind='design'))))['items'][0]
   for mode,spec in cases.items():
    item=dict(mode=mode,passed=False);report['cases'].append(item)
    try:
     expected=copy.deepcopy(existing)
     for pin in expected:
      m=next(m for m in mapping if m['reference']==pin['reference'] and m['pinNumber']==pin['pinNumber']);connected=not(mode=='missing_member' and m['index']==7);pin.update(connected=connected,net='DATA'+str(m['index']) if connected else None)
     plan=await call('capture_plan_bus_create',dict(sessionId=sid,guiSessionId=await attach(),hostProject=str(project),pageId=page['objectId'],prefix='DATA',busStart=[600,200],busEnd=[600,700],expectedConnections=expected,**spec))
     key={k:plan[k] for k in ('planId','planDigest')};item['plan']=key
     result=await call('capture_apply_bus_create',dict(**key,idempotencyKey=mode));item['result']=result
     assert result['localEntryRoutingComplete']==(mode in ('descending','ascending'))
     target=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn';saved=sha256(target);output=root/(mode+'-members.json')
     run_tcl(Config(install,root/'read-work',(root,),30),str(r/'tools/probe_bus_pin_members.tcl'),[str(target),str(output),'100000'],root)
     observed=json.loads(output.read_text(encoding='utf-8'));rows=observed['memberships'];assert len(rows)==8
     for m in mapping:
      row=next(row for row in rows if row['reference']==m['reference'] and row['pinNumber']==m['pinNumber'])
      connected=not(mode=='missing_member' and m['index']==7)
      assert row['hasMember']==connected,(mode,m,row)
      assert row['memberPointerEqualsPinNet']==connected
      assert row['position']==((m['index'] if mode=='ascending' else 7-m['index']) if connected else -1),(mode,m,row)
      assert row['pinNet']==('DATA'+str(m['index']) if connected else '')
     assert sha256(target)==saved;item.update(passed=True,eightPhysicalPinsAndNativeMemberPointersVerified=True,observed=rows);print(json.dumps(dict(mode=mode,passed=True)),flush=True)
    except BaseException:item['error']=traceback.format_exc();print(json.dumps(dict(mode=mode,passed=False,error=item['error'])),flush=True)
   report['passed']=len(report['cases'])==4 and all(c['passed'] for c in report['cases'])
 except BaseException:report['error']=traceback.format_exc()
 report.update(sourceUnchanged=sha256(source)==before,libraryUnchanged=sha256(library)==lib_before,hostProjectUnchanged=sha256(project)==host_before,oracleUnchanged=sha256(root/'expected.json')==oracle)
 report['passed']=report['passed'] and all(report[k] for k in ('sourceUnchanged','libraryUnchanged','hostProjectUnchanged','oracleUnchanged'))
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ('cases','placements')}),flush=True)
asyncio.run(main())
