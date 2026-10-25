from pathlib import Path
import argparse,json
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),45)
expected={'schematics':['ROOT'],'pages':['MAIN'],'wires':[[[100,100],[300,100]]],'parts':0,'pins':0}
write_json(root/'expected.json',expected);oracle=sha256(root/'expected.json');report={'scope':'private constructor comparison; production readers unchanged','allCasesPassed':False,'cases':[]}
for mode in ('default','expand_before','expand_after','get_root_occurrence'):
    directory=root/mode;directory.mkdir();row={'mode':mode,'passed':False};report['cases'].append(row)
    try:
        process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'fixture_wire_expansion.tcl',cfg.install_root,mode,directory,directory/'receipt.json'],directory,process_env(cfg),45)
        row['process']=process;row['receipt']=json.loads((directory/'receipt.json').read_text(encoding='utf-8'))
        assert process['returnCode']==0 and process['remainingOwnedProcesses']==0 and row['receipt']['saved']
        target=directory/'design.dsn';before=sha256(target)
        try:
            run_tcl(cfg,'inspect.tcl',[str(target),str(directory/'definitions.json'),'100000'],directory)
            definitions=json.loads((directory/'definitions.json').read_text(encoding='utf-8'))
            assert [s['name'] for s in definitions['schematic']]==expected['schematics'] and [p['name'] for p in definitions['page']]==expected['pages'] and not definitions['part'] and not definitions['pin']
            run_tcl(cfg,'inspect_page_objects.tcl',[str(target),str(directory/'connections.json'),'connections'],directory)
            data=json.loads((directory/'connections.json').read_text(encoding='utf-8'))
            assert [o['attributes']['points'] for o in data['objects'] if o['kind']=='wire']==expected['wires'] and all(o['kind']=='wire' for o in data['objects'])
            row['passed']=True
        except Exception as error:row['readError']=str(error)
        out=directory/'page-status.json'
        diagnostic=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'probe_page_status.tcl',cfg.install_root,target,out],directory,process_env(cfg),45)
        assert diagnostic['returnCode']==0;row['nativePageStatus']=json.loads(out.read_text(encoding='utf-8'))['rows'][-1]
        row['sourceUnchanged']=sha256(target)==before;row['passed']=row['passed'] and row['sourceUnchanged']
    except BaseException as error:row['error']=str(error)
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'mode':mode,'passed':row['passed'],'nativePageStatus':row.get('nativePageStatus'),'error':row.get('error'),'readError':row.get('readError')}),flush=True)
report['oracleUnchanged']=sha256(root/'expected.json')==oracle;report['allCasesPassed']=all(r['passed'] for r in report['cases']) and report['oracleUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
