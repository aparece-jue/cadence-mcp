"""Actual MCP native line-color save/reopen and unchanged baseline acceptance."""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config, sha256
from cadence_mcp.capture_graphic_line import read_lines


async def run(args, root, report):
    source=args.source.resolve(strict=True);before=sha256(source)
    params=StdioServerParameters(command=sys.executable,args=['-B','-m','cadence_mcp.server',
        '--install-root',str(args.install_root),'--workspace-root',str(root/'work'),
        '--read-root',str(source.parent)],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
    plans=[]
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
            tools=(await client.list_tools()).tools;assert len(tools)==245
            (root/'tools.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            schemas={t.name:t.output_schema for t in tools}
            async def call(name,values,error=None):
                result=await client.call_tool(name,values);Draft202012Validator(schemas[name]).validate(result.structured_content)
                if error:assert result.is_error and result.structured_content['error']['code']==error,result.structured_content
                else:assert not result.is_error,result.structured_content
                return result.structured_content['data']
            ws=await call('cadence_create_workspace',{'sourceDesign':str(source)})
            sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId']
            cfg=Config(args.install_root,root/'work',(root,),60);expected=[]
            for color in [1,8,47,48]:
                pages=await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}})
                page,=[p for p in pages['items'] if p['name']=='MCP_PLACE']
                base={'sessionId':sid,'pageId':page['objectId'],'start':[500,500],'end':[600,500],
                      'lineStyle':1,'lineWidth':1,'lineColor':color}
                if not expected:
                    for patch in [{'lineColor':0},{'lineColor':49},{'lineColor':True}]:
                        assert (await client.call_tool('capture_plan_graphic_line_add',{**base,**patch})).is_error
                    await call('capture_plan_graphic_line_add',{**base,'lineWidth':None},'invalid_graphic_stroke')
                plan=await call('capture_plan_graphic_line_add',base);key={k:plan[k] for k in ('planId','planDigest')}
                result=await call('capture_apply_graphic_line_add',{**key,'idempotencyKey':'color-'+str(color)})
                assert result['nativeColorVerified'] and result['nativeStrokeVerified'] and result['definitionAndConnectionBaselinePreserved']
                target=root/'work'/result['outputWorkspaceRelativePath']/'design.dsn'
                schematics=await call('capture_query',{'sessionId':sid,'entity':'schematic','scope':{'kind':'design'}})
                schematic,=[s for s in schematics['items'] if s['objectId']==page['schematicId']]
                rows=read_lines(cfg,target,target.parent,schematic['name'],'MCP_PLACE',True,True)
                expected.append(color)
                assert sorted((r['lineColor'],r['definitionColor']) for r in rows)==sorted((c,c) for c in expected),rows
                assert all(r['lineStyle']==1 and r['lineWidth']==1 and r['start']==[500,500] and r['end']==[600,500] for r in rows)
                opened=await call('capture_open_edit_result',{**key,'kind':'graphic_line'});sid=opened['sessionId']
                plans.append((key,result));report['cases'].append(dict(color=color,allReopenedColorPairs=[[r['lineColor'],r['definitionColor']] for r in rows],passed=True))
                print(json.dumps(report['cases'][-1]),flush=True)
            pending=await call('capture_plan_graphic_line_add',{**base,'sessionId':sid,'pageId':next(p['objectId'] for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'}}))['items'] if p['name']=='MCP_PLACE')})
            pending_key={k:pending[k] for k in ('planId','planDigest')};await call('capture_cancel_graphic_line_add',pending_key)
            assert (await client.call_tool('capture_apply_graphic_line_add',{**pending_key,'idempotencyKey':'cancel-color'})).is_error
        async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
            for key,result in plans:
                reply=await client.call_tool('capture_recover_graphic_line_add',key);assert not reply.is_error,reply.structured_content
                assert reply.structured_content['data']['artifact']['sha256']==result['artifact']['sha256']
            report.update(passed=True,freshRecoveryWithoutReplay=True,pendingCancel=True)
    except BaseException:
        import traceback
        report['error']=traceback.format_exc()
    finally:
        report['sourceSha256']=before;report['sourceUnchanged']=sha256(source)==before
        report['passed']=report['passed'] and report['sourceUnchanged']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','install-root','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();root=args.output.resolve();root.mkdir(exist_ok=False)
    (root/'expected.json').write_text(json.dumps({'colors':[1,8,47,48],'bothDefinitionAndInstance':True,'start':[500,500],'end':[600,500],'lineStyle':1,'lineWidth':1}),encoding='utf8')
    oracle_hash=sha256(root/'expected.json')
    report={'passed':False,'fullD05Accepted':False,'cases':[]};asyncio.run(run(args,root,report))
    report['oracleSha256']=oracle_hash;report['oracleUnchanged']=sha256(root/'expected.json')==oracle_hash;report['passed']=report['passed'] and report['oracleUnchanged']
    (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
