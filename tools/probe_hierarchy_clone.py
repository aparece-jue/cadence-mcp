"""Fixed native reused-child block fixture with predeclared definition/pose checks."""
import argparse,copy,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_wire import connection_digest
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(a.source.parent,),60)
def read(script,src,name,extras=()):
 out=root/(name+'.json');run_tcl(cfg,script,[str(src),str(out),*extras],root);return json.loads(out.read_text(encoding='utf-8'))
report={'passed':False,'scope':'reused internal child definition block clone probe','sourceBefore':sha256(a.source)}
try:
 before=read('inspect.tcl',a.source,'before-definition',['100000']);hbefore=read('inspect_hierarchy.tcl',a.source,'before-tree')
 target=next(x for x in before['part'] if x['reference']=='halfadd_A');geom=read('inspect_part_geometry.tcl',a.source,'before-geometry',[target['objectId'],'100000','10000'])
 connections=read('inspect_page_objects.tcl',a.source,'before-connections',['connections'])
 expected=copy.deepcopy(before);oid=target['pageId']+'/fixture-clone';expected['part'].append({**target,'objectId':oid,'reference':'halfadd_C'})
 for i,pin in enumerate([p for p in before['pin'] if p['partId']==target['objectId']]):expected['pin'].append({**pin,'objectId':oid+'/pin-'+str(i+1),'partId':oid,'reference':'halfadd_C','connected':False,'net':''})
 wanted=copy.deepcopy(geom);delta=[2000-geom['location'][0],2000-geom['location'][1]];wanted['reference']='halfadd_C';wanted['location']=[2000,2000]
 for pin in wanted['pins']:pin['hotSpot']=[v+d for v,d in zip(pin['hotSpot'],delta)]
 write_json(root/'expected.json',{'definitionDigest':definition_baseline(expected),'geometry':wanted,'occurrenceCount':23,'addedTopReference':'halfadd_C','addedChildCount':6,'connectionDigest':connection_digest(before,connections['objects'])})
 design=root/'design.dsn';shutil.copyfile(a.source,design)
 report['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'probe_hierarchy_clone.tcl'),str(cfg.install_root),str(design),str(root/'native-result.json')],root,process_env(cfg),60)
 if (root/'native-result.json').exists():report['receipt']=json.loads((root/'native-result.json').read_text())
 after=read('inspect.tcl',design,'after-definition',['100000']);hierarchy=read('inspect_hierarchy.tcl',design,'after-tree')
 new=next(x for x in after['part'] if x['reference']=='halfadd_C');actualgeom=read('inspect_part_geometry.tcl',design,'after-geometry',[new['objectId'],'100000','10000'])
 def geometry(g):return {k:sorted([{a:b for a,b in p.items() if a!='pinId'} for p in v],key=lambda p:p['name']) if k=='pins' else v for k,v in g.items() if k!='partId'}
 actualconn=read('inspect_page_objects.tcl',design,'after-connections',['connections'])
 clone=next(x for x in hierarchy if x['reference']=='halfadd_C')
 report['checks']={'definition':definition_baseline(after)==definition_baseline(expected),'geometry':geometry(actualgeom)==geometry(wanted),'count23':len(hierarchy)==23,'sixChildren':len([x for x in hierarchy if x['parentId']==clone['occurrenceId']])==6,'connections':connection_digest(after,actualconn['objects'])==connection_digest(before,connections['objects'])}
 report['passed']=report['process']['returnCode']==0 and all(report['checks'].values())
except BaseException as e:
 import traceback
 report.update(error=str(e),traceback=traceback.format_exc())
finally:
 report['sourceAfter']=sha256(a.source);report['passed'] &= report['sourceBefore']==report['sourceAfter']
 if (root/'design.dsn').exists():report['outputSha256']=sha256(root/'design.dsn')
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
