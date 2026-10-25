"""Actual MCP source-bound net-symbol create tasks and verification guards."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);olb=(a.install_root/'tools/capture/library/capsym.olb').resolve(strict=True)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.source.parent),'--read-root',str(olb.parent),'--timeout-seconds','60'],env=env)
def expected(name,connected=True):return [{'schematicName':'HALFADD','pageName':'MCP_PLACE','reference':ref,'pinNumber':num,'connected':connected if (ref,num)==('R101','1') else (ref,num) in {('R101','2'),('R102','1')},'net':name if (ref,num)==('R101','1') and connected else 'MCP_MIDDLE' if (ref,num) in {('R101','2'),('R102','1')} else None} for ref in ('R101','R102') for num in ('1','2')]
async def main():
 report={'passed':False,'phase':'start','sourceBefore':sha256(a.source),'libraryBefore':sha256(olb),'cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   ts=(await client.list_tools()).tools;assert len(ts)==132;schemas={t.name:t.output_schema for t in ts}
   for t in ts:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   async def call(name,args):
    v=await client.call_tool(name,args);assert not v.is_error,v.content;Draft202012Validator(schemas[name]).validate(v.structured_content);return v.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(a.source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];pages=await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000});page=next(p for p in pages['items'] if p['name']=='MCP_PLACE');lib=await call('capture_library_open',{'sourceLibrary':str(olb)});lid=lib['libraryId'];symbols=(await call('capture_query_net_symbols',{'libraryId':lid,'limit':1000}))['items'];sym=lambda kind,name:next(s['symbolId'] for s in symbols if s['kind']==kind and s['name']==name)
   base={'sessionId':sid,'pageId':page['objectId'],'libraryId':lid,'symbolId':sym('global','VCC'),'name':'MCP_SUPPLY','location':[230,300],'expectedHotSpot':[240,310],'leadEnd':[290,310],'expectedConnections':expected('MCP_SUPPLY')}
   for bad in ({**base,'symbolId':sym('port','PORTLEFT-L')},{**base,'rotationCode':True},{**base,'leadEnd':[289,311]},{**base,'expectedConnections':expected('MCP_SUPPLY')[:-1]},{**base,'eval':'unsafe'}):assert (await client.call_tool('capture_plan_net_symbol_create',bad)).is_error
   cases=[('global','VCC','MCP_SUPPLY',[230,300],0,0),('offpage','OFFPAGELEFT-L','MCP_LINK',[240,300],0,0),('global','GND','MCP_GROUND',[240,300],1,1),('offpage','OFFPAGELEFT-L','MCP_LINK_R',[230,310],1,1)]
   for i,(kind,source,name,loc,rot,mirror) in enumerate(cases):
    report['phase']='native-'+str(i);args={**base,'symbolId':sym(kind,source),'name':name,'location':loc,'rotationCode':rot,'mirrorCode':mirror,'expectedConnections':expected(name)};plan=await call('capture_plan_net_symbol_create',args);key={k:plan[k] for k in ('planId','planDigest')};keys.append((str(i),key));run=await call('capture_apply_net_symbol_create',{**key,'idempotencyKey':str(i)});assert run['leadBindingVerified'] and run['designPassed'] is None and not run['occurrenceConnectivityVerified'];opened=await call('capture_open_edit_result',{**key,'kind':'net_symbol_create'});objects=await call('capture_query_connections',{'sessionId':opened['sessionId'],'entity':kind,'limit':1000});target=next(o for o in objects['items'] if o['attributes']['name']==name);assert target['attributes']['hotSpot']==[240,310] and target['attributes']['sourceSymbol']==plan['preview']['cacheName'];report['cases'].append({'plan':plan,'result':run,'query':objects})
   report['phase']='wrong-oracle'
   # Keep lead target valid while declaring an incorrect glyph origin/hotspot relation.
   bad=await call('capture_plan_net_symbol_create',{**base,'location':[231,300]});bk={k:bad[k] for k in ('planId','planDigest')};v=await client.call_tool('capture_apply_net_symbol_create',{**bk,'idempotencyKey':'wrong-origin'});assert v.is_error;assert (await client.call_tool('capture_open_edit_result',{**bk,'kind':'net_symbol_create'})).is_error;v=await client.call_tool('capture_apply_net_symbol_create',{**bk,'idempotencyKey':'wrong-origin'});assert v.is_error and v.structured_content['error']['code']=='write_not_replayed';report['wrongOriginOracleRejected']=True
   pending=await call('capture_plan_net_symbol_create',base);pk={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_net_symbol_create',pk);assert (await client.call_tool('capture_apply_net_symbol_create',{**pk,'idempotencyKey':'cancel'})).is_error;report['jobs']=await call('capture_net_symbol_create_jobs',{'offset':0,'limit':1})
  report['phase']='fresh_server'
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   for name,key in keys:
    v=await client.call_tool('capture_apply_net_symbol_create',{**key,'idempotencyKey':name});assert not v.is_error and not v.structured_content['data']['mutationReplayed'];assert not (await client.call_tool('capture_recover_net_symbol_create',key)).is_error;assert not (await client.call_tool('capture_open_edit_result',{**key,'kind':'net_symbol_create'})).is_error
   name,key=keys[-1];path=root/'work/isolated-jobs/capture_net_symbol_create'/('plan-'+key['planId'])/'design.dsn'
   with path.open('ab') as f:f.write(b'controlled-tamper-negative')
   v=await client.call_tool('capture_open_edit_result',{**key,'kind':'net_symbol_create'});assert v.is_error and v.structured_content['error']['code']=='target_changed';report['freshNoReplayAndTamperRejected']=True
  report['passed']=True
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report.update(sourceAfter=sha256(a.source),libraryAfter=sha256(olb));report['passed'] &= report['sourceAfter']==report['sourceBefore'] and report['libraryAfter']==report['libraryBefore'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'phase':report['phase'],'cases':len(report['cases']),'error':report.get('error')}))
asyncio.run(main())
