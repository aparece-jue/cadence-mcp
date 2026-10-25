import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);config=Config(a.install_root.resolve(strict=True),root/'work',(root,),60)
expected={'create':{'schematic':['ROOT'],'page':[('ROOT','PAGE_ONE')]},'schematic_create':{'schematic':['ROOT','AUX'],'page':[('ROOT','PAGE_ONE'),('AUX','AUX_PAGE')]},'schematic_rename':{'schematic':['ROOT','AUX_RENAMED'],'page':[('ROOT','PAGE_ONE'),('AUX_RENAMED','AUX_PAGE')]},'schematic_delete':{'schematic':['ROOT'],'page':[('ROOT','PAGE_ONE')]},'page_delete':{'schematic':['ROOT','AUX'],'page':[('ROOT','PAGE_ONE')]}}
(root/'expected.json').write_text(json.dumps(expected,indent=2));report={'passed':False,'cases':[]};artifacts={}
for op in expected:
    row={'operation':op,'passed':False};report['cases'].append(row);directory=root/op;directory.mkdir();target=directory/'design.dsn'
    try:
        if op!='create':
            source=artifacts['create' if op=='schematic_create' else 'schematic_create'];shutil.copyfile(source,target);row['sourceHashBefore']=sha256(source)
        row['process']=run_owned_process(list(map(str,[config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'document_probe.tcl',config.install_root,target,directory/'native-result.json',op])),directory,process_env(config),60)
        if (directory/'native-result.json').exists():row['native']=json.loads((directory/'native-result.json').read_text(encoding='utf-8'))
        assert row['process']['state']=='exited' and row['process']['returnCode']==0,row.get('native',row['process'])
        cap=CaptureService(config);workspace=cap.create_workspace(str(target));opened=cap.open(workspace['workspaceId']);data=cap.sessions[opened['sessionId']]['data'];names={s['objectId']:s['name'] for s in data['schematic']}
        observed={'schematic':sorted(names.values()),'page':sorted((names[p['schematicId']],p['name']) for p in data['page'])};assert observed=={k:sorted(v) for k,v in expected[op].items()},observed
        assert not data['part'] and not data['pin'];row.update(passed=True,opened=opened,observed=observed,sha256=sha256(target));artifacts[op]=target
        if op!='create':row['sourceHashAfter']=sha256(source);assert row['sourceHashAfter']==row['sourceHashBefore']
    except BaseException as error:row.update(error=str(error),errorType=type(error).__name__)
report['passed']=all(c['passed'] for c in report['cases'])
(root/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'passed':report['passed'],'cases':[{k:c.get(k) for k in ('operation','passed','error')} for c in report['cases']],'report':str(root/'report.json')}))
