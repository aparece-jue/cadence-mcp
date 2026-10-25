"""Actual MCP read-only digital catalog; unsupported logic samples stay explicitly unavailable."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256,write_json
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-dat'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source_dat.resolve(strict=True);before=sha256(source)
expected={'sourceSha256':'1694bb1733d7d87ce8c0854972a248b972ef2acf0a9ea4670f4016b139aee1d5','blocks':1,'digitalRows':7090,'digitalColumns':212,'canonical':'INIT','aliases':['U4:INIT','U4.U2D:B','U4.U9A:CLRbar','U4.INIT']}
assert before==expected['sourceSha256'];write_json(root/'expected.json',expected);oracle=sha256(root/'expected.json')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=os.environ.copy())
async def main():
 report={'passed':False,'scope':'digital native catalog only; no validated logic-state samples or solver association','checks':{}}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==155;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    result=await client.call_tool(name,args);assert not result.is_error,(name,result.structured_content)
    Draft202012Validator(schemas[name]).validate(result.structured_content);return result.structured_content['data']
   opened=await call('pspice_dat_open',{'sourceDat':str(source)});ident=opened['datId'];report['opened']=opened
   assert opened['blockCount']==1 and opened['headerSource']=='native_direct_headers' and not opened['solverSuccessVerified'] and not opened['jobAssociationVerified']
   blocks=await call('pspice_dat_query',{'datId':ident,'entity':'block'});block=blocks['items'][0];report['block']=block
   assert block['dataTypeCode']==1 and block['digitalMetadataComplete'] and block['analogRowCount']==0 and block['analogTraceCount']==0
   assert block['digitalRowCount']==7090 and block['digitalTraceCount']==212 and block['rowCount']==7090
   assert block['analogReadSupported'] is False and block['digitalReadSupported'] is False
   rows=[];offset=0
   while True:
    page=await call('pspice_dat_query',{'datId':ident,'entity':'trace','block':0,'offset':offset,'limit':17});rows+=page['items']
    if page['nextOffset'] is None:break
    offset=page['nextOffset']
   assert len(rows)==212 and len({t['name'] for t in rows})==212
   assert all(t['signalType']=='digital' and t['rowCount']==7090 and t['sampleReadSupported'] is False and t['unit'] is None for t in rows)
   chosen=next(t for t in rows if t['name']=='INIT');assert chosen['aliases']==expected['aliases'];report['selected']=chosen
   report['traceNames']=[t['name'] for t in rows]
   report['checks']['native_counts_alias_grouping_and_paged_catalog']=True
   for name in ('INIT','U4:INIT','Time'):
    value=await client.call_tool('pspice_dat_samples',{'datId':ident,'block':0,'traceName':name})
    assert value.is_error and value.structured_content['error']['code']=='capability_unavailable'
   report['checks']['logic_values_not_misrepresented_as_analog']=True
   assert (await client.call_tool('pspice_dat_query',{'datId':ident,'entity':'trace','block':1})).is_error
   await call('pspice_dat_close',{'datId':ident})
   assert (await client.call_tool('pspice_dat_query',{'datId':ident,'entity':'block'})).is_error
   report['checks']['invalid_block_and_closed_session_refused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   value=await fresh.call_tool('pspice_dat_open',{'sourceDat':str(source)});assert not value.is_error;ident=value.structured_content['data']['datId']
   copied=root/'work'/ident/'imported.dat';assert copied.resolve().is_relative_to(root/'work')
   assert sha256(copied)==before;copied.write_bytes(copied.read_bytes()+b'OWNED_DIGITAL_SNAPSHOT_TAMPER')
   value=await fresh.call_tool('pspice_dat_query',{'datId':ident,'entity':'trace','block':0})
   assert value.is_error and value.structured_content['error']['code']=='target_changed'
   assert not (await fresh.call_tool('pspice_dat_close',{'datId':ident})).is_error
   report['checks']['fresh_snapshot_and_tamper_refusal']=True
  report['checks']['official_source_and_frozen_expected_unchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
  report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
