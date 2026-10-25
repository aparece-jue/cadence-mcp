"""Actual MCP compatible cache replacement and durable lifecycle on original independent pin oracles."""
import argparse,asyncio,copy,json,os,sys,shutil,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env,ADAPTERS
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir();fixture=a.fixture_root
prior=json.loads((fixture/'report.json').read_text(encoding='utf-8'));library_path=Path(prior['cases'][0]['request']['newLib']);source=fixture/'source-with-overrides.dsn';custom=sources/'custom.dsn';shutil.copy2(source,custom)
c=Config(a.install_root,root/'preparation',(fixture,),60)
process=run_owned_process([c.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_name('fixture_cache_overrides.tcl'),c.install_root,custom,root/'custom-receipt.json',ADAPTERS/'json.tcl'],root,process_env(c),60)
(root/'preparation-process.json').write_text(json.dumps(process,indent=2),encoding='utf-8');assert process['returnCode']==0
details=json.loads((fixture/'packageName-1/expected-details.json').read_text(encoding='utf-8'));baseline=json.loads((fixture/'baseline/definition.json').read_text(encoding='utf-8'))
oracle={}
for row in details.values():
 g=row['geometry'];ref=g['reference'];pins=[]
 for pin in g['pins']:
  old=next(p for p in baseline['pin'] if p['reference']==ref and p['number']==pin['number'])
  pins.append({k:pin[k] for k in ('number','name','hotSpot')}|{'connected':old['connected'],'net':old['net'] if old['connected'] else None})
 oracle[ref]=pins
