"""Further bounded writer setup/metadata variants, preserving the original2-block oracle."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.pspice_dat import PSpiceDat
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','original-script','expected-path'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);original=a.original_script.resolve(strict=True);before=sha256(original);source=original.read_text(encoding='utf-8');expected=json.loads(a.expected_path.read_text(encoding='utf-8'));write_json(root/'expected.json',expected);oracle=sha256(root/'expected.json')
cfg=Config(a.install_root,root/'work',(root,),45);report={'scope':'private writer variants with original full complex oracle','anyPassed':False,'cases':[]}
for mode in ('reset_rows','reuse_names','reuse_reset','version9','pio','engine','full_header'):
    directory=root/mode;directory.mkdir();text=source
    if mode in ('reset_rows','reuse_reset'):text=text.replace('        writer addBlock','        writer addBlock\n        writer setHeaderData NumberofAnalogRows 0')
    if mode in ('reuse_names','reuse_reset'):text=text.replace('        writer addDataName Frequency 0\n        writer addDataName Gain 0','        if {$b==0} {writer addDataName Frequency 0;writer addDataName Gain 0}')
    if mode=='version9':text=text.replace('complex.dat] 10','complex.dat] 9')
    if mode=='pio':text=text.replace('orevalexpr64.dll','orPIOData64.dll').replace('orExprEval writer','orPIOObject writer')
    if mode=='engine':text=text.replace('    load [file join $install tools bin orevalexpr64.dll]','    load [file join $install tools bin orPSP_ENG64.dll] orpspeng\n    load [file join $install tools bin orevalexpr64.dll]')
    if mode=='full_header':text=text.replace('        writer addBlock','        writer addBlock\n        writer setHeaderData CircuitSubtitle MCP_SUB\n        writer setHeaderData SimulationTime 12:00:00\n        writer setHeaderData Date 10/24/2026\n        writer setHeaderData ComplexFlag 1')
    marker='    set phase reload';end=text.index(marker);finish=text.index('\n} message options]',end);text=text[:end]+text[finish:]
    constructor='orPIOObject writer' if mode=='pio' else 'orExprEval writer'
    text=text.replace('    '+constructor,'    '+constructor+'\n    proc traceWriter {args} {note "TRACE $args"}\n    trace add execution writer {enter leave} traceWriter')
    script=directory/'writer.tcl';script.write_text(text,encoding='utf-8');row={'mode':mode,'passed':False};report['cases'].append(row)
    try:
        process=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',script,cfg.install_root,directory],directory,process_env(cfg),45)
        row['process']=process;row['log']=(directory/'fixture.log').read_text(encoding='utf-8');assert process['remainingOwnedProcesses']==0
        if process['returnCode']!=0:raise RuntimeError('native_exit_'+str(process['returnCode']))
        data=PSpiceDat(cfg);opened=data.open(str(directory/'complex.dat'));ident=opened['datId'];row['opened']=opened
        try:
            blocks=data.query(ident,'block',limit=1000)['items'];assert len(blocks)==2
            observed=[]
            for want in expected['blocks']:
                index=want['index'];block=blocks[index];assert block['complex'] and block['rowCount']==3
                freq=data.samples(ident,index,'Frequency',0,1000)['items'];gain=data.samples(ident,index,'Gain',0,1000)['items']
                assert [v['real'] for v in freq]==want['frequency'] and all(v['imaginary']==0 for v in freq)
                assert [v['real'] for v in gain]==want['gainReal'] and [v['imaginary'] for v in gain]==want['gainImaginary']
                observed.append({'block':block,'frequency':freq,'gain':gain})
            row.update(passed=True,observed=observed,datSha256=sha256(directory/'complex.dat'))
        finally:data.close(ident)
    except BaseException as error:row.update(error=str(error),errorType=type(error).__name__)
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'mode':mode,'passed':row['passed'],'error':row.get('error'),'lastTrace':row.get('log','').splitlines()[-2:]}),flush=True)
report['sourceAndOracleUnchanged']=sha256(original)==before and sha256(root/'expected.json')==oracle;report['anyPassed']=any(r['passed'] for r in report['cases']) and report['sourceAndOracleUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
