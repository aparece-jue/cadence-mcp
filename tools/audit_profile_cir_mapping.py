"""Independently audit native profile/CIR mapping, preserving original generated files."""
import argparse,json,re
from pathlib import Path
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('native-root','source-root','netlist-root','workspace-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);native=a.native_root.resolve();source=a.source_root.resolve();nets=a.netlist_root.resolve();report=json.loads((native/'report.json').read_text(encoding='utf-8'));assert report['passed'] and report['receipt']['updateResult']=='0' and report['process']['remainingOwnedProcesses']==0;cir=native/report['cirFiles'][0]['path'];profile=source/'LowPassFilters-PSpiceFiles/LPFilters/AC.sim';copied=native/'project/LowPassFilters-PSpiceFiles/LPFilters/AC.sim';net=native/'project/LowPassFilters-PSpiceFiles/LPFilters/LPFilters.net';before={str(p):sha256(p) for p in (cir,profile,copied,net)};assert sha256(profile)==sha256(copied) and sha256(net)==sha256(nets/'generated.net')==report['netSha256'];original=profile.read_text(encoding='utf-8');section=re.search(r'@Analysis: 1 1\s+(.*?)@End Analysis',original,re.S).group(1);assert re.search(r'\+0 "100"',section) and re.search(r'\+1 "0.1"',section) and re.search(r'\+2 "200"',section)
def check(text):
 lines=[s.strip() for s in text.splitlines() if s.strip() and not s.lstrip().startswith('*')];assert [s for s in lines if s.upper().startswith('.AC ')]==['.AC LIN 100 0.1 200'];assert [s for s in lines if s.upper().startswith('.INC ')]==['.INC "..\\LPFilters.net"'];assert [s for s in lines if s.upper().startswith('.LIB ')]==['.lib "nom.lib"'];assert lines[-1]=='.END';assert (cir.parent/'../LPFilters.net').resolve()==net.resolve()
text=cir.read_text(encoding='utf-8');check(text);cases=[{'case':'native_profile_analysis_and_net_mapping','passed':True}]
for name,bad in [('wrong_points',text.replace('.AC LIN 100 ','.AC LIN 99 ')),('wrong_stop',text.replace('0.1 200','0.1 201')),('wrong_include',text.replace('LPFilters.net','foreign.net')),('missing_library',text.replace('.lib "nom.lib"',''))]:
 assert bad!=text
 try:check(bad)
 except AssertionError:cases.append({'case':name,'passed':True,'rejected':True})
 else:raise AssertionError('negative accepted')
assert before=={str(Path(p)):sha256(Path(p)) for p in before};result={'passed':True,'cases':cases,'sourceFingerprints':before,'scope':'Native CIR maps original AC profile and source-audited NET. Model dependency encoding/closure and solver still unaccepted.'};(root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'passed':True,'cases':len(cases)}))
