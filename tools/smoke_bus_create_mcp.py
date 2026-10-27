"""Actual public bus tasks: original ascending/descending/missing/detached matrix."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
from cadence_mcp.capture_wire import geometry_union
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/bus-create-mcp-20261027';root.mkdir(exist_ok=False);source=r/'.local/editor-session-wire-20261026/before.dsn';before=sha256(source);assert before=='971c4675e25441783520afdd86a898647a39f05f377cc217d5e23c2bfb671dda'
project=r/'.local/placewire-resume-v2-20261027/MCP_PLACE_WIRE.opj';project_before=sha256(project);bindings=r/'.local/editor-wire-fresh-binding-20261027';env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(project.parent),'--gui-bridge-root',str(bindings),'--timeout-seconds','30'],env=env)
cases={}
for mode in ('descending','ascending','missing_member','detached_entry'):
 branches=[{'index':i,'entryPoint':[590 if mode=='detached_entry' and i==7 else 600,220+50*i],'endPoint':[620,240+50*i],'wireEnd':[800,240+50*i],'expectedBusAttached':not(mode=='detached_entry' and i==7)} for i in range(7 if mode=='missing_member' else 8)]
 cases[mode]={'firstIndex':0 if mode=='ascending' else 7,'lastIndex':7 if mode=='ascending' else 0,'branches':branches,'expectedRoutingComplete':mode in ('descending','ascending')}
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');oracle_hash=sha256(root/'expected.json')
def files():return {p.relative_to(root/'work').as_posix():sha256(p) for p in (root/'work').rglob('*') if p.is_file()}
async def main():
 report={'passed':False,'sourceBefore':before,'oracleSha256':oracle_hash,'cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   ts=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in ts};report['toolCount']=len(ts)
   async def call(name,args):
    res=await client.call_tool(name,args);assert not res.is_error,res.structured_content or res.content;Draft202012Validator(schemas[name]).validate(res.structured_content);return res.structured_content['data']
   async def attach():return (await call('capture_gui_attach',{'instanceId':(await call('capture_gui_instances',{}))['instances'][0]['instanceId']}))['sessionId']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];page=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
   base={'sessionId':sid,'hostProject':str(project),'pageId':page['objectId'],'prefix':'DATA','busStart':[600,200],'busEnd':[600,700],'expectedConnections':[]}
   pending=await call('capture_plan_bus_create',{**base,**{k:v for k,v in cases['descending'].items() if k!='expectedRoutingComplete'},'guiSessionId':await attach()});pkey={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_bus_create',pkey);assert (await client.call_tool('capture_apply_bus_create',{**pkey,'idempotencyKey':'cancelled-bus'})).is_error
   for mode,case in cases.items():
    item={'mode':mode,'passed':False};report['cases'].append(item)
    try:
     args={**base,**{k:v for k,v in case.items() if k!='expectedRoutingComplete'},'guiSessionId':await attach()}
     plan=await call('capture_plan_bus_create',args);key={k:plan[k] for k in ('planId','planDigest')};item['plan']=key
     result=await call('capture_apply_bus_create',{**key,'idempotencyKey':mode});item['result']=result;assert result['localEntryRoutingComplete']==case['expectedRoutingComplete'] and result['designPassed'] is None;keys.append((key,mode))
     opened=await call('capture_open_edit_result',{**key,'kind':'bus_create'});oid=opened['sessionId'];rows={kind:(await call('capture_query_bus',{'sessionId':oid,'entity':kind,'limit':1000}))['items'] for kind in ('bus','scalar','entry')}
     order=[f'DATA{i}' for i in range(case['firstIndex'],case['lastIndex']+(1 if mode=='ascending' else -1),1 if mode=='ascending' else -1)]
     assert rows['bus'] and all(w['width']==8 and [m['name'] for m in w['members']]==order for w in rows['bus'])
     assert geometry_union([w['points'] for w in rows['bus']])==geometry_union([[[600,200],[600,700]]])
     assert len(rows['scalar'])==len(case['branches']) and len(rows['entry'])==len(case['branches']);assert sorted(w['name'] for w in rows['scalar'])==[f'DATA{i}' for i in range(len(case['branches']))]
     wires={w['wireId']:w for w in rows['bus']+rows['scalar']}
     for b in case['branches']:
      entry=next(e for e in rows['entry'] if e['entryPoint']==b['entryPoint']);assert entry['endPoint']==b['endPoint'];assert (entry['entryWireId'] is not None)==b['expectedBusAttached'];assert wires[entry['endWireId']]['name']=='DATA'+str(b['index'])
     item.update(passed=True,independentPublicQueryVerified=True,expectedMemberOrder=order,rows=rows);print(json.dumps({'mode':mode,'passed':True,'routingComplete':result['localEntryRoutingComplete']}),flush=True)
    except BaseException:item['error']=traceback.format_exc();print(json.dumps({'mode':mode,'passed':False,'error':item['error']}),flush=True)
   frozen=files()
  async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
   for key,mode in keys:
    for name,args in [('capture_apply_bus_create',{**key,'idempotencyKey':mode}),('capture_recover_bus_create',key)]:
     res=await fresh.call_tool(name,args);assert not res.is_error,res.structured_content;assert not res.structured_content['data']['mutationReplayed']
  assert files()==frozen;report['freshServiceAllVerifiedTasksUnchanged']=True;report['passed']=len(report['cases'])==4 and all(c['passed'] for c in report['cases'])
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['hostProjectUnchanged']=sha256(project)==project_before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle_hash;report['passed']=report['passed'] and report['sourceUnchanged'] and report['hostProjectUnchanged'] and report['oracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='cases'}),flush=True)
asyncio.run(main())
