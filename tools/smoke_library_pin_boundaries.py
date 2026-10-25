"""Independent declared physical/logical pin boundary tests through the real MCP."""
import argparse,asyncio,copy,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256

p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
positions=[0,1,7,31,127,255,256,511,1023,2047,4094,4095]
numbers=['1','A1','P+','4','05','6-','7.1','P_8','1023','2048','4095','4096']
def spec(label):
 pins=[{'position':pos,'name':'PIN_'+str(i),'pinType':i%8,'start':[-10,i*10],'hotSpot':[-20,i*10],'visible':i%2==0} for i,pos in enumerate(positions)]
 return {'packageName':label,'referenceTemplate':'J?','footprint':'MCP_BOUNDARY_FP','expectedHomogeneous':True,'symbols':[{'cellName':label+'_CELL','partName':label+'.Normal','pins':pins,'lines':[]}],'devices':[{'designator':'','position':0,'cellName':label+'_CELL','mapping':[{'position':pos,'number':num,'shared':False,'swapId':(-1,0,125,126)[i%4]} for i,(pos,num) in enumerate(zip(positions,numbers))]}]}
sparse=spec('MCP_SPARSE');shuffled=spec('MCP_SHUFFLED');shuffled['symbols'][0]['pins'].reverse();shuffled['devices'][0]['mapping']=shuffled['devices'][0]['mapping'][6:]+shuffled['devices'][0]['mapping'][:6]
names=spec('MCP_NAMES');names['symbols'][0]['pins'][0]['name']='EXPLICIT_0';names['symbols'][0]['pins'][1]['name']='中文[x]$;';names['symbols'][0]['pins'][2]['name']='N'*128;names['symbols'][0]['pins'][3]['name']='SAME';names['symbols'][0]['pins'][4]['name']='SAME'
cases={'sparse_positions':sparse,'independent_declaration_order':shuffled,'explicit_pin_name_boundaries':names};(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(root),'--timeout-seconds','60'],env=env);report={'passed':False,'fullL02Accepted':False,'exactEmptyNameSupported':False,'cases':[],'checks':{}};keys=[]
def pin_rows(spec):
 pins={p['position']:p for p in spec['symbols'][0]['pins']}
 return sorted([[m['position'],m['number'],pins[m['position']]['name'],pins[m['position']]['pinType'],pins[m['position']]['visible'],m['shared'],m['swapId'],pins[m['position']]['hotSpot']] for m in spec['devices'][0]['mapping']],key=lambda r:r[0])
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   schemas={t.name:t.output_schema for t in (await client.list_tools()).tools};report['tools']=len(schemas)
   async def call(name,args,error=None):
    response=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content);return
    assert not response.is_error,(name,response.structured_content);return response.structured_content['data']
   for label,declared in cases.items():
    row={'case':label,'passed':False};report['cases'].append(row)
    try:
     row['plan']=await call('capture_plan_library_create',{'spec':declared});key={k:row['plan'][k] for k in ('planId','planDigest')};row['result']=await call('capture_apply_library_create',{**key,'idempotencyKey':label});opened=await call('capture_open_created_library',key);lid=opened['libraryId'];observed=[];cursor=None
     while True:
      page=await call('capture_library_query',{'libraryId':lid,'entity':'pin','packageName':declared['packageName'],'limit':1,'cursor':cursor});observed.extend(page['items']);cursor=page['nextCursor']
      if cursor is None:break
     actual=sorted([[p[k] for k in ('position','number','name','pinType','visible','shared','swapId','hotSpot')] for p in observed],key=lambda r:r[0]);assert actual==pin_rows(declared),(actual,pin_rows(declared));assert row['result']['uniquePhysicalPadCount']==12;row['observedPins']=actual;await call('capture_library_close',{'libraryId':lid});await call('capture_library_query',{'libraryId':lid,'entity':'pin'},'session_lost');row['passed']=True;keys.append((label,key))
    except BaseException as e:row.update(error=str(e),traceback=traceback.format_exc())
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'case':label,'passed':row['passed'],'error':row.get('error')},ensure_ascii=False),flush=True)
   for bad in (4096,-1):
    spec=copy.deepcopy(sparse);spec['symbols'][0]['pins'][0]['position']=bad
    response=await client.call_tool('capture_plan_library_create',{'spec':spec});assert response.is_error
   bad=copy.deepcopy(names);bad['symbols'][0]['pins'][2]['name']='N'*129;response=await client.call_tool('capture_plan_library_create',{'spec':bad});assert response.is_error;report['checks']['out_of_contract_positions_and_names_refused']=True
   jobs=root/'work/isolated-jobs/capture_library_create';before=set(jobs.glob('plan-*'));bad=copy.deepcopy(names);bad['symbols'][0]['pins'][0]['name']='';response=await client.call_tool('capture_plan_library_create',{'spec':bad});assert response.is_error and set(jobs.glob('plan-*'))==before;report['checks']['unsupported_empty_name_refused_before_durable_plan']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for label,key in keys:
    response=await fresh.call_tool('capture_apply_library_create',{**key,'idempotencyKey':label});assert not response.is_error and response.structured_content['data']['mutationReplayed'] is False;assert not (await fresh.call_tool('capture_open_created_library',key)).is_error
   report['checks']['accepted_outputs_fresh_reopen_no_replay']=True
  report['checks']['oracle_unchanged']=oracle==sha256(root/'expected.json');report['passed']=all(c['passed'] for c in report['cases']) and all(report['checks'].values())
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')},ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
