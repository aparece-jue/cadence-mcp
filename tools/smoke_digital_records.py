"""Exercise dedicated digital records through a real MCP stdio server on private DAT copies."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for name in ('repo','output','install-root','legal-dat','flagged-dat','compressed-dat','mixed-dat','read-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();r=a.repo.resolve();root=a.output.resolve();root.mkdir(exist_ok=False,parents=True)
legal=a.legal_dat.resolve();flagged=a.flagged_dat.resolve();pure=a.compressed_dat.resolve();mixed=a.mixed_dat.resolve()
sources=[legal,flagged,pure,mixed];before={str(x):sha256(x) for x in sources}
report={'passed':False,'checks':{},'sourcesBefore':before,'fullP04Accepted':False}
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(a.read_root.resolve())],env=env)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=60) as c:
   async def call(n,args):
    out=await c.call_tool(n,args)
    if out.is_error:raise AssertionError((n,out.structured_content))
    return out.structured_content['data']
   report['toolCount']=len((await c.list_tools()).tools);assert report['toolCount']==204
   for path,kind in [(legal,'six_states'),(mixed,'mixed'),(pure,'compressed')]:
    opened=await call('pspice_dat_open',{'sourceDat':str(path)});ident=opened['datId']
    traces=(await call('pspice_dat_query',{'datId':ident,'entity':'trace','block':0,'limit':1000}))['items']
    trace=next(t for t in traces if t.get('signalType')=='digital');name=trace['aliases'][0] if kind=='compressed' else trace['name']
    result=await call('pspice_dat_digital_samples',{'datId':ident,'block':0,'traceName':name})
    assert result==await call('pspice_dat_digital_samples',{'datId':ident,'block':0,'traceName':name})
    assert all(set(row)=={'index','time','state','stateCode','strengthCode'} for row in result['items'])
    if kind=='six_states':
     assert [row['state'] for row in result['items']]==list('0R1F0XZZ')
     assert [row['strengthCode'] for row in result['items']]==[25,41,41,41,25,41,0,0]
     assert all(abs(row['time']-i*1e-6)<1e-15 for i,row in enumerate(result['items']))
    elif kind=='compressed':
     assert result['blockDigitalRows']==7090 and result['total']==4
     assert result['trace']=='INIT' and result['requestedTrace']=='U4:INIT'
     page=await call('pspice_dat_digital_samples',{'datId':ident,'block':0,'traceName':name,'offset':1,'limit':2});assert page['items']==result['items'][1:3] and page['nextOffset']==3
     out=await c.call_tool('pspice_dat_digital_samples',{'datId':ident,'block':0,'traceName':name,'offset':5});assert out.is_error and out.structured_content['error']['code']=='invalid_query'
     run=await call('pspice_dat_digital_samples',{'datId':ident,'block':0,'traceName':'RUN'});assert run['total']==4
    else:assert [row['state'] for row in result['items']]==list('010ZZ')
    for unsafe in ['Time','MISSING']:
     out=await c.call_tool('pspice_dat_digital_samples',{'datId':ident,'block':0,'traceName':unsafe});assert out.is_error and out.structured_content['error']['code']=='trace_not_found'
    report['checks'][kind]=True;report[kind]=result
    await call('pspice_dat_close',{'datId':ident});out=await c.call_tool('pspice_dat_digital_samples',{'datId':ident,'block':0,'traceName':name});assert out.is_error and out.structured_content['error']['code']=='session_lost'
   ident=(await call('pspice_dat_open',{'sourceDat':str(flagged)}))['datId']
   out=await c.call_tool('pspice_dat_digital_samples',{'datId':ident,'block':0,'traceName':'DIN','limit':1})
   assert out.is_error and out.structured_content['error']['code']=='unsupported_digital_state_flags';report['checks']['flagged_full_trace_refusal']=True
   await call('pspice_dat_close',{'datId':ident});report['passed']=True
 except Exception as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourcesUnchanged']=all(sha256(Path(path))==digest for path,digest in before.items());report['passed']=report['passed'] and report['sourcesUnchanged']
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ['passed','error','checks','sourcesUnchanged']}))
asyncio.run(main())
