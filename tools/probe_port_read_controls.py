"""Read-only positive controls for a new port diagnostic reader; no design acceptance promotion."""
import json,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
r=Path(__file__).resolve().parents[1];root=r/'.local/editor-port-read-controls-20261027';root.mkdir(exist_ok=False)
s=(r/'tools/inspect_native_ports_v2.tcl').read_text(encoding='utf-8');anchor='set session "";set phase load;set rc [catch {'
helper='''proc nxt {object method state label} {set ::phase $label;set result [$object $method $state];ck $state;return $result}
''';assert s.count(anchor)==1;s=s.replace(anchor,helper+anchor)
for variable,method,label in [('vi','NextView','next_view'),('pi','NextPage','next_page'),('it','NextWire','next_wire'),('it','NextPort','next_port')]:s=s.replace('[$'+variable+' '+method+' $st]','[nxt $'+variable+' '+method+' $st '+label+']')
s=s.replace('set pi [$s NewPagesIter','set phase new_pages_iterator;set pi [$s NewPagesIter').replace('set it [$p NewWiresIter','set phase new_wires_iterator;set it [$p NewWiresIter').replace('set it [$p NewPortsIter','set phase new_ports_iterator;set it [$p NewPortsIter')
(r/'tools/inspect_native_ports_diagnostic.tcl').write_text(s,encoding='utf-8')
old=json.loads((r/'.local/bus-eight-pins-mcp-20261027/report.json').read_text(encoding='utf-8'))
sources={'known_empty':r/'.local/editor-session-wire-20261026/before.dsn','known_four_resistors':r/'.local/bus-eight-pins-mcp-20261027/work'/old['placements'][-1]['result']['outputWorkspaceRelativePath']/'design.dsn','failed_ports':r/'.local/editor-ports-20261027/plan-1722585d50b14fbb97c407acaba1c82f/design.dsn','failed_ports_v2':r/'.local/editor-ports-v2-20261027/plan-6fbb19bac25244dfba1e0c35b40f6c31/design.dsn'}
cfg=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',tuple(p.parent for p in sources.values()),30);report={'passed':False,'cases':[]}
for name,source in sources.items():
 before=sha256(source);item={'name':name,'sourceSha256':before};report['cases'].append(item)
 for script,outname,args in [('inspect.tcl','definitions',['100000']),(str(r/'tools/inspect_native_ports_diagnostic.tcl'),'ports',[])]:
  output=root/(name+'-'+outname+'.json')
  try:
   run_tcl(cfg,script,[str(source),str(output),*args],root);data=json.loads(output.read_text(encoding='utf-8'));item[outname]=data if outname=='ports' else {k:len(v) for k,v in data.items()}
  except BaseException as error:item[outname]=json.loads(output.read_text(encoding='utf-8')) if output.exists() else {'error':str(error)}
 item['sourceUnchanged']=sha256(source)==before;print(json.dumps(item),flush=True)
report['passed']=all(c['sourceUnchanged'] for c in report['cases']);report['scope']='diagnostic_controls_completed_not_business_acceptance';(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
