"""Native scalar NC add/remove and connected-pin/old-flag negative fixtures."""
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
def read(src,d,name,script,extra):
 out=d/(name+'.json');run_tcl(cfg,script,[str(src),str(out),*extra],d);return json.loads(out.read_text(encoding='utf-8'))
report={'passed':False,'sourceBefore':sha256(a.source),'cases':[]}
try:
 data=read(a.source,root,'baseline-def','inspect.tcl',['100000']);objects=read(a.source,root,'baseline-connections','inspect_page_objects.tcl',['connections'])['objects'];page=next(p for p in data['page'] if p['name']=='MCP_PLACE')
 expected=copy.deepcopy(objects);expected.append({'kind':'nc','pageId':page['objectId'],'attributes':{'partId':'expected','pinId':'expected','reference':'R101','number':'1','hotSpot':[290,310]}})
 write_json(root/'expected.json',{'definitionDigest':definition_baseline(data),'withNcDigest':connection_digest(data,expected),'withoutNcDigest':connection_digest(data,objects),'ncReference':'R101','ncNumber':'1','ncHotSpot':[290,310]})
 for name,number,old,new,source in [('add','1',0,1,a.source),('remove','1',1,0,root/'add/design.dsn'),('connected','2',0,1,a.source),('wrong_old','1',1,0,a.source)]:
  d=root/name;d.mkdir();target=d/'design.dsn';shutil.copyfile(source,target);before=sha256(target);row={'case':name,'passed':False};report['cases'].append(row)
  try:
   row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_nc_edit.tcl'),str(cfg.install_root),str(target),str(d/'receipt.json'),number,str(old),str(new)],d,process_env(cfg),60)
   row['receipt']=json.loads((d/'receipt.json').read_text())
   after=read(target,d,'definition','inspect.tcl',['100000']);actual=read(target,d,'connections','inspect_page_objects.tcl',['connections'])['objects']
   row['definitionMatches']=definition_baseline(after)==definition_baseline(data)
   row['connectionsMatch']=connection_digest(after,actual)==connection_digest(data,expected if name=='add' else objects)
   if name in ('connected','wrong_old'):
    row['rejectedBeforeMutation']=row['process']['returnCode']==1 and not row['receipt']['saved'] and row['receipt']['message']=={'connected':'connected_pin_refused','wrong_old':'old_flag_mismatch'}[name] and sha256(target)==before
   else:row['rejectedBeforeMutation']=True;assert row['process']['returnCode']==0 and row['receipt']['saved']
   row['passed']=row['definitionMatches'] and row['connectionsMatch'] and row['rejectedBeforeMutation'] and row['process']['remainingOwnedProcesses']==0
  except Exception as e:row['error']=str(e)
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(name,row['passed'],row.get('error'),flush=True)
 report['passed']=all(c['passed'] for c in report['cases'])
except Exception as e:report['error']=str(e)
report['sourceAfter']=sha256(a.source);report['passed'] &= report['sourceAfter']==report['sourceBefore'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}))
