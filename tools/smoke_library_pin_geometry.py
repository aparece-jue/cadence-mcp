"""Real MCP hotspot/visibility edits with prewritten declarations and independent reopens."""
import argparse,asyncio,copy,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
from cadence_mcp.library_vector_edit import vector_graph

p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);fixtures=a.fixture_root.resolve()
cases=[
 {'fixture':'single','part':'RES.Normal','position':0,'change':{'hotSpot':[-35,0]},'affected':1},
 {'fixture':'single','part':'RES.Convert','position':1,'change':{'visible':False},'affected':1},
 {'fixture':'shared_dual','part':'GATE.Normal','position':0,'change':{'hotSpot':[-45,10],'visible':False},'affected':2},
 {'fixture':'heterogeneous_power','part':'POWER.Normal','position':0,'change':{'hotSpot':[0,35],'visible':False},'affected':1},
]
# Exact independently authored part targets are checked against original declarations below.
specs={name:json.loads((fixtures/name/'spec.json').read_text(encoding='utf-8')) for name in ('single','shared_dual','heterogeneous_power')}
for case in cases:
    assert any(s['partName']==case['part'] and any(pin['position']==case['position'] for pin in s['pins']) for s in specs[case['fixture']]['symbols']),case
(root/'declarations.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
sources={n:fixtures/n/'library.olb' for n in specs}
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(fixtures),'--timeout-seconds','60'],env=env)
config=Config(a.install_root.resolve(),root/'oracle-work',(fixtures,),60)
def graph(source,tag):
    out=root/(tag+'.json');run_tcl(config,'inspect_library_create.tcl',[str(source),str(out),'100000','1'],root)
    return vector_graph(json.loads(out.read_text(encoding='utf-8')))
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
async def main():
    report={'passed':False,'cases':[],'sourceHashesBefore':{n:sha256(s) for n,s in sources.items()},'checks':{}}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
            for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            async def call(name,args,error=None):
                r=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(r.structured_content)
                if error:assert r.is_error and r.structured_content['error']['code']==error,r
                else:assert not r.is_error,r
                return r.structured_content['data']
            for i,case in enumerate(cases):
                source=sources[case['fixture']];before=graph(source,f'before-{i}');expected=copy.deepcopy(before)
                hits=[row for row in expected['definitions']['pin'] if row['scope'][-2:]==[case['part'],case['position']]]
                assert len(hits)==case['affected'],(case,hits)
                for row in hits:row.update(copy.deepcopy(case['change']))
                # Canonical definition ordering includes values; re-sort after declared edits.
                expected['definitions']['pin'].sort(key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False))
                dump(root/f'expected-{i}.json',expected);expected_hash=sha256(root/f'expected-{i}.json')
                opened=await call('capture_library_open',{'sourceLibrary':str(source)});lid=opened['libraryId']
                parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items']
                part=next(r for r in parts if r['name']==case['part'])
                pins=(await call('capture_library_query',{'libraryId':lid,'entity':'pin','limit':1000}))['items']
                target=next(r for r in pins if r['partId']==part['objectId'] and r['position']==case['position'])
                plan=await call('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],**case['change']});key={k:plan[k] for k in ('planId','planDigest')}
                assert len(plan['preview']['affected'])==case['affected']
                row={'case':case,'plan':plan};report['cases'].append(row);dump(root/'report.json',report)
                result=await call('capture_apply_library_pin_edit',{**key,'idempotencyKey':f'geometry-{i}'})
                assert result['modeledLibraryPreservationVerified'] and result['symbolGraphicsVerified']
                output=root/'work'/result['outputWorkspaceRelativePath']/'library.olb'
                assert graph(output,f'after-{i}')==expected
                assert sha256(root/f'expected-{i}.json')==expected_hash
                opened_output=await call('capture_open_edited_library',key)
                observed=(await call('capture_library_query',{'libraryId':opened_output['libraryId'],'entity':'pin','limit':1000}))['items']
                assert len(observed)==len(pins)
                row.update(result=result,expectedHash=expected_hash,outputHash=sha256(output))
                await call('capture_library_close',{'libraryId':lid});await call('capture_library_close',{'libraryId':opened_output['libraryId']})
                dump(root/'report.json',report);print(json.dumps({'case':i,'passed':True}),flush=True)
            # Original pin API fields remain compatible in one combined edit.
            opened=await call('capture_library_open',{'sourceLibrary':str(sources['single'])});lid=opened['libraryId']
            pins=(await call('capture_library_query',{'libraryId':lid,'entity':'pin','limit':1000}))['items'];target=pins[0]
            for bad in ({'hotSpot':[True,0]},{'hotSpot':[0,1,2]},{'hotSpot':[1000001,0]},{'visible':0},{'visible':'false'}):
                assert (await client.call_tool('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],**bad})).is_error
            await call('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],'hotSpot':target['hotSpot'],'visible':target['visible']},'no_change')
            pending=await call('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],'visible':False});pk={k:pending[k] for k in ('planId','planDigest')}
            await call('capture_cancel_library_pin_edit',pk);await call('capture_apply_library_pin_edit',{**pk,'idempotencyKey':'cancelled'},'write_not_replayed')
            combined=await call('capture_plan_library_pin_edit',{'libraryId':lid,'pinId':target['objectId'],'name':'CHANGED_LITERAL','number':'91','pinType':0,'hotSpot':[-50,0],'visible':False})
            ck={k:combined[k] for k in ('planId','planDigest')};cr=await call('capture_apply_library_pin_edit',{**ck,'idempotencyKey':'combined'})
            report['combined']={'plan':combined,'result':cr}
            report['toolCount']=len(tools);report['checks'].update(schema_boundaries=True,no_change=True,pending_cancel=True,combined_legacy_fields=True)
        async with Client(params,mode='legacy',read_timeout_seconds=120) as fresh:
            for i,row in enumerate(report['cases']):
                key={k:row['plan'][k] for k in ('planId','planDigest')}
                result=await fresh.call_tool('capture_apply_library_pin_edit',{**key,'idempotencyKey':f'geometry-{i}'});assert not result.is_error,result
                assert result.structured_content['data']['artifact']['sha256']==row['outputHash']
                recovered=await fresh.call_tool('capture_recover_library_pin_edit',key);assert not recovered.is_error,recovered
                output=root/'work'/row['result']['outputWorkspaceRelativePath']/'library.olb';assert sha256(output)==row['outputHash']
            row=report['cases'][-1];output=root/'work'/row['result']['outputWorkspaceRelativePath']/'library.olb'
            output.write_bytes(output.read_bytes()+b'owned tamper negative')
            r=await fresh.call_tool('capture_open_edited_library',{k:row['plan'][k] for k in ('planId','planDigest')});assert r.is_error and r.structured_content['error']['code']=='target_changed',r
        report['checks'].update(fresh_no_replay=True,independent_graph_reopens=True,terminal_tamper_refused=True);report['passed']=True
    except BaseException as error:report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    finally:
        report['sourceHashesAfter']={n:sha256(s) for n,s in sources.items()}
        if report['sourceHashesAfter']!=report['sourceHashesBefore']:report['passed']=False
        dump(root/'report.json',report)
    print(json.dumps({k:report.get(k) for k in ('passed','toolCount','checks','error')}));return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
