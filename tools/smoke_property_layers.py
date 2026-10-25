"""C02 original requirements: native cache defaults and explicit/display layers."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];sources=repo/'.local/property-layers-probe-v4-20261025/sources';root=repo/'.local/property-layers-mcp-20261025';root.mkdir(exist_ok=False)
expected={'default':'库默认值','override':'显式覆盖','local':''.join(['料号','[x]','$',';',chr(34),chr(92),chr(10),'尾']),'displayLocation':[13,17],'otherDisplayLocation':[5,15],'effectiveValue':'1k','counts':{'schematic':2,'page':3,'part':4,'pin':8}}
(root/'expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');before={p.name:sha256(p) for p in sources.glob('*.dsn')};assert len(before)==4
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'checks':{}}
def maplayer(layer,name):return {p['name']:p['value'] for p in layer[name]}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==167;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.structured_content)
    Draft202012Validator(schemas[name]).validate(r.structured_content);return r.structured_content['data']
   for mode in ('base','override','empty','deleted'):
    ws=await call('cadence_create_workspace',{'sourceDesign':str(sources/(mode+'.dsn'))});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId'];assert opened['counts']==expected['counts']
    schematics=(await call('capture_query',{'sessionId':sid,'entity':'schematic','scope':{'kind':'design'}}))['items'];names={s['objectId']:s['name'] for s in schematics}
    parts=(await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'}}))['items'];layers=[];target=None
    for part in parts:
     args={'sessionId':sid,'partId':part['objectId']};layer=await call('capture_get_property_layers',args);assert layer['revision']==opened['revision']
     effective=maplayer(layer,'effective');user=maplayer(layer,'user');display={p['name']:p for p in layer['display']}
     is_target=names[part['schematicId']]=='ROOT' and part['reference']=='R1'
     wanted=(expected['override'] if mode=='override' else '' if mode=='empty' else expected['default']) if is_target else expected['default']
     assert effective['MCP_DEFAULT']==wanted,(mode,part,effective)
     if is_target:
      assert user['MCP_LOCAL']==effective['MCP_LOCAL']==expected['local']
      if mode in ('override','empty'):assert 'MCP_DEFAULT' in user and user['MCP_DEFAULT']==wanted
      else:assert 'MCP_DEFAULT' not in user
      target=(args,layer)
     else:assert 'MCP_LOCAL' not in user and 'MCP_LOCAL' not in effective and 'MCP_DEFAULT' not in user
     assert 'MCP_PACKAGE_ONLY' not in effective and 'MCP_PACKAGE_ONLY' not in user
     assert display['Value']['value']==effective['Value']==expected['effectiveValue'] and display['Value']['location']==expected['displayLocation' if is_target else 'otherDisplayLocation']
     assert 'Value' not in user and display['Part Reference']['value']==part['reference']
     plain=await call('capture_get_part_properties',args);assert plain['items']==layer['effective']
     layers.append({'schematic':names[part['schematicId']],**layer})
    assert target
    for _ in range(3):assert await call('capture_get_property_layers',target[0])==target[1]
    directory=root/'work'/ws['workspaceId'];assert not list(directory.glob('property-layers-*.json')) and not list(directory.glob('part-properties-*.json'))
    wrong=await client.call_tool('capture_get_property_layers',{'sessionId':sid,'partId':'schematic-999/page-1/part-1'});assert wrong.is_error and wrong.structured_content['error']['code']=='object_not_found'
    # Snapshot remains source-bound; no stale property reads after private copy changes.
    with (directory/'design.dsn').open('ab') as stream:stream.write(b'OWNED_PROPERTY_STALE_TEST')
    r=await client.call_tool('capture_get_property_layers',target[0]);assert r.is_error and r.structured_content['error']['code']=='target_changed'
    await call('capture_close',{'sessionId':sid});r=await client.call_tool('capture_get_property_layers',target[0]);assert r.is_error and r.structured_content['error']['code']=='session_lost'
    report['cases'].append({'case':mode,'passed':True,'opened':opened,'layers':layers});print(mode,'passed',flush=True)
  report['checks']={'native_default_override_empty_delete_fallback':True,'unicode_and_control_characters_roundtrip':True,'duplicate_references_and_display_coordinates_isolated':True,'effective_reader_consistent':True,'repeat_reads_and_transient_cleanup':True,'wrong_target_stale_and_closed_rejected':True,'sources_oracle_unchanged':before=={p.name:sha256(p) for p in sources.glob('*.dsn')} and sha256(root/'expected.json')==oracle}
  report['passed']=len(report['cases'])==4 and all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
