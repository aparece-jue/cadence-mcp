"""Independent page-native object partition acceptance of saved alias probes."""
import argparse,json,copy
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import run_tcl
from cadence_mcp.page_net_partition import page_partition
from cadence_mcp.capture_wire import connection_digest
from cadence_mcp.capture_edit import definition_baseline
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','fixture-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);fixture=a.fixture_root.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(root,),60)
def read(src,label,script,extra=()):
 out=root/(label+'.json');run_tcl(cfg,script,[str(src),str(out),*extra],root);return json.loads(out.read_text(encoding='utf-8'))
def structure(data):
 value=copy.deepcopy(data)
 for p in value['pin']:p['net']=''
 return definition_baseline(value)
report={'passed':False,'cases':[],'sourceBefore':sha256(a.source)}
try:
 baseline=read(a.source,'baseline-native','inspect_page_net_partition.tcl');defs=read(a.source,'baseline-def','inspect.tcl',['100000']);objects=read(a.source,'baseline-objects','inspect_page_objects.tcl',['connections'])['objects']
 alias=next(o for o in objects if o['kind']=='alias' and o['attributes']['name']=='MCP_MIDDLE');wire=next(o for o in objects if o['objectId']==alias['attributes']['wireId']);target=['HALFADD','MCP_PLACE',wire['nativeId']]
 expected_partition=page_partition(baseline,target,'MCP_MIDDLE');write_json(root/'expected.json',{'partition':expected_partition,'structureDigest':structure(defs),'wire':target,'semantics':'original pin/wire native memberships unchanged; target native net name alone may change'})
 for case,name,loc in [('rename','MCP_RENAMED',[330,310]),('move','MCP_MIDDLE',[400,310]),('delete',None,None)]:
  src=fixture/case/'design.dsn';before=sha256(src);row={'case':case,'passed':False};report['cases'].append(row)
  try:
   actual=read(src,case+'-native','inspect_page_net_partition.tcl');observed=read(src,case+'-def','inspect.tcl',['100000']);objs=read(src,case+'-objects','inspect_page_objects.tcl',['connections'])['objects'];expected=copy.deepcopy(objects)
   if case=='delete':expected=[o for o in expected if o['objectId']!=alias['objectId']]
   else:
    for o in expected:
     if o['objectId']==alias['objectId']:o['attributes'].update(name=name,location=loc)
   row['partitionMatches']=page_partition(actual,target,name)==expected_partition
   row['definitionStructureMatches']=structure(observed)==structure(defs);row['connectionObjectsMatch']=connection_digest(observed,objs)==connection_digest(defs,expected);row['fileUnchanged']=before==sha256(src)
   row['passed']=all(row[k] for k in ('partitionMatches','definitionStructureMatches','connectionObjectsMatch','fileUnchanged'))
  except Exception as e:row['error']=str(e)
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(case,row['passed'],row.get('error'),flush=True)
 report['passed']=all(c['passed'] for c in report['cases'])
except Exception as e:report['error']=str(e)
report['sourceAfter']=sha256(a.source);report['passed'] &= report['sourceAfter']==report['sourceBefore'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
