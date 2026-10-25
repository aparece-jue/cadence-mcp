"""Predeclared native global/offpage lifecycle oracles on isolated copies."""
import argparse,copy,json,shutil,sys
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.capture_alias_edit import definition_structure
from cadence_mcp.capture_wire import connection_digest
from cadence_mcp.page_net_partition import page_partition
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_part_edit import page_geometry
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source-root'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--cases',nargs='+',choices=('rename','move','rotation','mirror','delete'),default=['rename','move','rotation','mirror','delete'])
p.add_argument('--adapter',choices=('edit_net_symbol.tcl','edit_net_symbol_disconnect.tcl'),default='edit_net_symbol.tcl')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),60)
report={'passed':False,'scope':'native global/offpage edit, page pin-wire partition, all selected-page part geometry; no flat/cross-page claim','cases':[],'adapterSha256':sha256(ADAPTERS/a.adapter)}
def inspect(path,d,prefix):
 data=[]
 for script,suffix,extra in [('inspect.tcl','definition',['100000']),('inspect_page_objects.tcl','connections',['connections']),('inspect_net_symbol_bindings.tcl','bindings',[])]:
  out=d/(prefix+'-'+suffix+'.json');run_tcl(cfg,script,[str(path),str(out),*extra],d);data.append(json.loads(out.read_text()))
 return data[0],data[1]['objects'],data[2]
def geometry(path,d):
 cap=CaptureService(cfg);cap.workspaces['fixture']={'directory':d,'manifest':{'copiedFingerprint':sha256(path)}};sid=cap.open('fixture')['sessionId']
 try:
  page=next(p for p in cap.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE');return page_geometry(cap,sid,page['objectId'])
 finally:cap.close(sid)
for kind,name in [('global','MCP_SUPPLY'),('offpage','MCP_LINK')]:
 src=(a.source_root/kind/'design.dsn').resolve(strict=True);source_hash=sha256(src)
 for case in a.cases:
  row={'case':kind+'-'+case,'passed':False,'sourceBefore':source_hash};report['cases'].append(row);d=root/row['case'];d.mkdir();target=d/'design.dsn';shutil.copyfile(src,target)
  try:
   data,objects,rows=inspect(target,d,'before');obj=next(o for o in objects if o['kind']==kind and o['attributes']['name']==name);old=obj['attributes'];page=next(p for p in data['page'] if p['objectId']==obj['pageId']);sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId']);scope=(sch['name'],page['name']);wire=next(r for r in rows if r['kind']=='wire' and r['points']==[[240,310],[290,310]]);key=[*scope,wire['nativeId']]
   before_geometry=geometry(target,d)
   spec={'schematicName':scope[0],'pageName':scope[1],'kind':kind,'nativeId':obj['nativeId'],'oldName':name,'oldLocation':old['location'],'oldRotation':old['rotationCode'],'oldMirror':old['mirrorCode'],'oldHotSpot':old['hotSpot'],'operation':'set_name' if case=='rename' else 'delete' if case=='delete' else 'set_pose','name':'MCP_RENAMED','location':old['location'],'rotation':0,'mirror':0}
   changed=copy.deepcopy(objects);wanted=next(o for o in changed if o['objectId']==obj['objectId'])
   expected_hot=old['hotSpot'];bound=True;expected_name=name
   if case=='rename':wanted['attributes']['name']='MCP_RENAMED';expected_name='MCP_RENAMED'
   elif case=='delete':changed.remove(wanted);expected_name=None
   else:
    if case=='move':spec['location']=[old['location'][0],old['location'][1]+100];expected_hot=[240,410]
    elif case=='rotation':spec['rotation']=1;expected_hot=[240,290] if kind=='global' else [250,300]
    else:spec['mirror']=1;expected_hot=[220,310] if kind=='global' else [240,310]
    wanted['attributes'].update(location=spec['location'],rotationCode=spec['rotation'],mirrorCode=spec['mirror'],hotSpot=expected_hot)
    bound=expected_hot==[240,310];expected_name=name if bound else None
   expected={'definitionStructure':definition_structure(data),'connections':connection_digest(data,changed),'partition':page_partition([r for r in rows if r['kind'] in ('pin','wire')],key),'geometry':before_geometry,'bound':bound,'expectedHotSpot':expected_hot,'expectedWireName':expected_name}
   write_json(d/'request.json',spec);write_json(d/'expected.json',expected)
   row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/a.adapter),str(cfg.install_root),str(target),str(d/'request.json'),str(d/'receipt.json')],d,process_env(cfg),60)
   row['receipt']=json.loads((d/'receipt.json').read_text());assert row['process']['returnCode']==0 and row['receipt']=={'saved':True,'operation':spec['operation']},'native mutation failed'
   after,actual,bindings=inspect(target,d,'after');row['structureMatches']=definition_structure(after)==expected['definitionStructure'];row['connectionObjectsMatch']=connection_digest(after,actual)==expected['connections'];row['partGeometryMatches']=geometry(target,d)==before_geometry
   filtered=[r for r in bindings if r['kind'] in ('pin','wire')];row['partitionMatches']=page_partition(filtered,key,expected_name)==expected['partition'];newwire=next(r for r in filtered if r['kind']=='wire' and [r['schematicName'],r['pageName'],r['nativeId']]==key);row['observedWireNet']=newwire['netName']
   if case=='delete':row['symbolBindingMatches']=not any(r['kind']==kind and (r['schematicName'],r['pageName'])==scope and r['name']==name for r in bindings)
   else:
    found=[r for r in bindings if r['kind']==kind and (r['schematicName'],r['pageName'])==scope and r['name']==('MCP_RENAMED' if case=='rename' else name)]
    assert len(found)==1,'symbol not unique';symbol=found[0];page_members=[r for r in filtered if (r['schematicName'],r['pageName'])==scope and r['group'] is not None]
    row['observedHotSpot']=symbol['hotSpot'];row['symbolBindingMatches']=symbol['hotSpot']==expected_hot and (symbol['group']==newwire['group'] if bound else all(symbol['group']!=r['group'] for r in page_members))
   row['sourceUnchanged']=sha256(src)==source_hash;row['passed']=all(row[k] for k in ('structureMatches','connectionObjectsMatch','partGeometryMatches','partitionMatches','symbolBindingMatches','sourceUnchanged'));row['outputSha256']=sha256(target)
  except Exception as e:row['error']=str(e)
  row['sourceAfter']=sha256(src);row['sourceUnchanged']=source_hash==row['sourceAfter'];row['passed'] &= row['sourceUnchanged']
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(row['case'],row['passed'],row.get('error'),flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
sys.exit(0 if report['passed'] else 1)
