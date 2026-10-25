import argparse,asyncio,copy,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);fixtures=a.fixture_root.resolve()
cases=[{'fixture':'single','part':'RES.Normal','position':0,'style':{'long':False},'other':{},'views':1},
       {'fixture':'single','part':'RES.Convert','position':1,'style':{'clock':True,'dot':True},'other':{'visible':False,'startPoint':[5,5]},'views':1},
       {'fixture':'shared_dual','part':'GATE.Normal','position':0,'style':{'dot':True},'other':{},'views':2},
       {'fixture':'heterogeneous_power','part':'POWER.Normal','position':0,'style':{'clock':True},'other':{},'views':1},
       {'fixture':'single','part':'RES.Normal','position':0,'style':{'clock':True},'other':{'pinType':7},'views':1}]
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');sources={n:fixtures/n/'library.olb' for n in {c['fixture'] for c in cases}};before={n:sha256(p) for n,p in sources.items()};env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(fixtures),'--timeout-seconds','60'],env=env);report={'passed':False,'fullL04Accepted':False,'cases':[],'checks':{}};keys=[]
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as c:
   tools=(await c.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['tools']=len(tools);assert next(t for t in tools if t.name=='capture_get_library_pin_style').model_dump(mode='json',by_alias=True)['annotations']['readOnlyHint']
   async def call(name,args,error=None):
    response=await c.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content);return
    assert not response.is_error,(name,response.structured_content);return response.structured_content['data']
   for index,case in enumerate(cases):
    row={'index':index,'case':case,'passed':False};report['cases'].append(row)
    try:
     lid=(await call('capture_library_open',{'sourceLibrary':str(sources[case['fixture']])}))['libraryId'];parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items'];part=next(p for p in parts if p['name']==case['part']);pins=(await call('capture_library_query',{'libraryId':lid,'entity':'pin','limit':1000}))['items'];pin=next(p for p in pins if p['partId']==part['objectId'] and p['position']==case['position']);old=await call('capture_get_library_pin_style',{'libraryId':lid,'pinId':pin['objectId']});wanted={**old['flags'],**case['style']};wanted.update({k:v for k,v in case['other'].items() if k=='visible'});assert len(old['sharedViewScopes'])==case['views'];row['before']=old
     if 'visible' in case['other'] or 'pinType' in case['other']:wanted['global']=case['other'].get('pinType',pin['pinType'])==7 or not wanted['visible']
     args={'libraryId':lid,'pinId':pin['objectId'],'style':case['style'],**case['other']};plan=await call('capture_plan_library_pin_edit',args);row['plan']=plan;key={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_library_pin_edit',{**key,'idempotencyKey':'style-'+str(index)});row['result']=result;assert result['nativePinStylesVerified'];opened=await call('capture_open_edited_library',{**key,'kind':'pin'});out_lid=opened['libraryId'];outparts=(await call('capture_library_query',{'libraryId':out_lid,'entity':'part','limit':1000}))['items'];outpins=(await call('capture_library_query',{'libraryId':out_lid,'entity':'pin','limit':1000}))['items'];selected=[]
     for p in outparts:
      if p['name']!=case['part']:continue
      for target in outpins:
       if target['partId']==p['objectId'] and target['position']==case['position']:
        flags=await call('capture_get_library_pin_style',{'libraryId':out_lid,'pinId':target['objectId']});assert flags['flags']==wanted;selected.append(flags)
     assert len(selected)==case['views'];row['after']=selected;row['passed']=True;keys.append((index,key));await call('capture_plan_library_pin_edit',{'libraryId':out_lid,'pinId':selected[0]['pinId'],'style':case['style']},'no_change');await call('capture_get_library_pin_style',{'libraryId':lid,'pinId':'foreign-pin'},'object_not_found');await call('capture_library_close',{'libraryId':lid});await call('capture_get_library_pin_style',{'libraryId':lid,'pinId':pin['objectId']},'session_lost')
    except BaseException as error:row.update(passed=False,error=str(error),traceback=traceback.format_exc())
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'case':index,'passed':row['passed'],'error':row.get('error')},ensure_ascii=False),flush=True)
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for index,key in keys:
    response=await fresh.call_tool('capture_apply_library_pin_edit',{**key,'idempotencyKey':'style-'+str(index)});assert not response.is_error and not response.structured_content['data']['mutationReplayed'];assert not (await fresh.call_tool('capture_recover_library_pin_edit',key)).is_error;assert not (await fresh.call_tool('capture_open_edited_library',{**key,'kind':'pin'})).is_error
   report['checks']['accepted_fresh_lifecycle_no_replay']=True
  report['checks']['sources_and_oracle_unchanged']=oracle==sha256(root/'expected.json') and all(sha256(p)==before[n] for n,p in sources.items());report['passed']=all(row['passed'] for row in report['cases']) and all(report['checks'].values())
 except BaseException as error:report.update(error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')},ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
