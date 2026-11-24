"""Actual MCP all-pose existing-line edits, exact deletion, and durable guards."""
import argparse
import asyncio
import copy
import json
import os
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture_graphic_line import read_lines


def clean(row):
    return {k:copy.deepcopy(v) for k,v in row.items() if k not in ('objectId','pageId','index')}


def transform(p,r,m):
    x,y=p
    if m:x=-x
    x,y=[(x,y),(y,-x),(-x,-y),(-y,x)][r]
    return [900+x,700+y]


async def run(a,root,report):
    sources=[a.prototype_root/('update-'+str(r)+'-'+str(m))/'design.dsn' for r in range(4) for m in range(2)]
    inputs=[*sources,a.base_source,a.prototype_root/'expected.json',a.prototype_root/'report.json']
    hashes={p:sha256(p) for p in inputs};prototype=json.loads((a.prototype_root/'report.json').read_text());assert prototype['passed']
    old_expected=json.loads((a.prototype_root/'expected.json').read_text())
    oracle=[]
    for r in range(4):
        for m in range(2):
            nr,nm=(r+1)%4,1-m
            change=dict(localStart=[-15,-10],localEnd=[45,35],location=[900,700],rotation=nr,mirror=nm,lineStyle=2,lineWidth=1,lineColor=47)
            oracle.append(dict(operation='update',oldRotation=r,oldMirror=m,change=change,expectedPoints=[transform(p,nr,nm) for p in [[-15,-10],[45,35]]]))
    oracle.extend(dict(operation='delete',index=i) for i in range(3))
    (root/'expected.json').write_text(json.dumps(oracle,indent=2)+'\n',encoding='utf8');oracle_hash=sha256(root/'expected.json')
    params=StdioServerParameters(command=sys.executable,args=['-B','-m','cadence_mcp.server','--install-root',str(a.install_root),
        '--workspace-root',str(root/'work'),'--read-root',str(a.prototype_root),'--read-root',str(a.base_source.parent)],
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
    plans=[]
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
            tools=(await client.list_tools()).tools;assert len(tools)==245
            (root/'tools.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            schemas={t.name:t.output_schema for t in tools}
            async def call(name,args,error=None):
                value=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(value.structured_content)
                if error:assert value.is_error and value.structured_content['error']['code']==error,value.structured_content
                else:assert not value.is_error,value.structured_content
                return value.structured_content['data']
            async def opened(source):
                ws=await call('cadence_create_workspace',{'sourceDesign':str(source)})
                sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
                pages=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items']
                page,=[p for p in pages if p['name']=='MCP_PLACE']
                rows=(await call('capture_query_page_vectors',{'sessionId':sid,'pageId':page['objectId'],'limit':1000}))['items']
                assert len(rows)==3 and all(r['kind']=='line' for r in rows)
                return ws,sid,page,rows
            for index,case in enumerate(oracle):
                source=sources[index] if case['operation']=='update' else a.base_source
                ws,sid,page,before=await opened(source);target_index=0 if case['operation']=='update' else case['index'];selected=before[target_index]
                request=dict(sessionId=sid,graphicId=selected['objectId'],operation=case['operation'])
                if case['operation']=='update':
                    frozen=old_expected[index]['target'];assert clean(selected)==frozen
                    request['change']=case['change']
                if index==0:
                    for value in [dict(request,graphicId='schematic-999/page-999/graphic-1'),dict(request,graphicId=page['objectId']+'/wire-1'),dict(request,change=dict(case['change'],mirror=True)),dict(request,change=dict(case['change'],lineColor=49))]:
                        assert (await client.call_tool('capture_plan_graphic_line_edit',value)).is_error
                    await call('capture_plan_graphic_line_edit',dict(request,operation='delete'),'invalid_graphic_line_edit')
                    await call('capture_plan_graphic_line_edit',dict(request,change=dict(case['change'],localEnd=[-15,-10])),'invalid_graphic_geometry')
                plan=await call('capture_plan_graphic_line_edit',request);key={k:plan[k] for k in ('planId','planDigest')}
                result=await call('capture_apply_graphic_line_add',{**key,'idempotencyKey':'existing-line-'+str(index)})
                assert result['modeledGraphicsAndInstancesPreserved'] and result['lineIdentitiesAndColorsPreserved'] and result['definitionAndConnectionBaselinePreserved']
                assert result['graphicRemovalVerified']==(case['operation']=='delete')
                out=await call('capture_open_edit_result',{**key,'kind':'graphic_line'})
                actual=(await call('capture_query_page_vectors',{'sessionId':out['sessionId'],'pageId':page['objectId'],'limit':1000}))['items']
                expected=[clean(r) for r in before]
                if case['operation']=='delete':del expected[target_index]
                else:
                    expected[0].update(location=[900,700],rotationCode=case['change']['rotation'],mirrorCode=case['change']['mirror'],
                        localDescriptor=['line',[-15,-10],[45,35],2,1],pageControlPoints=case['expectedPoints'])
                assert [clean(r) for r in actual]==expected
                target=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn'
                colors=read_lines(Config(a.install_root,root/'work',(root,),60),target,target.parent,'HALFADD','MCP_PLACE',True,True,True)
                expected_colors=[8,48,8] if case['operation']=='update' else [48,48,8]
                if case['operation']=='update':expected_colors[0]=47
                else:del expected_colors[target_index]
                assert [r['lineColor'] for r in colors]==expected_colors and [r['definitionColor'] for r in colors]==expected_colors
                plans.append((key,result));report['cases'].append(dict(operation=case['operation'],index=target_index,
                    oldPose=[case.get('oldRotation'),case.get('oldMirror')],artifactSha256=result['artifact']['sha256'],passed=True))
                await call('capture_close',{'sessionId':out['sessionId']});await call('capture_close',{'sessionId':sid})
                print(json.dumps(report['cases'][-1]),flush=True)
            # New source copies for cancellation and source-tamper guards; no failed job replay.
            ws,sid,page,rows=await opened(a.base_source)
            request=dict(sessionId=sid,graphicId=rows[0]['objectId'],operation='delete')
            pending=await call('capture_plan_graphic_line_edit',request);pending_key={k:pending[k] for k in ('planId','planDigest')}
            await call('capture_cancel_graphic_line_add',pending_key)
            assert (await client.call_tool('capture_apply_graphic_line_add',{**pending_key,'idempotencyKey':'cancel-edit'})).is_error
            stale=await call('capture_plan_graphic_line_edit',request);stale_key={k:stale[k] for k in ('planId','planDigest')}
            copied=root/'work'/ws['workspaceId']/'design.dsn';copied.write_bytes(copied.read_bytes()+b'owned stale-source negative')
            await call('capture_apply_graphic_line_add',{**stale_key,'idempotencyKey':'stale-edit'},'target_changed')
            await call('capture_close',{'sessionId':sid})
            report.update(pendingCancelRefused=True,staleSourceRefusedBeforeNative=True)
        async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
            for key,result in plans:
                reply=await client.call_tool('capture_recover_graphic_line_add',key);assert not reply.is_error,reply.structured_content
                recovered=reply.structured_content['data'];assert recovered['artifact']['sha256']==result['artifact']['sha256'] and not recovered.get('mutationReplayed',False)
            key,result=plans[-1];target=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn';original=target.read_bytes();target.write_bytes(original+b'owned terminal negative')
            reply=await client.call_tool('capture_recover_graphic_line_add',key);assert reply.is_error
            report['terminalTamperError']=reply.structured_content['error']['code'];target.write_bytes(original);assert sha256(target)==result['artifact']['sha256']
            report.update(terminalTamperRefused=True,terminalTestBytesRestored=True,freshRecoveryWithoutReplay=True,passed=True)
    except BaseException:
        import traceback
        report['error']=traceback.format_exc()
    finally:
        report['inputsUnchanged']=all(sha256(p)==h for p,h in hashes.items());report['oracleUnchanged']=sha256(root/'expected.json')==oracle_hash
        report['inputSha256']={str(p):h for p,h in hashes.items()};report['oracleSha256']=oracle_hash
        report['passed']=report['passed'] and report['inputsUnchanged'] and report['oracleUnchanged']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('install-root','prototype-root','base-source','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.prototype_root=a.prototype_root.resolve();a.base_source=a.base_source.resolve();root=a.output.resolve();root.mkdir(exist_ok=False)
    report=dict(passed=False,fullD05Accepted=False,cases=[]);asyncio.run(run(a,root,report))
    (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(passed=report['passed'],error=report.get('error'))))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
