"""Actual MCP new-design -> created-library placement -> scalar wire chain."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source-library'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.source_library.parent),'--timeout-seconds','60'],env=env)
def pin_expectations(refs,bound=False):
    return [{'schematicName':'CORE','pageName':'MAIN','reference':ref,'pinNumber':num,
             'connected':bound and (ref,num) in (('R501','2'),('R502','1')),
             'net':'MCP_LINK' if bound and (ref,num) in (('R501','2'),('R502','1')) else None}
            for ref in refs for num in ('1','2')]
(root/'expected.json').write_text(json.dumps({'root':'CORE','page':'MAIN','references':['R501','R502'],
    'locations':[[300,300],[500,300]],'wire':[[320,300],[480,300]],'finalPins':pin_expectations(['R501','R502'],True)},indent=2),encoding='utf-8')
async def main():
    report={'passed':False,'checks':{},'libraryHashBefore':sha256(a.source_library)}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
            for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            (root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            async def call(name,args,error=None):
                r=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(r.structured_content)
                if error:assert r.is_error and r.structured_content['error']['code']==error,r
                else:assert not r.is_error,r
                return r.structured_content['data']
            for values,code in [({'rootName':'../bad','pageName':'PAGE'},'invalid_document_name'),({'rootName':'根图','pageName':'PAGE'},'unsupported_design_encoding')]:
                await call('capture_plan_design_create',values,code)
            assert (await client.call_tool('capture_plan_design_create',{'rootName':'CORE','pageName':'MAIN','eval':'x'})).is_error
            plan=await call('capture_plan_design_create',{'rootName':'CORE','pageName':'MAIN'});key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
            result=await call('capture_apply_design_create',{**key,'idempotencyKey':'new-core'});report['result']=result
            assert result['artifact']['sourceKind']=='new_design_spec' and result['artifact']['sourceFingerprint']==plan['preview']['specDigest']
            assert result['artifact']['kind']=='capture_created_design' and result['rootAndPageCountsVerified']
            opened=await call('capture_open_edit_result',{**key,'kind':'design_create'});assert opened['counts']=={'schematic':1,'page':1,'part':0,'pin':0}
            pending=await call('capture_plan_design_create',{'rootName':'CANCEL','pageName':'PAGE'});pending_key={k:pending[k] for k in ('planId','planDigest')}
            await call('capture_cancel_design_create',pending_key);await call('capture_apply_design_create',{**pending_key,'idempotencyKey':'pending-cancel'},'write_not_replayed')
            library=await call('capture_library_open',{'sourceLibrary':str(a.source_library)})
            part=(await call('capture_library_query',{'libraryId':library['libraryId'],'entity':'part','packageName':'MCP_RES'}))['items'][0]
            refs=[];report['placements']=[]
            for reference,x in [('R501',300),('R502',500)]:
                sid=opened['sessionId'];page=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
                placement=await call('capture_plan_placement',{'sessionId':sid,'pageId':page['objectId'],'libraryId':library['libraryId'],'libraryPartId':part['objectId'],
                    'reference':reference,'location':[x,300],'value':'1k','expectedPins':[{'number':num,'name':name,'hotSpot':[x+dx,300],'connected':False,'net':None} for num,name,dx in [('1','A',-20),('2','B',20)]],
                    'expectedExistingConnections':pin_expectations(refs)})
                pk={k:placement[k] for k in ('planId','planDigest')};pr=await call('capture_apply_placement',{**pk,'idempotencyKey':reference})
                opened=await call('capture_open_edit_result',{**pk,'kind':'placement'});refs.append(reference)
                report['placements'].append({'plan':placement,'result':pr});print(json.dumps({'placed':reference,'passed':True}),flush=True)
            sid=opened['sessionId'];page=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'][0]
            wire=await call('capture_plan_wire_add',{'sessionId':sid,'pageId':page['objectId'],'start':[320,300],'end':[480,300],'netName':'MCP_LINK','expectedConnections':pin_expectations(refs,True)})
            wk={k:wire[k] for k in ('planId','planDigest')};wr=await call('capture_apply_wire_add',{**wk,'idempotencyKey':'link-created-design'})
            final=await call('capture_open_edit_result',{**wk,'kind':'wire_add'});report.update(wirePlan=wire,wireResult=wr,final=final)
            assert final['counts']=={'schematic':1,'page':1,'part':2,'pin':4}
            tamper=await call('capture_plan_design_create',{'rootName':'TAMPER','pageName':'PAGE'});tk={k:tamper[k] for k in ('planId','planDigest')}
            tr=await call('capture_apply_design_create',{**tk,'idempotencyKey':'tamper-created'});report['tamperPlan']=tamper
            path=root/'work'/tr['outputWorkspaceRelativePath']/'design.dsn';path.write_bytes(path.read_bytes()+b'owned design tamper negative')
            await call('capture_open_edit_result',{**tk,'kind':'design_create'},'target_changed')
            assert len((await call('capture_design_create_jobs',{}))['jobs'])==3
            report['checks'].update(strict_schemas=True,creation_source_kind=True,pending_cancel=True,jobs=True,tamper_rejected=True,blank_design_two_parts_wire_chain=True)
            report['toolCount']=len(tools)
        async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
            r=await fresh.call_tool('capture_apply_design_create',{**key,'idempotencyKey':'new-core'});assert not r.is_error and r.structured_content['data']['artifact']['sha256']==result['artifact']['sha256']
            r=await fresh.call_tool('capture_open_edit_result',{**key,'kind':'design_create'});assert not r.is_error and r.structured_content['data']['counts']['part']==0
        report['checks']['fresh_server_no_replay']=True;report['passed']=True
    except BaseException as error:report.update(errorType=type(error).__name__,error=str(error))
    finally:
        report['libraryHashAfter']=sha256(a.source_library)
        if report['libraryHashBefore']!=report['libraryHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','toolCount','checks','error')}))
    return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
