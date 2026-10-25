import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();fixture=a.fixture_root.resolve();source=fixture/'design.dsn';root.mkdir(exist_ok=False);expected=json.loads((fixture/'expected.json').read_text(encoding='utf-8'));env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(fixture),'--timeout-seconds','60'],env=env)
report={'passed':False,'fullH01Accepted':False,'sourceHashBefore':sha256(source),'expectedHashBefore':sha256(fixture/'expected.json'),'cases':[],'checks':{}}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;report['tools']=len(tools);schemas={t.name:t.output_schema for t in tools};assert next(t for t in tools if t.name=='capture_get_occurrence_properties').model_dump(mode='json',by_alias=True)['annotations']['readOnlyHint']
   async def call(name,args,error=None):
    response=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(response.structured_content)
    if error:assert response.is_error and response.structured_content['error']['code']==error,(name,response.structured_content)
    else:assert not response.is_error,(name,response.structured_content)
    return response.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];hier=(await call('capture_get_hierarchy',{'sessionId':sid,'limit':1000}))['items'];root_occ=next(row for row in hier if row['parentId'] is None);directory=root/'work'/ws['workspaceId'];before=set(directory.glob('occurrence-props-request*.json'));await call('capture_get_occurrence_properties',{'sessionId':sid,'occurrenceId':root_occ['occurrenceId']},'capability_unavailable');assert set(directory.glob('occurrence-props-request*.json'))==before;await call('capture_get_occurrence_properties',{'sessionId':sid,'occurrenceId':'occ-99999'},'object_not_found');report['checks']['root_and_unknown_refused_before_request']=True
   for label,path in [('A',['halfadd_A','U3A']),('B',['halfadd_B','U3C'])]:
    target=next(row for row in hier if row['instancePathSegments']==path);args={'sessionId':sid,'occurrenceId':target['occurrenceId']};data=await call('capture_get_occurrence_properties',args);report['cases'].append({'label':label,'occurrenceId':target['occurrenceId'],'result':data});assert data['instancePathSegments']==path and data['context']=='component_occurrence' and not data['propertySourceResolutionVerified'];eff={p['name']:p['value'] for p in data['effective']};user={p['name']:p['value'] for p in data['user']};defs={p['name']:p['value'] for p in data['definition']['effective']};assert user['MCP_SCOPE_TAG']==expected[label] and eff['MCP_SCOPE_TAG']==expected[label] and eff['Value']==expected[label+'Value'];assert defs['Value']==expected['BValue'] and defs['MCP_DEF_TAG']==expected['definitionTag'] and 'MCP_SCOPE_TAG' not in defs;assert data['definition']['fullReference']=='U3A' and data['definition']['deviceDesignator']=='A'
    for i in range(3):assert await call('capture_get_occurrence_properties',args)==data
   assert report['cases'][0]['result']['definition']['nativeId']==report['cases'][1]['result']['definition']['nativeId'];report['checks'].update(shared_definition_distinct_occurrences=True,per_occurrence_unicode_and_value_isolation=True,definition_inheritance_separate=True,repeated_stable_reads=True)
   sid2=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];hier2=(await call('capture_get_hierarchy',{'sessionId':sid2,'limit':1000}))['items'];target=next(row for row in hier2 if row['instancePathSegments']==['halfadd_B','U3C']);data=await call('capture_get_occurrence_properties',{'sessionId':sid2,'occurrenceId':target['occurrenceId']});assert data['user']==report['cases'][1]['result']['user'];await call('capture_close',{'sessionId':sid2});report['checks']['independent_reopen']=True
   (directory/'design.dsn').write_bytes((directory/'design.dsn').read_bytes()+b'owned source-stale negative');await call('capture_get_occurrence_properties',{'sessionId':sid,'occurrenceId':report['cases'][0]['occurrenceId']},'target_changed');await call('capture_close',{'sessionId':sid});await call('capture_get_occurrence_properties',{'sessionId':sid,'occurrenceId':report['cases'][0]['occurrenceId']},'session_lost');report['checks'].update(changed_source_refused=True,closed_session_refused=True)
  report['passed']=all(report['checks'].values())
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 report['sourceHashAfter']=sha256(source);report['expectedHashAfter']=sha256(fixture/'expected.json');report['passed']=report['passed'] and report['sourceHashBefore']==report['sourceHashAfter'] and report['expectedHashBefore']==report['expectedHashAfter'];(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')}))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
