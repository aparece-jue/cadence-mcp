"""Native selected pin-map/connection acceptance, not complete H02 approval."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source','connected-source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
expected={'datasheet':'https://www.ti.com/document-viewer/SN7432/datasheet',
          'ls32':{'U1A':{'I0':'1','I1':'2','O':'3','VCC':'14','GND':'7'},
                  'U1B':{'I0':'4','I1':'5','O':'6','VCC':'14','GND':'7'},
                  'U1C':{'I0':'9','I1':'10','O':'8','VCC':'14','GND':'7'}},
          'resistors':{'same_net':[['R101','2'],['R102','1']],
                       'unbound':[['R101','1'],['R102','2']]}}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
report={'passed':False,'checks':{},'notChecked':['complete_fulladd_wiring_oracle','bus_and_mixed_ports','heterogeneous_cell_correspondence','all_shared_pin_conflicts','native_drc']}
try:
    for key,source in [('fulladd',a.source),('connected',a.connected_source)]:
        run=subprocess.run([sys.executable,str(Path(__file__).with_name('probe_occurrence_nets.py')),'--install-root',str(a.install_root),'--workspace-root',str(root/key),'--source',str(source)],capture_output=True,text=True,encoding='utf-8',timeout=75)
        (root/(key+'-process.txt')).write_text(run.stdout+run.stderr,encoding='utf-8')
        assert run.returncode==0,(key,run.stdout,run.stderr)
    full=json.loads((root/'fulladd/native.json').read_text(encoding='utf-8'))
    assert full['occurrenceCount']==16
    for reference,mapping in expected['ls32'].items():
        rows=[p for p in full['pins'] if p['reference']==reference]
        assert {p['name']:p['occurrencePhysicalNumber'] for p in rows}==mapping
    for reference in ('U1B','U1C'):
        power={p['name']:p['flatNetId'] for p in full['pins'] if p['reference']==reference and p['name'] in ('VCC','GND')}
        if reference=='U1B':previous=power
        else:assert power==previous and power['VCC']!=power['GND']
    # The named X_BAR net is private to each repeated HALFADD instance.
    pair=[p for p in full['pins'] if p['reference'] in ('U3A','U3C') and p['name']=='O']
    assert len(pair)==2 and pair[0]['flatNetId']!=pair[1]['flatNetId']
    report['checks'].update(ls32_independent_pin_map=True,shared_power_and_private_net_examples=True)
    connected=json.loads((root/'connected/native.json').read_text(encoding='utf-8'))
    contexts={tuple(p['instancePathSegments'][:-1]) for p in connected['pins'] if p['reference']=='R101'}
    assert contexts
    for context in contexts:
        selected={(p['reference'],p['occurrencePhysicalNumber']):p for p in connected['pins']
                  if tuple(p['instancePathSegments'][:-1])==context and p['reference'] in ('R101','R102')}
        assert len(selected)==4
        left,right=[selected[tuple(x)] for x in expected['resistors']['same_net']]
        assert left['flatNetId'] is not None and left['flatNetId']==right['flatNetId']
        assert left['flatNetName']==right['flatNetName']
        assert all(selected[tuple(x)]['flatNetId'] is None for x in expected['resistors']['unbound'])
    report['checks']['declared_resistor_connections_and_unbound']=True
    report.update(passed=True,connectedContexts=[list(x) for x in sorted(contexts)])
except BaseException as e:report.update(errorType=type(e).__name__,error=str(e))
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
raise SystemExit(0 if report['passed'] else 1)
