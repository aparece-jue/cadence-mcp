"""Read-only acceptance against original FULLADD and frozen cache replacement outputs."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
from cadence_mcp.library import validate_library
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','fixture-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(root,),60);fixture=a.fixture_root.resolve(strict=True)
sources=[('official',cfg.install_root/'tools/capture/samples/Schematic/FULLADD/FULLADD.DSN'),('prepared',fixture/'source-with-overrides.dsn'),('replace0',fixture/'packageName-0/design.dsn'),('replace1',fixture/'packageName-1/design.dsn')]
report={'passed':False,'cases':[]}
for name,source in sources:
 row={'name':name,'passed':False,'sourceSha256Before':sha256(source)};report['cases'].append(row)
 try:
  out=root/(name+'.json');run_tcl(cfg,'inspect_cache.tcl',[str(source),str(out),'100000'],root);data=json.loads(out.read_text(encoding='utf-8'));validate_library(data)
  names=[p['name'] for p in data['package']];row['packageNames']=names
  assert {'74LS04','74LS08','74LS32'}<=set(names)
  if name=='official':assert set(names)=={'74LS04','74LS08','74LS32'}
  elif name=='prepared':assert 'MCP_FIXTURE_R' in names
  else:
   pkg=next(p for p in data['package'] if p['name']=='R');pins=[p for p in data['pin'] if p['packageId']==pkg['objectId']];assert any(p['name']=='CACHE_INPUT' and p['number']=='1' for p in pins);row['replacementPinVerified']=True
  row['sourceSha256After']=sha256(source);assert row['sourceSha256After']==row['sourceSha256Before'];row['passed']=True
 except Exception as e:row.update(error=str(e),errorType=type(e).__name__)
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
