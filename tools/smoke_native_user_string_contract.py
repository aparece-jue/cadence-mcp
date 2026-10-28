"""Native literal UserProp policy, verified against official information-model constraint."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];root=r/'.local/native-user-string-contract-20261028';root.mkdir(exist_ok=False)
source=r/'.local/typed-package-probe-v6-20261025/library.olb';before=sha256(source)
values={'NUMERIC_LITERAL':'00123','SCIENTIFIC_LITERAL':'1e3','BOOL_LITERAL':'False','EMPTY_LITERAL':'','UNICODE_LITERAL':'器件 00123'}
(root/'expected.json').write_text(json.dumps({'values':values,'nativeType':0,'originalTypedProbeStillNotTypedAcceptance':True},ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'nativeNonStringUserPropsAccepted':False,'fullL04Accepted':False}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
   async def call(name,args):
    value=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(value.structured_content);assert not value.is_error,value
    return value.structured_content['data']
   opened=await call('capture_library_open',{'sourceLibrary':str(source)});lid=opened['libraryId']
   packages=(await call('capture_library_query',{'libraryId':lid,'entity':'package','limit':1000}))['items'];package=next(p for p in packages if p['name']=='MCP_RESVAR');pid=package['objectId']
   current=await call('capture_query_library_package_properties',{'libraryId':lid,'packageId':pid});report['before']=current
   assert current['userPropertyValueContract']=={'storage':'native_string','automaticNumberOrBooleanParsing':False,'builtInDBProperties':'separate_typed_attributes'}
   assert all(p['nativeType']==0 and isinstance(p['value'],str) for p in current['properties']['userProperties'])
   jobs_before=await call('capture_library_package_edit_jobs',{})
   for value in (123,False,1.5):
    rejected=await client.call_tool('capture_plan_library_package_edit',{'libraryId':lid,'packageId':pid,'userProperties':[{'name':'BAD_TYPED','operation':'set','value':value}]});assert rejected.is_error
   jobs_after=await call('capture_library_package_edit_jobs',{});assert jobs_before==jobs_after
   plan=await call('capture_plan_library_package_edit',{'libraryId':lid,'packageId':pid,'userProperties':[{'name':name,'operation':'set','value':value} for name,value in values.items()]})
   key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
   result=await call('capture_apply_library_package_edit',{**key,'idempotencyKey':'native-user-string-contract'});report['result']=result
   output=await call('capture_open_edited_library',{**key,'kind':'package'});report['output']=output
   outid=output['libraryId'];outpackage=next(p for p in (await call('capture_library_query',{'libraryId':outid,'entity':'package','limit':1000}))['items'] if p['name']=='MCP_RESVAR')
   after=await call('capture_query_library_package_properties',{'libraryId':outid,'packageId':outpackage['objectId']});report['after']=after
   actual={p['name']:p for p in after['properties']['userProperties']}
   for name,value in values.items():assert actual[name]['value']==value and actual[name]['nativeType']==0
   for prop in current['properties']['userProperties']:assert actual[prop['name']]==prop
   again=await call('capture_apply_library_package_edit',{**key,'idempotencyKey':'native-user-string-contract'});assert not again['mutationReplayed']
   report.update(passed=True,literalStringSaveReopenAccepted=True,existingUserPropertiesPreserved=True,numericBooleanInputsRejectedBeforePlan=True,idempotenceAccepted=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourceUnchanged']=sha256(source)==before;report['oracleUnchanged']=sha256(root/'expected.json')==oracle
 report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged']
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','toolCount','error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
