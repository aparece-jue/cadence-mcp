"""Fresh hierarchy-port graph discovery and independent readers, fixed fixture."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(root,),60)
expected={'root':'TOP','schematics':['TOP','CHILD'],'pages':['MAIN','CHILD_PAGE'],'block':'BLOCK_A','implementation':'CHILD','blockLocation':[400,300],'parentPinHotspots':{'IN':[400,320],'OUT':[500,320]},'childPorts':{'IN':{'hotSpot':[100,100],'pinType':0},'OUT':{'hotSpot':[300,100],'pinType':1}},'rule':'child IN and OUT connected by one native wire; parent boundary pins and child domain must map through CHILD ports'}
write_json(root/'expected.json',expected);report={'passed':False,'scope':'fresh parent-block/child-port graph discovery','readers':[]};target=root/'design.dsn'
try:
 report['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_hierarchy_ports.tcl'),str(cfg.install_root),str(target),str(root/'native-result.json')],root,process_env(cfg),60)
 if (root/'native-result.json').exists():report['receipt']=json.loads((root/'native-result.json').read_text())
 if not target.exists():raise ValueError('No saved design produced')
 before=sha256(target);report['savedHashBefore']=before
 for script,name,extras in [('inspect.tcl','definition',['100000']),('inspect_hierarchy.tcl','tree',[]),('inspect_page_objects.tcl','connections',['connections']),('inspect_occurrence_nets.tcl','flat',[])]:
  row={'reader':script,'passed':False};report['readers'].append(row);out=root/(name+'.json')
  try:run_tcl(cfg,script,[str(target),str(out),*extras],root);row.update(passed=True,output=name+'.json')
  except Exception as e:row['error']=str(e)
 report['savedHashAfter']=sha256(target);report['passed']=report['process']['returnCode']==0 and all(r['passed'] for r in report['readers']) and before==report['savedHashAfter']
except BaseException as e:report['error']=str(e)
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
