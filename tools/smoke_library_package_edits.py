"""Actual package-property lifecycle with independent literal expectations."""
import argparse,asyncio,copy,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','library-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=(a.library_root/'library.olb').resolve(strict=True);before=sha256(source)
description='描述 Ω $[x];{literal}\nline 2'
def prop(name,value):return {'name':name,'value':value,'nativeType':0,'editable':1,'deletable':1}
def target(template,footprint,pcb,props):return {'packageName':'MCP_SECOND','referenceTemplate':template,'footprint':footprint,'pcbLibrary':pcb,'designator':template,'userPropsPermitted':1,'userProperties':sorted(props,key=lambda p:p['name'])}
cases=[
 {'name':'create-and-fixed','changes':{'referenceTemplate':'J?','footprint':'PKG_51','pcbLibrary':'PCB_LIB_51'},
  'users':[{'name':'Description','operation':'set','value':description},{'name':'MCP_NOTE','operation':'set','value':'initial $[x];'},{'name':'MCP_EMPTY','operation':'set','value':''}],
  'expected':target('J?','PKG_51','PCB_LIB_51',[prop('Description',description),prop('MCP_NOTE','initial $[x];'),prop('MCP_EMPTY','')])},
 {'name':'empty-and-update','changes':{},'users':[{'name':'MCP_NOTE','operation':'set','value':''},{'name':'Description','operation':'set','value':'Updated 中文\nsecond'}],
  'expected':target('J?','PKG_51','PCB_LIB_51',[prop('Description','Updated 中文\nsecond'),prop('MCP_NOTE',''),prop('MCP_EMPTY','')])},
 {'name':'delete-explicit','changes':{},'users':[{'name':'MCP_NOTE','operation':'delete','value':None},{'name':'MCP_EMPTY','operation':'delete','value':None}],
  'expected':target('J?','PKG_51','PCB_LIB_51',[prop('Description','Updated 中文\nsecond')])},
 {'name':'clear-fixed-and-last-user','changes':{'referenceTemplate':'Q?','footprint':'','pcbLibrary':''},'users':[{'name':'Description','operation':'delete','value':None}],
  'expected':target('Q?','','',[])},
 {'name':'restore-fixed','changes':{'referenceTemplate':'X?','footprint':'SECOND_FP','pcbLibrary':''},'users':[],
  'expected':target('X?','SECOND_FP','',[])}]
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[]};keys=[]
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
   async def call(name,args):
    r=await client.call_tool(name,args);assert not r.is_error,(name,r.content);return r.structured_content['data']
   ts=(await client.list_tools()).tools;assert len(ts)==155
   (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in ts],indent=2),encoding='utf-8')
   lid=(await call('capture_library_open',{'sourceLibrary':str(source)}))['libraryId'];original_lid=lid
   packages=(await call('capture_library_query',{'libraryId':lid,'entity':'package','limit':1000}))['items'];assert len(packages)==2
   package=next(p for p in packages if p['name']=='MCP_SECOND');original_pid=package['objectId']
   original=await call('capture_query_library_package_properties',{'libraryId':lid,'packageId':package['objectId']});assert original['properties']==target('X?','SECOND_FP','',[])
   other=next(p for p in packages if p['name']!='MCP_SECOND')
   untouched=(await call('capture_query_library_package_properties',{'libraryId':lid,'packageId':other['objectId']}))['properties']
   for case in cases:
    row={'case':case['name'],'passed':False};report['cases'].append(row)
    try:
     plan=await call('capture_plan_library_package_edit',{'libraryId':lid,'packageId':package['objectId'],'changes':case['changes'],'userProperties':case['users']});row['plan']=plan
     key={k:plan[k] for k in ('planId','planDigest')};result=await call('capture_apply_library_package_edit',{**key,'idempotencyKey':case['name']});row['result']=result
     assert result['packagePropertiesVerified'] and result['modeledLibraryPreservationVerified']
     opened=await call('capture_open_edited_library',{**key,'kind':'package'});row['opened']=opened;lid=opened['libraryId']
     saved=(await call('capture_library_query',{'libraryId':lid,'entity':'package','limit':1000}))['items'];assert len(saved)==2
     package=next(p for p in saved if p['name']=='MCP_SECOND');other=next(p for p in saved if p['name']!='MCP_SECOND')
     observed=await call('capture_query_library_package_properties',{'libraryId':lid,'packageId':package['objectId']});row['observed']=observed
     assert observed['properties']==case['expected'],(case['name'],observed['properties'],case['expected'])
     assert (await call('capture_query_library_package_properties',{'libraryId':lid,'packageId':other['objectId']}))['properties']==untouched
     pins=(await call('capture_library_query',{'libraryId':lid,'entity':'pin','limit':1000}))['items'];assert len(pins)==24
     row['passed']=True;keys.append((case['name'],key))
    except BaseException as e:
     import traceback
     row.update(error=str(e),traceback=traceback.format_exc());raise
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(case['name'],row['passed'],flush=True)
   total=(await call('capture_library_package_edit_jobs',{}))['total']
   base={'libraryId':original_lid,'packageId':original_pid}
   invalid=[({'changes':{'footprint':'SECOND_FP'}},'no_change'),
    ({'userProperties':[{'name':'PCB Footprint','operation':'set','value':'unsafe'}]},'reserved_or_duplicate_property'),
    ({'userProperties':[{'name':'MISSING','operation':'delete'}]},'invalid_package_edit'),
    ({'userProperties':[{'name':'MPN','operation':'set','value':'A'},{'name':'mpn','operation':'set','value':'B'}]},'reserved_or_duplicate_property')]
   for arguments,code in invalid:
    r=await client.call_tool('capture_plan_library_package_edit',{**base,**arguments});assert r.is_error and r.structured_content['error']['code']==code,(r.content,code)
   assert (await call('capture_library_package_edit_jobs',{}))['total']==total;report['invalidPlansHaveNoDurableJobs']=True
   extra=(await call('capture_library_open',{'sourceLibrary':str(source)}))['libraryId']
   epackage=next(p for p in (await call('capture_library_query',{'libraryId':extra,'entity':'package','limit':1000}))['items'] if p['name']=='MCP_SECOND')
   await call('capture_query_library_package_properties',{'libraryId':extra,'packageId':epackage['objectId']})
   copied=root/'work'/extra/'library.olb';copied.write_bytes(copied.read_bytes()+b'PRIVATE COPY TAMPER')
   r=await client.call_tool('capture_query_library_package_properties',{'libraryId':extra,'packageId':epackage['objectId']});assert r.is_error and r.structured_content['error']['code']=='target_changed'
   await call('capture_library_close',{'libraryId':extra})
   r=await client.call_tool('capture_query_library_package_properties',{'libraryId':extra,'packageId':epackage['objectId']});assert r.is_error and r.structured_content['error']['code']=='session_lost'
   report['cachedTamperAndClosedReadRefused']=True
  async with Client(params,mode='legacy',read_timeout_seconds=240) as fresh:
   for name,key in keys:
    r=await fresh.call_tool('capture_apply_library_package_edit',{**key,'idempotencyKey':name});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
    assert not (await fresh.call_tool('capture_recover_library_package_edit',key)).is_error
    r=await fresh.call_tool('capture_open_edited_library',{**key,'kind':'package'});assert not r.is_error
   report['freshLifecycleNoReplay']=True
  report['sourceAndOracleUnchanged']=sha256(source)==before and sha256(root/'expected.json')==oracle
  report['passed']=len(keys)==5 and report['sourceAndOracleUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