(root/'expected.json').write_text(json.dumps({'pins':oracle,'customTag':'缓存在_PLACEHOLDER'},indent=2),encoding='utf-8')
expected_tag='缓存在_PLACEHOLDER'.replace('在_PLACEHOLDER','[x]$;"\\\nTAG')
# The literal declaration matches the ASCII Tcl Unicode escapes, not observed output.
(root/'expected.json').write_text(json.dumps({'pins':oracle,'customTag':expected_tag,'displayValueLocation':[17,23],'displayValueRotation':2},ensure_ascii=False,indent=2),encoding='utf-8');oracle_hash=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(fixture),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
report={'passed':False,'sourceHashesBefore':{'original':sha256(source),'custom':sha256(custom),'library':sha256(library_path)},'cases':[],'checks':{}}
def dump():(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
   for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   async def call(name,args,error=None):
    r=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(r.structured_content)
    if error:assert r.is_error and r.structured_content['error']['code']==error,(name,r.structured_content)
    else:assert not r.is_error,(name,r.structured_content)
    return r.structured_content['data']
   for i,src in enumerate((source,custom)):
    ws=await call('cadence_create_workspace',{'sourceDesign':str(src)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
    lid=(await call('capture_library_open',{'sourceLibrary':str(library_path)}))['libraryId'];packages=(await call('capture_library_query',{'libraryId':lid,'entity':'package','limit':1000}))['items'];pkg=next(p for p in packages if p['name']=='R');parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'];view=next(p for p in parts if p['packageId']==pkg['objectId'])
    parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];targets=[p for p in parts if p['reference'] in oracle];target=next(p for p in targets if p['reference']=='R101');expectations=[{'partId':p['objectId'],'libraryPartId':view['objectId'],'pins':copy.deepcopy(oracle[p['reference']])} for p in targets]
    if i==1:
     for p in targets:
      layers=await call('capture_get_property_layers',{'sessionId':sid,'partId':p['objectId']});assert next(u['value'] for u in layers['user'] if u['name']=='MCP_TAG')==expected_tag
      dp=next(v for v in layers['display'] if v['name']=='Value');assert dp['location']==[17,23] and dp['rotationCode']==2
    args={'sessionId':sid,'partId':target['objectId'],'libraryId':lid,'packageId':pkg['objectId'],'expectedInstances':expectations}
    await call('capture_plan_cache_replace',{**args,'expectedInstances':expectations[:1]},'incomplete_cache_expectations')
    bad=copy.deepcopy(expectations);bad[0]['pins'][0]['net']='SHORT';bad[0]['pins'][0]['connected']=True
    await call('capture_plan_cache_replace',{**args,'expectedInstances':bad},'cache_connectivity_change')
    bad=copy.deepcopy(expectations);bad[0]['pins'][0]['hotSpot']=[999,999]
    await call('capture_plan_cache_replace',{**args,'expectedInstances':bad},'cache_hotspot_change')
    plan=await call('capture_plan_cache_replace',args);key={k:plan[k] for k in ('planId','planDigest')};assert len(plan['preview']['changes'])==2
    record={'case':'original' if i==0 else 'custom','plan':plan};report['cases'].append(record);dump()
    if i==0:await call('capture_close',{'sessionId':sid});await call('capture_library_close',{'libraryId':lid})
    result=await call('capture_apply_cache_replace',{**key,'idempotencyKey':f'replace-{i}'});record['result']=result
    assert result['sourceQualifiedCacheGraphVerified'] and result['modeledAllInstanceStateVerified'] and result['sourceViewsVerified'] and result['changedInstanceCount']==2
    opened=await call('capture_open_edit_result',{**key,'kind':'cache_replace'});out_sid=opened['sessionId']
    after=(await call('capture_query',{'sessionId':out_sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items']
    for part in [p for p in after if p['reference'] in oracle]:
     binding=await call('capture_query_cache_binding',{'sessionId':out_sid,'partId':part['objectId']});assert binding['binding']['sourcePackage']=='R'
     layers=await call('capture_get_property_layers',{'sessionId':out_sid,'partId':part['objectId']})
     if i==1:assert next(p['value'] for p in layers['user'] if p['name']=='MCP_TAG')==expected_tag
    await call('capture_close',{'sessionId':out_sid})
    if i==1:
     pending=await call('capture_plan_cache_replace',args);pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_cache_replace',pk);await call('capture_apply_cache_replace',{**pk,'idempotencyKey':'pending'},'write_not_replayed')
     await call('capture_close',{'sessionId':sid});await call('capture_library_close',{'libraryId':lid})
    report['checks'][record['case']]=True;dump();print(json.dumps({'case':record['case'],'passed':True}),flush=True)
   jobs=await call('capture_cache_replace_jobs',{'offset':0,'limit':100});assert jobs['total']==3;report['toolCount']=len(tools)
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for i,row in enumerate(report['cases']):
    key={k:row['plan'][k] for k in ('planId','planDigest')};r=await fresh.call_tool('capture_apply_cache_replace',{**key,'idempotencyKey':f'replace-{i}'});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
    r=await fresh.call_tool('capture_recover_cache_replace',key);assert not r.is_error
   row=report['cases'][1];d=root/'work'/row['result']['outputWorkspaceRelativePath'];library=d/'library.olb';library.write_bytes(library.read_bytes()+b'owned asset tamper negative')
   r=await fresh.call_tool('capture_open_edit_result',{**{k:row['plan'][k] for k in ('planId','planDigest')},'kind':'cache_replace'});assert r.is_error and r.structured_content['error']['code']=='target_changed'
   row=report['cases'][0];d=root/'work'/row['result']['outputWorkspaceRelativePath'];target=d/'design.dsn';target.write_bytes(target.read_bytes()+b'owned design tamper negative')
   r=await fresh.call_tool('capture_open_edit_result',{**{k:row['plan'][k] for k in ('planId','planDigest')},'kind':'cache_replace'});assert r.is_error and r.structured_content['error']['code']=='target_changed'
  report['checks'].update(fresh_no_replay=True,terminal_design_and_library_hashes=True,pending_cancel=True,closed_input_sessions=True,scope_pin_net_hotspot_negatives=True)
  report['sourceHashesAfter']={'original':sha256(source),'custom':sha256(custom),'library':sha256(library_path)};assert report['sourceHashesBefore']==report['sourceHashesAfter'];assert sha256(root/'expected.json')==oracle_hash
  report['passed']=True
 except BaseException as error:report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
 finally:dump()
 print(json.dumps({k:report.get(k) for k in ('passed','toolCount','checks','error')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
