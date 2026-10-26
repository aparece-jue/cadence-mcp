import argparse,asyncio,json,math,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser(description='Original LowPassFilters R1=500 to1k MCP fixture; not a generic design editor.')
for name in ('workspace-root','source','install-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();r=Path(__file__).resolve().parents[1];root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);before=sha256(source)
assert before=='77dca668ad134b7159d94971d612152209524be9b7705688b1af719ccf9bf517'
oracle={'scope':'Original required P05 resistor change500ohm to1kohm, other circuit parameters fixed; complex voltages frozen before DSN mutation','sourceFingerprint':before,'change':{'reference':'R1','property':'Value','before':'500','after':'1k'},'cases':{}}
for label,resistor in [('before',500.),('after',1000.)]:
 values=[]
 for row,f in [(0,.1),(99,200.)]:
  for trace,z in [('V(N00509)',1/(1+resistor/1000+1j*2*math.pi*f*resistor*7e-6)),('V(N00813)',1000/(1000+1j*2*math.pi*f*2))]:values.append({'block':0,'row':row,'traceName':trace,'real':z.real,'imaginary':z.imag,'absoluteTolerance':2e-5,'relativeTolerance':1e-4})
 oracle['cases'][label]=values
(root/'expected.json').write_text(json.dumps(oracle,indent=2),encoding='utf-8');oracle_hash=sha256(root/'expected.json');report={'passed':False,'fullP05Accepted':False,'sourceBefore':before,'oracleSha256':oracle_hash}
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(root),'--timeout-seconds','60'],env=env)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=100) as c:
   async def call(name,args):
    out=await c.call_tool(name,args)
    if out.is_error:raise AssertionError((name,out.structured_content))
    return out.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
   parts=(await call('capture_query',{'sessionId':sid,'entity':'part','reference':'R1','scope':{'kind':'design'},'limit':1000}))['items'];assert len(parts)==1;part=parts[0]
   props=await call('capture_get_part_properties',{'sessionId':sid,'partId':part['objectId']});assert next(p['value'] for p in props['items'] if p['name']=='Value')=='500'
   plan=await call('capture_plan_property',{'sessionId':sid,'partId':part['objectId'],'propertyName':'Value','value':'1k'});report['propertyPlan']=plan;key={k:plan[k] for k in ('planId','planDigest')};(root/'property-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   result=await call('capture_apply_property',{**key,'idempotencyKey':'p05-resistor-value-once'});report['propertyResult']=result
   assert result['independentReopenVerified'] and result['definitionBaselinePreserved'] and result['observedValue']=='1k' and not result['electricalBehaviorVerified']
   output=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn';assert sha256(output)==result['artifact']['sha256'];report['modifiedDesign']=str(output);report['modifiedDesignSha256']=sha256(output);await call('capture_close',{'sessionId':sid})
  async with Client(params,mode='legacy',read_timeout_seconds=100) as c:
   out=await c.call_tool('capture_apply_property',{**key,'idempotencyKey':'p05-resistor-value-once'});assert not out.is_error and out.structured_content['data']==result;report['freshServerIdempotence']=True
   out=await c.call_tool('capture_open_edit_result',{**key,'kind':'property'});assert not out.is_error;sid=out.structured_content['data']['sessionId']
   out=await c.call_tool('capture_query',{'sessionId':sid,'entity':'part','reference':'R1','scope':{'kind':'design'}});assert not out.is_error;rows=out.structured_content['data']['items'];assert len(rows)==1
   out=await c.call_tool('capture_get_part_properties',{'sessionId':sid,'partId':rows[0]['objectId']});assert not out.is_error and next(p['value'] for p in out.structured_content['data']['items'] if p['name']=='Value')=='1k';report['freshServerReopenValueAccepted']=True
   await c.call_tool('capture_close',{'sessionId':sid});report['passed']=True
 except Exception as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourceAndOracleUnchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle_hash;report['passed']=report['passed'] and report['sourceAndOracleUnchanged'];(root/'property-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ['passed','error','modifiedDesign','modifiedDesignSha256','sourceAndOracleUnchanged']}))
asyncio.run(main())

if not report["passed"]:raise SystemExit(1)
