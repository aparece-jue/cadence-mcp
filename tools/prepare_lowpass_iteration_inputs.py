from pathlib import Path
import argparse,json,shutil,subprocess,sys
from cadence_mcp.core import sha256
p=argparse.ArgumentParser(description='Create explicitly configured before/after native CIR fixtures from accepted project/NET/ALS cases.')
for name in ('baseline-source-root','modified-source-root','baseline-netlist-root','modified-netlist-root','global-ini','install-root','workspace-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();r=Path(__file__).resolve().parents[1];base=a.baseline_source_root.resolve(strict=True);modified=a.modified_source_root.resolve(strict=True);root=a.workspace_root.resolve();root.mkdir(exist_ok=False);reports={}
for label,src,nets in [('before',base,a.baseline_netlist_root.resolve(strict=True)),('after',modified,a.modified_netlist_root.resolve(strict=True))]:
 private=root/(label+'-source');private.mkdir()
 for relative in ['lowpassfilters.dsn','LowPassFilters.opj','LowPassFilters-PSpiceFiles/LPFilters/AC.sim']:
  target=private/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src/relative,target)
 target=private/'LowPassFilters-PSpiceFiles/LPFilters/LPFilters.net';shutil.copyfile(nets/'generated.net',target)
 nr=json.loads((nets/'report.json').read_text());assert nr['sourceSha256']==sha256(private/'lowpassfilters.dsn') and nr['activeDesignUnchanged'] and nr['activeBindingPreserved'] and nr['sourceUnchanged'] and nr['receipt']['nativeReturn']=='1'
 out=root/(label+'-native');cmd=[sys.executable,str(r/'tools/probe_private_lowpass_profile.py'),'--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(out),'--source-root',str(private),'--native-netlist-root',str(nets),'--global-ini',str(a.global_ini.resolve(strict=True))];child=subprocess.run(cmd,capture_output=True,text=True,timeout=45);assert child.returncode==0,(label,child.stdout,child.stderr);report=json.loads((out/'report.json').read_text());assert report['passed'];reports[label]={'root':str(out),'circuit':str(out/'project/LowPassFilters-PSpiceFiles/LPFilters/AC/AC.cir'),'reportSha256':sha256(out/'report.json'),'sourceDesignSha256':sha256(private/'lowpassfilters.dsn'),'netlistSha256':sha256(target)}
(root/'report.json').write_text(json.dumps({'passed':True,'cases':reports,'scope':'Fresh independently bound before/after native NET/ALS/profile CIR; solver not yet run'},indent=2),encoding='utf-8');print(json.dumps({'passed':True,'cases':reports}))
