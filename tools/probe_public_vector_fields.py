"""Additional native declaration field matrix; failures retained independently."""
import argparse,copy,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates
from cadence_mcp.library_vector_query import query_library_vectors
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','specs-path'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--font-quality',type=int,choices=range(7),default=2)
p.add_argument('--cases',nargs='+',choices=('native_default_enums','unicode_multiline_literals','explicit_font_fields'))
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
base=json.loads(a.specs_path.read_text(encoding='utf-8'))['legacy'];source_hash=sha256(a.specs_path)
font8={'faceName':'Arial','height':8,'width':1,'weight':500,'strikeOut':True,'charSet':1,'outPrecision':3,'clipPrecision':1,'quality':a.font_quality,'pitchAndFamily':32}
cases={
 'native_default_enums':({'kind':'line','start':[0,0],'end':[20,10],'style':5,'width':3},['line',[0,0],[20,10],5,3]),
 'unicode_multiline_literals':({'kind':'text','text':'中文 Ω $[x];{literal}\nLine 2','bounds':[0,0,200,40]},['text','中文 Ω $[x];{literal}\nLine 2',[0,0],[0,0,200,40],['Arial',-11,0,0,0,400,0,0,0,0,7,0,1,16]]),
 'explicit_font_fields':({'kind':'text','text':'Font fields','bounds':[0,0,100,20],'font':font8},['text','Font fields',[0,0],[0,0,100,20],['Arial',8,1,0,0,500,0,0,1,1,3,1,a.font_quality,32]])
}
report={'passed':False,'cases':[]}
for name,(vector,expected) in cases.items():
 if a.cases and name not in a.cases:continue
 row={'case':name,'passed':False};report['cases'].append(row)
 d=root/name;d.mkdir();s=copy.deepcopy(base)
 for symbol in s['symbols']:symbol['vectors']=[copy.deepcopy(vector)]
 (d/'spec.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
 (d/'expected.json').write_text(json.dumps(expected,ensure_ascii=False),encoding='utf-8');oracle=sha256(d/'expected.json')
 try:
  cfg=Config(a.install_root,d/'work',(d,),60);library=LibraryService(cfg);creator=LibraryCreates(cfg,library)
  plan=creator.plan(s);row['plan']=plan;result=creator.apply(plan['planId'],plan['planDigest'],name);row['result']=result
  opened=creator.open_output(plan['planId'],plan['planDigest']);part=library.sessions[opened['libraryId']]['data']['part'][0]
  query=query_library_vectors(library,opened['libraryId'],part['objectId']);actual=query['items'][-1]['descriptor']
  actual=actual[:-1] if actual[0]=='text' else actual
  assert actual==expected,(actual,expected);row['queried']=query
  row['passed']=sha256(d/'expected.json')==oracle and sha256(a.specs_path)==source_hash
 except BaseException as e:
  import traceback
  row.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(name,row['passed'],row.get('error'),flush=True)
report['passed']=all(r['passed'] for r in report['cases']);(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
