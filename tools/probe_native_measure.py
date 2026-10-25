"""Bounded native MEASURE format discovery using only new owned circuits."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--install',type=Path,required=True);a=p.parse_args()
root=a.root.resolve();root.mkdir(exist_ok=False)
cases={
 'dc':('* native divider measurements\nV1 1 0 DC 5\nR1 1 2 1k\nR2 2 0 1k\n.DC V1 0 5 1\n.MEASURE DC divider_max MAX V(2)\n.MEASURE DC divider_avg AVG V(2)\n.MEASURE DC divider_at FIND V(2) AT=4\n.PROBE\n.END\n',{'divider_max':2.5,'divider_avg':1.25,'divider_at':2.0}),
 'ac':('* native RC measurements\nV1 1 0 DC 0 AC 1\nR1 1 2 1k\nC1 2 0 1u\n.AC LIN 3 79.5774715459 238.732414638\n.MEASURE AC rc_mag FIND VM(2) AT=159.154943092\n.PROBE\n.END\n',{'rc_mag':2**-0.5}),
 'transient':('* native RC measurements\nV1 1 0 PULSE(0 1 0 1n 1n 1 2)\nR1 1 2 1k\nC1 2 0 1u\n.TRAN 10u 5m 0 10u\n.MEASURE TRAN rc_tau WHEN V(2)=0.632120558829 RISE=1\n.MEASURE TRAN rc_at FIND V(2) AT=1m\n.PROBE\n.END\n',{'rc_tau':0.001,'rc_at':0.632120558829})}
report={'scope':'native measure discovery; not business acceptance','cases':[]}
for name,(text,expected) in cases.items():
 d=root/name;d.mkdir();c=d/'input.cir';c.write_text(text,encoding='ascii');before=sha256(c);cfg=Config(a.install,d,(d,),60)
 row={'analysis':name,'expected':expected,'sourceSha256':before};report['cases'].append(row)
 try:
  row['process']=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'pspice_engine_analysis.tcl'),str(cfg.install_root),str(c),str(d),name],d,process_env(cfg),60)
  row['sourceUnchanged']=before==sha256(c)
  row['files']=[{'name':f.name,'size':f.stat().st_size,'sha256':sha256(f)} for f in d.iterdir() if f.is_file()]
 except Exception as e:row['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(name,row.get('process',row.get('error')),flush=True)
