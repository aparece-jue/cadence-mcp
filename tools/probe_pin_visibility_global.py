import argparse,copy,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates
from cadence_mcp.library_pin_style import read_styles
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);config=Config(a.install_root.resolve(),root/'work',(root,),60);library=LibraryService(config);creator=LibraryCreates(config,library)
spec={'packageName':'MCP_VIS','referenceTemplate':'J?','footprint':'VIS_FP','expectedHomogeneous':True,'symbols':[{'cellName':'VIS_CELL','partName':'VIS.Normal','pins':[{'position':i,'name':'PIN'+str(i),'pinType':i//2,'start':[-10,i*10],'hotSpot':[-20,i*10],'visible':i%2==0} for i in range(16)],'lines':[]}],'devices':[{'designator':'','position':0,'cellName':'VIS_CELL','mapping':[{'position':i,'number':str(i+1),'shared':False,'swapId':0} for i in range(16)]}]}
targets={str(i):i%2!=0 for i in range(16)};(root/'expected.json').write_text(json.dumps({'source':spec,'targetVisibility':targets,'hypothesis':'For scalar symbol pins in this fixture, global=(pinType==7 or not visible), before and after SetIsVisible. All other flags remain unchanged.'},indent=2),encoding='utf-8');before=sha256(root/'expected.json');plan=creator.plan(spec);creator.apply(plan['planId'],plan['planDigest'],'create-vis');d,_,_=creator._load(plan['planId']);source=d/'library.olb';source_hash=sha256(source);target=root/'after.olb';shutil.copy2(source,target);(root/'request.json').write_text(json.dumps(targets),encoding='utf-8');shutil.copy2(ADAPTERS/'json.tcl',root/'json.tcl');shutil.copy2(Path(__file__).with_name('probe_pin_visibility_global.tcl'),root/'probe.tcl')
def inspect(path):
 lid=library.open(str(path))['libraryId'];data=library.sessions[lid]['data'];rows=read_styles(config,path,root,data);library.close(lid);return rows
old=inspect(source);process=run_owned_process([config.install_root/'tcltk/bin/tclsh.exe',root/'probe.tcl',config.install_root,target,root/'request.json'],root,process_env(config),60);(root/'process.json').write_text(json.dumps(process,indent=2),encoding='utf-8');assert process['returnCode']==0,process;new=inspect(target);changes=[]
for original,actual in zip(old,new):
 position=original['scope'][-1];wanted=copy.deepcopy(original);wanted['flags']['visible']=targets[str(position)];wanted['flags']['global']=position//2==7 or not targets[str(position)]
 assert original['flags']['global']==(position//2==7 or not spec['symbols'][0]['pins'][position]['visible'])
 assert wanted==actual,(wanted,actual);changes.append({'position':position,'pinType':position//2,'before':original['flags'],'expected':wanted['flags'],'actual':actual['flags']})
report={'passed':len(changes)==16 and source_hash==sha256(source) and before==sha256(root/'expected.json'),'sourceHash':source_hash,'expectedSha256':before,'cases':changes,'process':process,'scope':'native symbol visibility/global coupling only; no instance electrical connectivity verdict'};(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(changes)}))
