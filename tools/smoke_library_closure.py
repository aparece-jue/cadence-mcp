"""L01 original criteria against original pre-write variant declarations and official R oracle."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];root=repo/'.local/library-query-closure-20261025';root.mkdir(exist_ok=False);variants=repo/'.local/library-part-variants-20261024';assert json.loads((variants/'report.json').read_text())['passed']
install=Path(r'D:\Program Files\Cadence\SPB_24.1');official=install/'tools/capture/library/pspice/analog.olb'
cases=[('official',official,None)]+[(name,variants/name/'library.olb',variants/name/'expected.json') for name in ('single','shared_dual','heterogeneous_power')]
before={str(p):sha256(p) for _,source,oracle in cases for p in ([source] if oracle is None else [source,oracle])}
expected={'officialPackage':'R','officialPhysicalPins':['1','2'],'reopenRepeats':2,'originalDeclarationFiles':{name:sha256(oracle) for name,source,oracle in cases if oracle}}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oraclehash=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(install),'--workspace-root',str(root/'work'),'--read-root',str(official.parent),'--read-root',str(variants),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'checks':{}}
def sortedrows(rows):return sorted(rows,key=lambda r:json.dumps(r,sort_keys=True))
def canonical(rows):
 packages={r['objectId']:r for r in rows['package']};devices={r['objectId']:r for r in rows['device']};cells={r['objectId']:r for r in rows['cell']};parts={r['objectId']:r for r in rows['part']};scopes=[];pins=[]
 for part in rows['part']:
  dev=devices[part['deviceId']];pkg=packages[part['packageId']];cell=cells[part['cellId']];assert dev['packageId']==pkg['objectId'] and dev['cellId']==cell['objectId'];scope=[pkg['name'],dev['designator'],dev['position'],cell['name'],part['name']];scopes.append(scope)
  for pin in (p for p in rows['pin'] if p['partId']==part['objectId']):
   assert pin['deviceId']==dev['objectId'] and pin['packageId']==pkg['objectId'];pins.append([*scope,pin['position'],pin['number'],pin['name'],pin['pinType'],pin['visible'],pin['shared'],pin['swapId'],pin['hotSpot']])
 return sortedrows(scopes),sortedrows(pins)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==178;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content);Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
   async def all_rows(lid,entity):
    rows=[];cursor=None;first_cursor=None
    while True:
     result=await call('capture_library_query',{'libraryId':lid,'entity':entity,'cursor':cursor,'limit':3});rows+=result['items'];cursor=result['nextCursor']
     if cursor and first_cursor is None:first_cursor=cursor
     if cursor is None:assert result['complete'] and len(rows)==result['total'];return rows,first_cursor
   for label,source,originaloracle in cases:
    opened=await call('capture_library_open',{'sourceLibrary':str(source)});lid=opened['libraryId'];assert opened['readOnly'] and not opened['externalFootprintVerified'] and opened['revision']==sha256(source)
    rows={};cursors=[]
    for entity in ('package','device','cell','part','pin'):
     rows[entity],cursor=await all_rows(lid,entity);assert len(rows[entity])==opened['counts'][entity] and len({v['objectId'] for v in rows[entity]})==len(rows[entity])
     if cursor:cursors.append((entity,cursor))
    scopes,pins=canonical(rows)
    if originaloracle:
     declared=json.loads(originaloracle.read_text());assert len(rows['package'])==1;assert {k:v for k,v in rows['package'][0].items() if k!='objectId'}==declared['package'];assert scopes==sortedrows(declared['devices']) and pins==sortedrows(declared['pins'])
     package=declared['package']['name'];physical=sorted({p[6] for p in declared['pins']});assert sorted({p['number'] for p in rows['pin']})==physical
    else:
     package='R';physical=['1','2'];assert opened['counts']==json.loads((repo/'.local/library-analog-20261023/library-smoke-report.json').read_text())['counts']
     selected=await call('capture_library_query',{'libraryId':lid,'entity':'pin','packageName':'R','limit':1000});assert selected['items'] and sorted({p['number'] for p in selected['items']})==physical
    missing=await call('capture_library_query',{'libraryId':lid,'entity':'pin','packageName':package+'NOT_PRESENT','limit':100});assert missing['total']==0 and not missing['items'] and missing['nextCursor'] is None
    short=await call('capture_library_query',{'libraryId':lid,'entity':'package','packageName':package[:-1],'limit':100});assert short['total']==0
    entity,cursor=cursors[0];bad=await client.call_tool('capture_library_query',{'libraryId':lid,'entity':entity,'cursor':cursor,'limit':4});assert bad.is_error and bad.structured_content['error']['code']=='stale_cursor'
    fresh=await call('capture_library_open',{'sourceLibrary':str(source)});freshid=fresh['libraryId']
    bad=await client.call_tool('capture_library_query',{'libraryId':freshid,'entity':entity,'cursor':cursor,'limit':3});assert bad.is_error and bad.structured_content['error']['code']=='stale_cursor'
    for kind in rows:assert (await all_rows(freshid,kind))[0]==rows[kind]
    await call('capture_library_close',{'libraryId':freshid})
    for _ in range(expected['reopenRepeats']):
     again=await call('capture_library_open',{'sourceLibrary':str(source)});assert again['counts']==opened['counts'];await call('capture_library_close',{'libraryId':again['libraryId']})
    copy=root/'work'/lid/'library.olb';assert sha256(copy)==sha256(source)
    with copy.open('ab') as f:f.write(b'OWNED_STALE_LIBRARY_TEST')
    bad=await client.call_tool('capture_library_query',{'libraryId':lid,'entity':'pin','limit':10});assert bad.is_error and bad.structured_content['error']['code']=='target_changed'
    await call('capture_library_close',{'libraryId':lid});bad=await client.call_tool('capture_library_query',{'libraryId':lid,'entity':'pin'});assert bad.is_error and bad.structured_content['error']['code']=='session_lost'
    report['cases'].append({'case':label,'passed':True,'opened':opened,'deviceViewScopes':scopes,'pinViewRows':len(rows['pin']),'uniquePhysicalPins':physical,'originalOracleSha256':sha256(originaloracle) if originaloracle else None});print(label,'library query passed',flush=True)
  report['checks']={'all_entities_paged_and_parent_links':True,'original_variant_pin_mapping_oracles':True,'logical_views_not_physical_pad_count':True,'cursor_scope_session_bound':True,'stale_copy_close_and_repeats':True,'sources_and_original_oracles_unchanged':before=={p:sha256(Path(p)) for p in before} and sha256(root/'expected.json')==oraclehash};report['passed']=len(report['cases'])==4 and all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
