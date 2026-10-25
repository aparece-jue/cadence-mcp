import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);c=Config(a.install_root.resolve(),root/'work',(root,),60);source=c.install_root/'tools/capture/library/capsym.olb';library=root/'library.olb';shutil.copy2(source,library)
objects=[]
for page in ('PAGE_A','PAGE_B'):
 for mirror in (0,1):
  for rotation in range(4):
   x=200+150*rotation;y=200+200*mirror
   for kind,name,cache,location,local in [('global','DUP_SUPPLY','READ_GLOBAL',[x,y],[10,10]),('offpage','DUP_LINK','READ_OFF',[x,y+70],[0,10])]:
    dx,dy=local
    if mirror:dx=-dx
    tx,ty=((dx,dy),(dy,-dx),(-dx,-dy),(-dy,dx))[rotation]
    objects.append({'pageName':page,'kind':kind,'attributes':{'name':name,'sourceSymbol':cache,'location':location,'hotSpot':[location[0]+tx,location[1]+ty],'rotationCode':rotation,'mirrorCode':mirror,'isBus':False}})
 for y in (800,900):
  objects.append({'pageName':page,'kind':'wire','attributes':{'points':[[100,y],[200,y]],'net':'LOCAL_DUP'}})
  objects.append({'pageName':page,'kind':'alias','attributes':{'name':'LOCAL_DUP','location':[140,y]}})
expected={'pages':['PAGE_A','PAGE_B','EMPTY'],'objects':objects,'poseHypothesis':'clockwise screen rotation; X mirror before rotation; source VCC local(10,10), OFFPAGELEFT-L local(0,10). Freeze before native creation; failures retained, not overwritten.'};(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');before=sha256(root/'expected.json')
process=run_owned_process([c.install_root/'tcltk/bin/tclsh.exe',Path(__file__).with_name('fixture_connection_inventory.tcl'),c.install_root,library,root/'design.dsn',root/'receipt.json',ADAPTERS/'json.tcl'],root,process_env(c),60)
report={'passed':process['returnCode']==0,'process':process,'receipt':json.loads((root/'receipt.json').read_text(encoding='utf-8')),'expectedHashBefore':before,'expectedHashAfter':sha256(root/'expected.json'),'libraryOriginalHash':sha256(source),'libraryCopyHash':sha256(library)};report['passed']=report['passed'] and report['expectedHashBefore']==report['expectedHashAfter'] and report['libraryOriginalHash']==report['libraryCopyHash'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'receipt':report['receipt']}));raise SystemExit(0 if report['passed'] else 1)
