"""Actual stdio validation of original independent2-block complex data, generated afresh twice."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','expected-path'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);expected=json.loads(a.expected_path.read_text(encoding='utf-8'));original_oracle=sha256(a.expected_path);write_json(root/'expected.json',expected);oracle=sha256(root/'expected.json')
cfg=Config(a.install_root,root/'work',(root,),60);report={'passed':False,'scope':'synthetic DAT version9; no solver/job association and no public DAT writer','checks':{},'generations':[]}
for name in ('fresh-a','fresh-b'):
 directory=root/name;directory.mkdir();process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'fixture_complex_dat_v9.tcl',cfg.install_root,directory],directory,process_env(cfg),45)
 row={'label':name,'process':process,'log':(directory/'fixture.log').read_text(encoding='utf-8')};report['generations'].append(row)
 if process['returnCode']!=0 or process['remainingOwnedProcesses']!=0:
  report['error']='fresh_native_fixture_failed';(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');raise SystemExit(1)
 row['datSha256']=sha256(directory/'complex.dat')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(cfg.workspace_root),'--read-root',str(root),'--timeout-seconds','60'],env=process_env(cfg))
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==155;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    value=await client.call_tool(name,args);assert not value.is_error,(name,value.structured_content)
    Draft202012Validator(schemas[name]).validate(value.structured_content);return value.structured_content['data']
   opened=await call('pspice_dat_open',{'sourceDat':str(root/'fresh-a/complex.dat')});ident=opened['datId'];report['opened']=opened
   assert opened['blockCount']==2 and not opened['jobAssociationVerified'] and not opened['solverSuccessVerified']
   first=await call('pspice_dat_query',{'datId':ident,'entity':'block','offset':0,'limit':1});second=await call('pspice_dat_query',{'datId':ident,'entity':'block','offset':first['nextOffset'],'limit':1})
   blocks=first['items']+second['items'];assert [b['index'] for b in blocks]==[0,1] and all(b['complex'] and b['rowCount']==3 for b in blocks)
   report['observed']=[]
   for want in expected['blocks']:
    block=want['index'];traces=await call('pspice_dat_query',{'datId':ident,'entity':'trace','block':block,'limit':1000});assert {t['name'] for t in traces['items']}=={'Frequency','Gain'}
    observed={}
    for trace in ('Frequency','Gain'):
     rows=[];offset=0
     while True:
      page=await call('pspice_dat_samples',{'datId':ident,'block':block,'traceName':trace,'offset':offset,'limit':1});rows.extend(page['items'])
      assert not page['jobAssociationVerified'] and page['producedByPlan'] is None
      if trace=='Frequency':assert page['unit']=='Hz' and page['unitSource']=='axis_name_convention'
      else:assert page['unit'] is None and page['unitSource']=='unknown'
      if page['nextOffset'] is None:break
      offset=page['nextOffset']
     assert [v['real'] for v in rows]==want['frequency' if trace=='Frequency' else 'gainReal']
     assert [v['imaginary'] for v in rows]==([0,0,0] if trace=='Frequency' else want['gainImaginary'])
     observed[trace]=rows
    report['observed'].append({'block':block,'traces':observed})
   for block,row in [(1,0),(0,2),(1,2),(0,1)]:
    value=await call('pspice_dat_samples',{'datId':ident,'block':block,'traceName':'Gain','offset':row,'limit':1});want=expected['blocks'][block]
    assert value['items']==[{'index':row,'real':want['gainReal'][row],'imaginary':want['gainImaginary'][row]}]
   report['checks']['original_multiblock_complex_oracle_and_interleaved_paging']=True
   for args in [{'block':2,'traceName':'Gain'},{'block':0,'traceName':'MISSING'},{'block':0,'traceName':'Gain','offset':4}]:
    result=await client.call_tool('pspice_dat_samples',{'datId':ident,**args});assert result.is_error
   end=await call('pspice_dat_samples',{'datId':ident,'block':1,'traceName':'Gain','offset':3,'limit':1});assert end['items']==[] and end['complete']
   await call('pspice_dat_close',{'datId':ident});assert (await client.call_tool('pspice_dat_samples',{'datId':ident,'block':0,'traceName':'Gain'})).is_error
   report['checks']['missing_trace_block_and_row_bounds_closed_session_refused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   value=await fresh.call_tool('pspice_dat_open',{'sourceDat':str(root/'fresh-b/complex.dat')});assert not value.is_error;opened=value.structured_content['data'];ident=opened['datId']
   value=await fresh.call_tool('pspice_dat_samples',{'datId':ident,'block':1,'traceName':'Gain','offset':0,'limit':3});assert not value.is_error
   assert value.structured_content['data']['items']==[{'index':i,'real':r,'imaginary':j} for i,(r,j) in enumerate(zip(expected['blocks'][1]['gainReal'],expected['blocks'][1]['gainImaginary']))]
   copied=cfg.workspace_root/ident/'imported.dat';assert copied.resolve().is_relative_to(cfg.workspace_root)
   copied.write_bytes(copied.read_bytes()+b'OWNED_SNAPSHOT_TAMPER')
   result=await fresh.call_tool('pspice_dat_samples',{'datId':ident,'block':1,'traceName':'Gain'});assert result.is_error and result.structured_content['error']['code']=='target_changed'
   assert not (await fresh.call_tool('pspice_dat_close',{'datId':ident})).is_error
   report['checks']['new_generation_fresh_server_and_snapshot_tamper_refusal']=True
  report['checks']['sources_and_original_oracle_unchanged']=all(sha256(root/r['label']/'complex.dat')==r['datSha256'] for r in report['generations']) and sha256(a.expected_path)==original_oracle and sha256(root/'expected.json')==oracle
  report['passed']=all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
