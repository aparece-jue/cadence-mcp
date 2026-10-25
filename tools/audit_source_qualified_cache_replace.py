"""Read-only audit of original replacements: exact cache source, logical metadata, all effective properties and views."""
import argparse,copy,json,collections
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_cache_bindings import query_cache_binding
from cadence_mcp.capture_edit import read_design_properties
from cadence_mcp.library import LibraryService
from cadence_mcp.library_semantics import library_graph
from cadence_mcp.environment import run_tcl

p=argparse.ArgumentParser()
for name in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);fixture=a.fixture_root;prior=json.loads((fixture/'report.json').read_text(encoding='utf-8'))
source=fixture/'source-with-overrides.dsn';library_path=Path(prior['cases'][0]['request']['newLib']);library_before=sha256(library_path);source_before=sha256(source)
c=Config(a.install_root,root/'work',(fixture,library_path.parent),60)
cap=CaptureService(c);libraries=LibraryService(c);opened=libraries.open(str(library_path));libdata=libraries.sessions[opened['libraryId']]['data'];package=next(p for p in libdata['package'] if p['name']=='R')
def subset(data,pkg):return {kind:[r for r in values if (r['objectId'] if kind=='package' else r['packageId'])==pkg] for kind,values in data.items()}
source_graph=library_graph(subset(libdata,package['objectId']))
def snapshot(source):
 ws=cap.create_workspace(str(source));sid=cap.open(ws['workspaceId'])['sessionId'];target=next(p for p in cap.sessions[sid]['data']['part'] if p['reference']=='R101');binding=query_cache_binding(cap,sid,target['objectId']);return sid,binding,cap.sessions[sid]['qualifiedCache']
def groups(snapshot):
 result=[];data=snapshot['definitions'];origins={r['cachePackageId']:r for r in snapshot['origins']}
 for package in data['package']:
  o=origins[package['objectId']];result.append({'isCached':o['isCached'],'sourceLibrary':o['sourceLibrary'].casefold(),'packageName':package['name'],'graph':library_graph(subset(data,package['objectId']))})
 return result
def canonical(rows):return sorted(rows,key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))
report={'passed':False,'mutationReplayed':False,'cases':[],'originalReportStillFailed':not prior['passed']}
try:
 sid,old_binding,before=snapshot(source);before_groups=groups(before);old=old_binding['binding'];before_properties=read_design_properties(c,source,root)
 for index,row in enumerate(prior['cases']):
  target=fixture/(row['selector']+'-'+str(row['update']))/'design.dsn';target_before=sha256(target);request=row['request']
  wanted_props=copy.deepcopy(before_properties)
  for prop_row in wanted_props:
   if prop_row['scope'][:2]!=['HALFADD','MCP_PLACE'] or prop_row['scope'][2] not in ('R101','R102'):continue
   for prop in prop_row['properties']:
    bindings={'Source Library':request['newLib'].upper(),'Source Package':'R','Source Part':'R.Normal','Graphic':'R.Normal'}
    if prop['name'] in bindings:prop['value']=bindings[prop['name']]
  wanted_props=canonical(wanted_props)
  wanted_groups=copy.deepcopy(before_groups)
  matches=[g for g in wanted_groups if g['isCached'] and g['sourceLibrary']==old['sourceLibrary'].casefold() and g['packageName']==old['sourcePackage']]
  assert len(matches)==1
  wanted_groups.remove(matches[0]);wanted_groups.append({'isCached':True,'sourceLibrary':request['newLib'].casefold(),'packageName':'R','graph':source_graph})
  expected={'cacheGroups':canonical(wanted_groups),'properties':wanted_props};(root/f'expected-{index}.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2),encoding='utf-8');oracle=sha256(root/f'expected-{index}.json')
  new_sid,binding,after=snapshot(target);observed={'cacheGroups':canonical(groups(after)),'properties':read_design_properties(c,target,root)}
  (root/f'observed-{index}.json').write_text(json.dumps(observed,ensure_ascii=False,indent=2),encoding='utf-8')
  checks={'exactSourceQualifiedCacheAndUnrelatedDefinitions':observed['cacheGroups']==expected['cacheGroups'],'allEffectivePropertiesAndOverrides':observed['properties']==expected['properties'],'boundPackageMatchesSourceLibrary':library_graph(binding['definitions'])==source_graph}
  views=[]
  for reference in ('R101','R102'):
   output=root/f'view-{index}-{reference}.json'
   run_tcl(c,'inspect_placed_view.tcl',[str(target),str(library_path),str(output),'HALFADD','MCP_PLACE',reference,'R','','R.Normal'],root)
   view=json.loads(output.read_text(encoding='utf-8'));assert view['matches'] is True;views.append(view)
  checks['actualPlacedViewsMatchSource']=all(v['matches'] for v in views);checks['frozenInputsAndOracleUnchanged']=target_before==sha256(target) and oracle==sha256(root/f'expected-{index}.json')
  report['cases'].append({'update':row['update'],'checks':checks,'passed':all(checks.values()),'views':views,'outputSha256':target_before})
  cap.close(new_sid);print(json.dumps(report['cases'][-1]),flush=True)
 cap.close(sid)
 report['sourceUnchanged']=source_before==sha256(source);report['libraryUnchanged']=library_before==sha256(library_path)
 report['passed']=all(row['passed'] for row in report['cases']) and report['sourceUnchanged'] and report['libraryUnchanged']
except BaseException as error:
 import traceback
 report.update(errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
finally:(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'error':report.get('error')}))
raise SystemExit(0 if report['passed'] else 1)
