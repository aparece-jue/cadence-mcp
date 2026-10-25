"""Native scalar alias rename/move/delete discovery on independent saved copies."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(a.source.parent,),60)
def read(src,d,name,script,extra):
 out=d/(name+'.json');run_tcl(cfg,script,[str(src),str(out),*extra],d);return json.loads(out.read_text(encoding='utf-8'))
report={'passed':False,'cases':[],'sourceBefore':sha256(a.source)}
try:
 objects=read(a.source,root,'before-connections','inspect_page_objects.tcl',['connections']);alias=next(o for o in objects['objects'] if o['kind']=='alias' and o['attributes']['name']=='MCP_MIDDLE');wire=next(o for o in objects['objects'] if o['objectId']==alias['attributes']['wireId'])
 for case,op,name,loc in [('rename','set','MCP_RENAMED',[330,310]),('move','set','MCP_MIDDLE',[400,310]),('delete','delete','',[330,310])]:
  d=root/case;d.mkdir();target=d/'design.dsn';shutil.copyfile(a.source,target)
  spec={'schematicName':'HALFADD','pageName':'MCP_PLACE','wireNativeId':wire['nativeId'],'oldPoints':wire['attributes']['points'],'oldNet':wire['attributes']['net'],'aliasName':'MCP_MIDDLE','oldLocation':[330,310],'operation':op,'name':name,'location':loc};write_json(d/'request.json',spec);row={'case':case,'passed':False};report['cases'].append(row)
  try:
   row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'edit_alias.tcl'),str(cfg.install_root),str(target),str(d/'request.json'),str(d/'receipt.json')],d,process_env(cfg),60)
   row['receipt']=json.loads((d/'receipt.json').read_text());data=read(target,d,'definition','inspect.tcl',['100000']);obs=read(target,d,'connections','inspect_page_objects.tcl',['connections']);row['selectedPins']=[p for p in data['pin'] if p['reference'] in ('R101','R102')];row['selectedObjects']=[o for o in obs['objects'] if o['pageId']==alias['pageId']];row['passed']=row['process']['returnCode']==0
  except Exception as e:row['error']=str(e)
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(case,row['passed'],row.get('error'),flush=True)
 report['passed']=all(c['passed'] for c in report['cases'])
except Exception as e:report['error']=str(e)
report['sourceAfter']=sha256(a.source);report['passed'] &= report['sourceBefore']==report['sourceAfter'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
