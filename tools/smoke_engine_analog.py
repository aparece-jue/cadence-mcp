"""New analog solves: DC divider, RC frequency response and RC time constant."""
import argparse,json,math
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.environment import ADAPTERS,process_env
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
p.add_argument('--probe-selection',choices=['named','all'],default='named')
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
circuits={
'dc':'Independent DC divider\nV1 IN 0 DC 5\nR1 IN OUT 1k\nR2 OUT 0 1k\n.DC V1 5 5 1\n.PRINT DC V(OUT)\n.PROBE V(IN) V(OUT)\n.END\n',
'ac':'Independent RC complex response\nV1 IN 0 DC 0 AC 1\nR1 IN OUT 1k\nC1 OUT 0 1u\n.AC LIN 3 79.5774715 238.7324146\n.PROBE V(IN) V(OUT)\n.END\n',
'transient':'Independent RC step response\nV1 IN 0 PULSE(0 1 0 1n 1n 10m 20m)\nR1 IN OUT 1k\nC1 OUT 0 1u IC=0\n.OPTIONS RELTOL=1e-6 ABSTOL=1p VNTOL=1u\n.TRAN 10u 5m 0 10u UIC\n.PROBE V(IN) V(OUT)\n.END\n'}
if a.probe_selection=='all':
    circuits={name:text.replace('.PROBE V(IN) V(OUT)','.PROBE').replace('.PRINT DC V(OUT)\n','') for name,text in circuits.items()}
expected={'dc':{'inputVolts':5,'outputVolts':2.5,'absoluteTolerance':1e-6},'ac':{'R':1000,'C':1e-6,'transfer':'1/(1+j*2*pi*f*R*C)','absoluteTolerance':1e-6,'cutoffRelativeTolerance':0.01,'nonzeroImaginaryRequired':True},'transient':{'R':1000,'C':1e-6,'tauSeconds':0.001,'response':'1-exp(-t/tau)','absoluteTolerance':2e-4,'tauRelativeTolerance':0.01}}
(root/'expected.json').write_text(json.dumps(expected,indent=2))
for name,text in circuits.items():(sources/(name+'.cir')).write_text(text,encoding='ascii')
config=Config(a.install_root.resolve(strict=True),root/'work',(root,),60);inputs=PSpiceInputs(config);data=PSpiceDat(config)
report={'passed':False,'probeSelection':a.probe_selection,'cases':[],'sourceHashesBefore':{name:sha256(sources/(name+'.cir')) for name in circuits}}
def samples(ident,trace):
    rows=[];offset=0
    while True:
        page=data.samples(ident,0,trace,offset,1000);rows+=page['items'];offset=page['nextOffset']
        if offset is None:return rows
for name in circuits:
    row={'analysis':name,'passed':False,'phase':'prepare'};report['cases'].append(row)
    try:
        prepared=inputs.prepare(str(sources/(name+'.cir')));task=inputs.inputs[prepared['simulationId']]['directory'];inputs.get(prepared['simulationId'])
        row['taskRelativePath']=str(task.relative_to(root));row['phase']='solve'
        cmd=[config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'pspice_engine_analysis.tcl',config.install_root,task/'input.cir',task,name]
        row['process']=run_owned_process(list(map(str,cmd)),task,process_env(config),60)
        if (task/'phases.log').is_file():row['phases']=(task/'phases.log').read_text().splitlines()
        if (task/'receipt.json').is_file():row['receipt']=json.loads((task/'receipt.json').read_text())
        assert row['process']['state']=='exited' and row['process']['returnCode']==0 and row['process']['remainingOwnedProcesses']==0,row['process']
        row['phase']='fresh_dat';opened=data.open(str(task/'result.dat'));ident=opened['datId'];row['datSession']=opened
        try:
            block=data.query(ident,'block')['items'];assert len(block)==1,block
            row['block']=block[0];axis=samples(ident,block[0]['axis']);out=samples(ident,'V(OUT)');vin=samples(ident,'V(IN)')
            assert len(out)==len(axis)==len(vin)>0
            row['phase']='numeric_oracle';row['sampleCount']=len(out)
            if name=='dc':
                assert not block[0]['complex'] and len(out)==1
                assert abs(vin[0]['real']-5)<=1e-6 and abs(out[0]['real']-2.5)<=1e-6,(vin,out)
                row['outputVolts']=out[0]['real']
            elif name=='ac':
                assert block[0]['complex'] and len(out)==3
                actual=[]
                for f,v,source in zip(axis,out,vin):
                    frequency=f['real'];h=1/(1+1j*2*math.pi*frequency*0.001)
                    assert abs(source['real']-1)<=1e-6 and abs(source['imaginary'])<=1e-6
                    assert abs(v['real']-h.real)<=1e-6 and abs(v['imaginary']-h.imag)<=1e-6,(frequency,v,h)
                    actual.append({'frequency':frequency,'expectedReal':h.real,'expectedImaginary':h.imag,'actual':v})
                assert any(abs(v['imaginary'])>0.1 for v in out),'No independent nonzero imaginary proof'
                cutoff=axis[1]['real'];assert abs(cutoff/(1/(2*math.pi*0.001))-1)<=0.01
                assert abs(abs(complex(out[1]['real'],out[1]['imaginary']))-1/math.sqrt(2))<=1e-6
                row.update(samples=actual,cutoffHz=cutoff,nonzeroImaginaryVerified=True)
            else:
                assert not block[0]['complex'];pairs=[(t['real'],v['real']) for t,v in zip(axis,out)]
                assert pairs[0][0]<=1e-9 and pairs[-1][0]>=0.005-1e-8
                errors=[abs(v-(1-math.exp(-t/0.001))) for t,v in pairs];assert max(errors)<=2e-4,max(errors)
                threshold=1-math.exp(-1);cross=None
                for (ta,va),(tb,vb) in zip(pairs,pairs[1:]):
                    if va<=threshold<=vb and vb>va:cross=ta+(tb-ta)*(threshold-va)/(vb-va);break
                assert cross is not None and abs(cross/0.001-1)<=0.01,cross
                row.update(maxAbsoluteError=max(errors),observedTauSeconds=cross)
            row.update(passed=True,artifacts=[{'name':p.name,'sha256':sha256(p),'size':p.stat().st_size} for p in (task/'result.out',task/'result.dat')])
        finally:data.close(ident)
    except BaseException as error:row.update(error=str(error),errorType=type(error).__name__)
report['sourceHashesAfter']={name:sha256(sources/(name+'.cir')) for name in circuits}
report['passed']=all(r['passed'] for r in report['cases']) and report['sourceHashesBefore']==report['sourceHashesAfter']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'cases':[{k:r.get(k) for k in ('analysis','passed','phase','error')} for r in report['cases']],'report':str(root/'report.json')}))
