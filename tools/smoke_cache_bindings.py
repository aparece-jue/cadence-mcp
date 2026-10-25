"""Actual source-qualified cache reads on original duplicate-name and replacement fixtures."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);prior=json.loads((a.fixture_root/'report.json').read_text(encoding='utf-8'))
cases=[{'name':'prepared','source':str(a.fixture_root/'source-with-overrides.dsn'),'package':'MCP_FIXTURE_R','sourceLibrary':prior['selected']['sourceLib'],'sameNameEntries':2,'pinOneName':'1'}]
for row in prior['cases']:
 cases.append({'name':'replace'+str(row['update']),'source':str(a.fixture_root/(row['selector']+'-'+str(row['update']))/'design.dsn'),'package':'R','sourceLibrary':row['request']['newLib'].upper(),'sameNameEntries':1,'pinOneName':'CACHE_INPUT'})
(root/'expected.json').write_text(json.dumps(cases,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.fixture_root),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'sourceHashesBefore':{c['name']:sha256(Path(c['source'])) for c in cases},'checks':{}}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
   for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   async def call(name,args,error=None):
    r=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(r.structured_content)
    if error:assert r.is_error and r.structured_content['error']['code']==error,r.structured_content
    else:assert not r.is_error,(name,r.structured_content)
    return r.structured_content['data']
   for i,case in enumerate(cases):
    ws=await call('cadence_create_workspace',{'sourceDesign':case['source']});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId']
    parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items']
    # Query old cache first to prove identifiers can be safely shared with the new qualified reader.
    old=(await call('capture_query_cache',{'sessionId':sid,'entity':'package','limit':1000}))['items'];bindings=[]
    for reference in ('R101','R102'):
     target=next(p for p in parts if p['reference']==reference)
     row=await call('capture_query_cache_binding',{'sessionId':sid,'partId':target['objectId']});bindings.append(row)
     b=row['binding'];assert b['sourcePackage']==case['package'] and b['sourceLibrary'].casefold()==case['sourceLibrary'].casefold()
     assert all(b[k] for k in ('isCached','lookupMatchesPlaced','originVerified')) and row['sourceQualifiedPackageIdentityVerified']
     assert row['externalSourceLibraryVerified'] is False and row['cacheSynchronizationVerified'] is False
     assert len(row['sameNameDefinitions'])==case['sameNameEntries']
     assert len(row['definitions']['package'])==1 and row['definitions']['package'][0]['objectId']==b['cachePackageId']
     assert any(p['objectId']==b['cachePackageId'] and p['name']==case['package'] for p in old)
     assert next(p for p in row['definitions']['pin'] if p['number']=='1')['name']==case['pinOneName']
     repeated=await call('capture_query_cache_binding',{'sessionId':sid,'partId':target['objectId']});assert repeated==row
    assert bindings[0]['binding']['cachePackageId']==bindings[1]['binding']['cachePackageId']
    if case['name']=='prepared':
     origins=bindings[0]['sameNameDefinitions'];assert sum(r['isCached'] for r in origins)==1 and sum(not r['isCached'] for r in origins)==1
    # The original fixture also contains two U3 units on one page and drawn hierarchy instances.
    units=[p for p in parts if p['reference']=='U3'];assert len(units)==2
    unit_bindings=[await call('capture_query_cache_binding',{'sessionId':sid,'partId':p['objectId']}) for p in units]
    assert {b['binding']['deviceDesignator'] for b in unit_bindings}=={'A','B'}
    assert unit_bindings[0]['binding']['nativeId']!=unit_bindings[1]['binding']['nativeId']
    assert unit_bindings[0]['binding']['cachePackageId']==unit_bindings[1]['binding']['cachePackageId']
    drawn=next(p for p in parts if p['reference']=='halfadd_A')
    await call('capture_query_cache_binding',{'sessionId':sid,'partId':drawn['objectId']},'not_placed_instance')
    await call('capture_query_cache_binding',{'sessionId':sid,'partId':'foreign'},'object_not_found')
    report['cases'].append({'case':case,'bindings':bindings,'sameReferenceUnits':unit_bindings});print(json.dumps({'case':case['name'],'passed':True}),flush=True)
    await call('capture_close',{'sessionId':sid})
    assert (await client.call_tool('capture_query_cache_binding',{'sessionId':sid,'partId':parts[0]['objectId']})).is_error
   # Stale cached reads must still reject a mutated registered copy.
   ws=await call('cadence_create_workspace',{'sourceDesign':cases[0]['source']});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'];target=next(p for p in parts if p['reference']=='R101')
   await call('capture_query_cache_binding',{'sessionId':sid,'partId':target['objectId']})
   copy=root/'work'/ws['workspaceId']/'design.dsn';copy.write_bytes(copy.read_bytes()+b'owned stale snapshot negative')
   await call('capture_query_cache_binding',{'sessionId':sid,'partId':target['objectId']},'target_changed');await call('capture_close',{'sessionId':sid})
   assert (await client.call_tool('capture_query_cache_binding',{'sessionId':'foreign','partId':target['objectId']})).is_error
   report['toolCount']=len(tools);report['checks'].update(strict_schemas=True,same_name_local_cache_disambiguated=True,old_query_ids_match=True,same_reference_multiunit_separate=True,drawn_foreign_closed_stale_refused=True,repeated_snapshot_stable=True)
  report['sourceHashesAfter']={c['name']:sha256(Path(c['source'])) for c in cases};assert report['sourceHashesBefore']==report['sourceHashesAfter'];assert sha256(root/'expected.json')==oracle
  report['passed']=True
 except BaseException as error:report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:report.get(k) for k in ('passed','toolCount','checks','error')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
