"""Original C01 acceptance requirements, independent fixed counts and names."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env,ADAPTERS
from cadence_mcp.process_tree import run_owned_process
repo=Path(__file__).resolve().parents[1];root=repo/'.local/query-closure-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
install=Path(r'D:\Program Files\Cadence\SPB_24.1');cfg=Config(install,root/'work',(sources,),60)
expected={'empty':{'schematic':1,'page':1,'part':0,'pin':0},'duplicate':{'schematic':2,'page':3,'part':4,'pin':8},'schematicNames':['ROOT','AUX'],'pageNames':['SAME_PAGE','EMPTY_PAGE','SAME_PAGE'],'references':['R1','R10','R1','R10'],'pinNumbers':['1','2'],'repeatOpens':12}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
report={'passed':False,'fixtures':[],'cases':[],'checks':{}}
for name in ('empty','duplicate'):
 process=run_owned_process([install/'tcltk/bin/tclsh.exe',repo/'tools/fixture_query.tcl',install,sources/(name+'.dsn'),name,sources/(name+'.json'),ADAPTERS/'json.tcl'],sources,process_env(cfg),60)
 report['fixtures'].append({'case':name,'process':process});assert process['returnCode']==0 and process['remainingOwnedProcesses']==0
before={p.name:sha256(p) for p in sources.glob('*.dsn')}
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(install),'--workspace-root',str(cfg.workspace_root),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==167;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content)
    Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
   async def query(sid,entity,scope={'kind':'design'},**kw):return await call('capture_query',{'sessionId':sid,'entity':entity,'scope':scope,**kw})
   for name in ('empty','duplicate'):
    ws=await call('cadence_create_workspace',{'sourceDesign':str(sources/(name+'.dsn'))});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId'];assert opened['counts']==expected[name],opened
    observed={};cursors=[]
    for entity in ('schematic','page','part','pin'):
     values=[];cursor=None
     while True:
      result=await query(sid,entity,limit=1,cursor=cursor);assert result['total']==expected[name][entity] and result['revision']==opened['revision']
      values+=result['items'];cursor=result['nextCursor']
      if cursor:cursors.append((entity,cursor))
      else:assert result['complete'];break
     assert len(values)==expected[name][entity] and len({v['objectId'] for v in values})==len(values);observed[entity]=values
    if name=='duplicate':
     assert sorted(v['name'] for v in observed['schematic'])==sorted(expected['schematicNames'])
     assert sorted(v['name'] for v in observed['page'])==sorted(expected['pageNames'])
     assert sorted(v['reference'] for v in observed['part'])==sorted(expected['references'])
     pages=[p for p in observed['page'] if p['name']=='SAME_PAGE'];assert len(pages)==2 and len({p['schematicId'] for p in pages})==2
     for page in observed['page']:
      scoped={'kind':'page','pageId':page['objectId']};q=await query(sid,'part',scoped,reference='R1',limit=10)
      assert q['total']==(0 if page['name']=='EMPTY_PAGE' else 1)
      pins=await query(sid,'pin',scoped,reference='R1',limit=10)
      assert pins['total']==(0 if page['name']=='EMPTY_PAGE' else 2)
      if pins['items']:assert sorted(p['number'] for p in pins['items'])==expected['pinNumbers']
     assert (await query(sid,'part',reference='R1',limit=10))['total']==2
     assert (await query(sid,'part',reference='R',limit=10))['total']==0
     assert (await query(sid,'part',reference='R100',limit=10))['total']==0
     projection=await query(sid,'part',fields=['reference'],limit=10);assert all(set(p)=={'reference'} for p in projection['items'])
     r=await client.call_tool('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':2,'cursor':next(c for e,c in cursors if e=='part')});assert r.is_error and r.structured_content['error']['code']=='stale_cursor'
    snap=await call('capture_snapshot',{'sessionId':sid});artifact=snap['artifact'];snapshot=cfg.workspace_root/ws['workspaceId']/artifact['workspaceRelativePath'];assert sha256(snapshot)==artifact['sha256']
    frozen=json.loads(snapshot.read_text(encoding='utf-8'));assert frozen['objects']==observed and frozen['revision']==opened['revision'] and not frozen['occurrenceConnectivityVerified']
    again=await call('capture_open',{'workspaceId':ws['workspaceId']});assert again['revision']==opened['revision'] and again['counts']==opened['counts']
    if cursors:
     r=await client.call_tool('capture_query',{'sessionId':again['sessionId'],'entity':'page','scope':{'kind':'design'},'limit':1,'cursor':cursors[0][1]});assert r.is_error and r.structured_content['error']['code']=='stale_cursor'
    await call('capture_close',{'sessionId':again['sessionId']})
    for _ in range(expected['repeatOpens']):
     fresh=await call('capture_open',{'workspaceId':ws['workspaceId']});assert fresh['counts']==expected[name];await call('capture_close',{'sessionId':fresh['sessionId']})
    await call('capture_close',{'sessionId':sid});r=await client.call_tool('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'}});assert r.is_error and r.structured_content['error']['code']=='session_lost'
    # Deliberate corruption only of the MCP-owned copied design, not source or snapshot.
    copy=cfg.workspace_root/ws['workspaceId']/'design.dsn'
    with copy.open('ab') as stream:stream.write(b'OWNED_STALE_QUERY_TEST')
    r=await client.call_tool('capture_open',{'workspaceId':ws['workspaceId']});assert r.is_error and r.structured_content['error']['code']=='target_changed'
    assert sha256(snapshot)==artifact['sha256'] and frozen['objects']==observed
    report['cases'].append({'case':name,'passed':True,'opened':opened,'observed':observed,'snapshot':snap});print(name,'passed',flush=True)
  report['checks']={'original_counts_names_and_exact_filters':True,'page_and_cursor_isolation':True,'immutable_snapshot_and_stale_copy':True,'repeat_open_close':True,'source_and_oracle_unchanged':before=={p.name:sha256(p) for p in sources.glob('*.dsn')} and sha256(root/'expected.json')==oracle}
  report['passed']=len(report['cases'])==2 and all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
