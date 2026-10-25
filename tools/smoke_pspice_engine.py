"""Fresh divider DC engine proof; original CLI evidence is never reused."""
import argparse,json,re
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.environment import ADAPTERS,process_env
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);sources=root/'source';sources.mkdir()
source=sources/'divider.cir';source.write_text('Independent engine DC divider acceptance\nV1 1 0 DC 5\nR1 1 2 1k\nR2 2 0 1k\n.DC V1 5 5 1\n.PRINT DC V(2)\n.PROBE V(2)\n.END\n',encoding='ascii')
config=Config(a.install_root.resolve(strict=True),root/'prepared',(sources,),60)
service=PSpiceInputs(config);prepared=service.prepare(str(source));task=service.inputs[prepared['simulationId']]['directory'];service.get(prepared['simulationId'])
expected={'sweepSource':'V1','sweepValue':5.0,'node':'2','volts':2.5,'absoluteTolerance':1e-6}
(root/'expected.json').write_text(json.dumps(expected,indent=2))
report={'passed':False,'expected':expected,'sourceHashBefore':sha256(source),'engineContext':'independent_tclsh','phase':'run'}
try:
    cmd=[config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'pspice_engine_probe.tcl',config.install_root,task/'input.cir',task]
    report['process']=run_owned_process(list(map(str,cmd)),task,process_env(config),60)
    report['taskRelativePath']=str(task.relative_to(root))
    if (task/'receipt.json').exists():report['receipt']=json.loads((task/'receipt.json').read_text(encoding='utf-8'))
    if (task/'phases.log').exists():report['phases']=(task/'phases.log').read_text().splitlines()
    assert report['process']['state']=='exited' and report['process']['returnCode']==0 and report['process']['remainingOwnedProcesses']==0,report['process']
    assert (task/'dc.out').is_file() and (task/'dc.dat').is_file(),'No fresh unique OUT/DAT pair'
    text=(task/'dc.out').read_text(encoding='ascii',errors='replace');assert not re.search(r'\bERROR\s*(?:\(|--|:)',text,re.I),'Engine error in new OUT'
    rows=text.splitlines();value=None;numeric=re.compile(r'^\s*([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s*$')
    for i,row in enumerate(rows):
        if 'V1' not in row.upper() or 'V(2)' not in row.upper():continue
        for following in rows[i+1:i+8]:
            m=numeric.fullmatch(following)
            if m and abs(float(m[1])-5)<=1e-6:value=float(m[2])
    assert value is not None and abs(value-2.5)<=1e-6,('DC 2.5V oracle',value)
    report.update(passed=True,observedVolts=value,phase='numeric_oracle')
except BaseException as error:report.update(error=str(error),errorType=type(error).__name__)
finally:
    report['sourceHashAfter']=sha256(source)
    if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
    report['artifacts']=[{'name':f.name,'sha256':sha256(f),'size':f.stat().st_size} for f in task.iterdir() if f.is_file()]
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'phases':report.get('phases'),'error':report.get('error'),'report':str(root/'report.json')}))
