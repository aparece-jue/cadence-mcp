"""Original minimal analog+digital stimulus solve; inspect representations without public capability claims."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_dat import PSpiceDat
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(root,),60)
source=root/'mixed.cir';source.write_text('''Original minimal independent mixed signal fixture
VPOWER DPWR 0 DC 5
VANALOG ANALOG 0 DC 1
RLOAD ANALOG 0 1k
.MODEL IOLOCAL UIO(DRVH=50 DRVL=50)
UDIG STIM(1,1) DPWR 0 DIN IOLOCAL
+ 0s 0
+ 1us 1
+ 2us 0
+ 3us Z
.OPTIONS DIGINITSTATE=0
.TRAN 0.1us 4us
.PROBE
.END
''',encoding='ascii');before=sha256(source)
expected={'analogNode':'ANALOG','analogVolts':1,'absoluteTolerance':1e-6,'digitalStimulus':[[0,'0'],[1e-6,'1'],[2e-6,'0'],[3e-6,'Z']],'digitalStatesNotYetVerified':True};write_json(root/'expected.json',expected)
report={'passed':False,'scope':'private mixed solver fixture representation, no claimed digital sample acceptance','sourceHash':before}
try:
 inputs=PSpiceInputs(cfg);prepared=inputs.prepare(str(source));directory=inputs.inputs[prepared['simulationId']]['directory'];report['prepared']=prepared
 process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'pspice_engine_analysis.tcl',cfg.install_root,directory/'input.cir',directory,'transient'],directory,process_env(cfg),60);report['process']=process
 assert process['returnCode']==0 and process['remainingOwnedProcesses']==0
 report['receipt']=json.loads((directory/'receipt.json').read_text(encoding='utf-8'));assert report['receipt']['caught']==0
 report['outTail']=(directory/'result.out').read_text(encoding='cp1252')[-4000:]
 data=PSpiceDat(Config(cfg.install_root,cfg.workspace_root,(directory,),60));opened=data.open(str(directory/'result.dat'));ident=opened['datId'];report['opened']=opened
 report['blocks']=data.query(ident,'block',limit=1000)['items'];report['traces']=data.query(ident,'trace',0,limit=1000)['items']
 out=directory/'native-digital.json';read=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'probe_digital_dat.tcl',cfg.install_root,directory/'result.dat',out],directory,process_env(cfg),45);report['readProcess']=read
 if out.exists():report['native']=json.loads(out.read_text(encoding='utf-8'))
 report['datPath']=str(directory/'result.dat');report['datHash']=sha256(directory/'result.dat');report['passed']=bool(report['blocks'] and report['blocks'][0]['dataTypeCode']==2 and report['blocks'][0]['digitalRowCount']>0 and report['blocks'][0]['analogRowCount']>0)
 data.close(ident)
except BaseException as error:
 import traceback
 report.update(error=str(error),traceback=traceback.format_exc())
report['sourceUnchanged']=sha256(source)==before
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'sourceUnchanged':report['sourceUnchanged'],'process':report.get('process'),'blocks':report.get('blocks'),'error':report.get('error')}))
