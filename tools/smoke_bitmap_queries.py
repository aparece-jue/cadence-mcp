"""Real stdio bitmap queries and fixed-reader graph preservation; private fixtures only."""
import argparse,asyncio,json,hashlib,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import process_env
from cadence_mcp.embedded_tcl import command
from cadence_mcp.process_tree import run_owned_process

p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source-a','source-b','source-shifted','legacy'):
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
sources={'A':a.source_a.resolve(strict=True),'B':a.source_b.resolve(strict=True),'shifted':a.source_shifted.resolve(strict=True),'legacy':a.legacy.resolve(strict=True)}
before={str(path/'library.olb'):sha256(path/'library.olb') for path in sources.values()}
expected={key:['bitmap',[0,0,20,20],[0,0],[2,2],56,hashlib.sha256((path/'pattern.bmp').read_bytes()[14:]).hexdigest()] for key,path in sources.items() if key!='legacy'}
assert expected['A']==expected['shifted'] and expected['A']!=expected['B']
write_json(root/'expected.json',expected);oracle=sha256(root/'expected.json')
cfg=Config(a.install_root,root/'worker',(root,*sources.values()),60)
env=process_env(cfg)
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(cfg.install_root),'--workspace-root',str(root/'work'),'--timeout-seconds','60',*[v for path in (root,*sources.values()) for v in ('--read-root',str(path))]],env=env)

async def main():
    report={'passed':False,'cases':[],'checks':{}}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=240) as client:
            async def call(name,args):
                value=await client.call_tool(name,args)
                assert not value.is_error,(name,value.structured_content)
                return value.structured_content['data']
            assert len((await client.list_tools()).tools)==155
            for label,path in sources.items():
                row={'label':label,'passed':False};report['cases'].append(row)
                opened=await call('capture_library_open',{'sourceLibrary':str(path/'library.olb')})
                lid=opened['libraryId'];row['opened']=opened
                parts=(await call('capture_library_query',{'libraryId':lid,'entity':'part','limit':1000}))['items']
                part=next(v for v in parts if v['name']=='GATE.Normal')
                args={'libraryId':lid,'partId':part['objectId'],'limit':5}
                page=await call('capture_query_library_vectors',args);items=list(page['items'])
                wrong=await client.call_tool('capture_query_library_vectors',{**args,'limit':3,'cursor':page['nextCursor']})
                assert wrong.is_error and wrong.structured_content['error']['code']=='stale_cursor'
                while page['nextCursor']:
                    page=await call('capture_query_library_vectors',{**args,'cursor':page['nextCursor']});items.extend(page['items'])
                bitmaps=[v for v in items if v['kind']=='bitmap']
                if label=='legacy':
                    assert not bitmaps and len(items)==13
                else:
                    assert len(items)==14 and len(bitmaps)==1 and bitmaps[0]['index']==13
                    assert bitmaps[0]['descriptor']==expected[label]
                    assert expected['B' if label=='A' else 'A']!=bitmaps[0]['descriptor'] if label in ('A','B') else True
                row['vectors']=items
                assert [v['index'] for v in items]==list(range(len(items)))
                await call('capture_library_close',{'libraryId':lid})
                bad=await client.call_tool('capture_query_library_vectors',args)
                assert bad.is_error and bad.structured_content['error']['code']=='session_lost'
                # Full fresh graph reader must hash images too, in a separately owned process.
                out=root/(label+'-graph.json')
                process=run_owned_process(command(cfg.install_root,'inspect_library_create.tcl',[path/'library.olb',out,'100000','1']),root,env,60)
                row['process']=process
                assert process['returnCode']==0 and process['remainingOwnedProcesses']==0 and process['rootExitSignalConfirmed']
                graph=json.loads(out.read_text(encoding='utf-8'))
                vectors=[v for s in graph['meta']['symbols'] for v in s['orderedVectors'] if v[0]=='bitmap']
                if label=='legacy':assert not vectors
                else:assert vectors and all(v==expected[label] for v in vectors)
                row['passed']=True
                print(label,True,flush=True)
        report['checks']['pixel_identity_and_legacy_queries']=True
        report['checks']['closed_sessions_and_cursors_refused']=True
        report['checks']['separate_process_full_graph_digest']=True
        report['checks']['sources_and_oracle_unchanged']=all(sha256(Path(path))==digest for path,digest in before.items()) and sha256(root/'expected.json')==oracle
        report['passed']=all(report['checks'].values())
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'error':report.get('error')}))
    return report['passed']

raise SystemExit(0 if asyncio.run(main()) else 1)
