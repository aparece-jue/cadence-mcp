"""Native cache-replacement matrix; independent readers retain all evidence."""
import argparse,json,shutil,sys
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,run_tcl,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.library import LibraryService
from cadence_mcp.library_edit import LibraryPinEdits
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();a.source=a.source.resolve(strict=True);a.install_root=a.install_root.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(a.source.parent,a.install_root),60)
report={'passed':False,'scope':'native cache replacement discovery; no public tool','sourceHashBefore':sha256(a.source),'cases':[]}
def read(script,source,directory,name,extra=False):
 out=directory/(name+'.json');args=[str(source),str(out)]+(['100000'] if extra else [])
 run_tcl(cfg,script,args,directory);return json.loads(out.read_text(encoding='utf-8'))
try:
 baseline=root/'baseline';baseline.mkdir()
 units=read('inspect_reference_units.tcl',a.source,baseline,'units')
 # Prepare explicit per-instance overrides on a fresh owned copy before replacement.
 original_source=a.source;prepared=root/'source-with-overrides.dsn';shutil.copyfile(a.source,prepared)
 for idx,(ref,prop,old,new) in enumerate([('R101','PCB Footprint','AXRC05','KEEP_USER_FP'),('R102','Value','1k','2k')]):
  u=next(u for u in units if u['reference']==ref)
  run_tcl(cfg,'edit_property.tcl',[str(prepared),str(root/('override-'+str(idx)+'.json')),u['partId'],'100000',prop,old,new,u['schematicName'],u['pageName'],ref],root)
 a.source=prepared;report['preparedSourceSha256']=sha256(prepared)
 units=read('inspect_reference_units.tcl',a.source,baseline,'prepared-units')
 selected=next(u for u in units if u['reference']=='R101');report['selected']=selected
 original=cfg.install_root/'tools/capture/library/pspice/analog.olb';report['librarySourceHashBefore']=sha256(original)
 library=LibraryService(cfg);opened=library.open(str(original));lid=opened['libraryId'];data=library.sessions[lid]['data']
 pkg=next(p for p in data['package'] if p['name']=='R');pin=next(p for p in data['pin'] if p['packageId']==pkg['objectId'] and p['number']=='1')
 writer=LibraryPinEdits(cfg,library);plan=writer.plan(lid,pin['objectId'],name='CACHE_INPUT');edit=writer.apply(plan['planId'],plan['planDigest'],'cache-probe-library')
 newlib=writer.root/('plan-'+plan['planId'])/'library.olb';report['libraryEdit']=edit
 before=read('inspect.tcl',a.source,baseline,'definition',True)
 cache=read('inspect_cache.tcl',a.source,baseline,'cache',True)
 report['baselineCacheNames']=[x['name'] for x in cache['package']]
 # Cache name and original source part are separate hypotheses; preserve both failures.
 affected=[u for u in units if u['packageName']==selected['packageName'] and u['sourceLib']==selected['sourceLib']]
 report['affected']=affected
 def detail(script,src,d,tag,part):
  out=d/(tag+'.json');run_tcl(cfg,script,[str(src),str(out),part['partId'],'100000','10000'],d);return json.loads(out.read_text(encoding='utf-8'))
 baseline_detail={}
 for i,part in enumerate(affected):
  baseline_detail[part['partId']]={kind:detail(script,a.source,baseline,kind+'-'+str(i),part) for kind,script in [('geometry','inspect_part_geometry.tcl'),('properties','inspect_part_properties.tcl')]}
 for selector in ('packageName',):
  for update in (0,1):
   case={'selector':selector,'update':update,'passed':False};report['cases'].append(case)
   d=root/(selector+'-'+str(update));d.mkdir();target=d/'design.dsn';shutil.copyfile(a.source,target)
   spec={'oldName':selected[selector],'oldLib':selected['sourceLib'],'newName':'R','newLib':str(newlib),'update':update,'restoreReferences':[{'nativeId':u['nativeId'],'reference':u['reference'],'preserveProperties':{p['name']:p['value'] for p in baseline_detail[u['partId']]['properties']['properties'] if p['name'] in ('Value','PCB Footprint')}} for u in affected]};write_json(d/'request.json',spec);case['request']=spec
   # Binding fields must change to the explicitly selected source, everything else stays.
   expected_details={}
   import copy
   for key,old in baseline_detail.items():
    wanted=copy.deepcopy(old)
    for pin in wanted['geometry']['pins']:
     if pin['number']=='1':pin['name']='CACHE_INPUT'
    binding={'Source Library':str(newlib).upper(),'Source Package':'R','Source Part':'R.Normal','Graphic':'R.Normal'}
    for prop in wanted['properties']['properties']:
     if prop['name'] in binding:prop['value']=binding[prop['name']]
    expected_details[key]=wanted
   write_json(d/'expected-details.json',expected_details)
   try:
    case['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'probe_cache_replace.tcl'),str(cfg.install_root),str(target),str(d/'request.json'),str(d/'native-result.json')],d,process_env(cfg),60)
    if (d/'native-result.json').exists():case['receipt']=json.loads((d/'native-result.json').read_text())
    after=read('inspect.tcl',target,d,'definition-after',True)
    case['definition']=after
    newunits=read('inspect_reference_units.tcl',target,d,'units-after');case['units']=newunits
    newcache=read('inspect_cache.tcl',target,d,'cache-after',True)
    case['cacheHasNewPin']=any(p['name']=='CACHE_INPUT' for p in newcache['pin'])
    # Known physical identity and all definition rows except changed pin name must hold.
    import copy
    expected=copy.deepcopy(before)
    for pin in expected['pin']:
     if pin['partId'] in baseline_detail and pin['number']=='1':pin['name']='CACHE_INPUT'
    case['definitionMatchesDeclared']=after==expected
    case['details']=[]
    for i,part in enumerate(affected):
     old=baseline_detail[part['partId']];actual={kind:detail(script,target,d,kind+'-'+str(i),part) for kind,script in [('geometry','inspect_part_geometry.tcl'),('properties','inspect_part_properties.tcl')]}
     wanted=expected_details[part['partId']]
     case['details'].append({'partId':part['partId'],'geometryMatches':actual['geometry']==wanted['geometry'],'propertiesMatch':actual['properties']==wanted['properties'],'before':old,'expected':wanted,'after':actual})
    case['passed']=case['process']['returnCode']==0 and case['cacheHasNewPin'] and case['definitionMatchesDeclared'] and all(v['geometryMatches'] and v['propertiesMatch'] for v in case['details'])
   except Exception as e:case.update(errorType=type(e).__name__,error=str(e))
   case['sourceUnchanged']=sha256(original_source)==report['sourceHashBefore'] and sha256(a.source)==report['preparedSourceSha256'];case['outputSha256']=sha256(target)
   (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   print(selector,update,case['passed'],case.get('receipt'),case.get('error'),flush=True)
 report['passed']=all(c['passed'] for c in report['cases'])
except BaseException as e:
 import traceback
 report.update(error=str(e),traceback=traceback.format_exc())
finally:
 report['sourceHashAfter']=sha256(original_source if 'original_source' in locals() else a.source)
 if 'original' in locals():report['librarySourceHashAfter']=sha256(original)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}))
