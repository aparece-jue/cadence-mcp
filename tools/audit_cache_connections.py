"""Read-only connection-object audit of already saved replacement fixtures."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
p=argparse.ArgumentParser();p.add_argument('--install-root',type=Path,required=True);p.add_argument('--fixture-root',type=Path,required=True);a=p.parse_args()
root=a.fixture_root.resolve(strict=True);report=json.loads((root/'report.json').read_text());cfg=Config(a.install_root,root/'audit-work',(root,),60)
source=root/'source-with-overrides.dsn';before=sha256(source);out=root/'audit-source-connections.json'
run_tcl(cfg,'inspect_page_objects.tcl',[str(source),str(out),'connections'],root);baseline=json.loads(out.read_text(encoding='utf-8'))
audit={'passed':False,'scope':'exact connection object inventory after cache replacement','cases':[],'sourceBefore':before}
for c in report['cases']:
 d=root/(c['selector']+'-'+str(c['update']));target=d/'design.dsn';fingerprint=sha256(target);out=d/'audit-connections.json'
 row={'update':c['update'],'beforeSha256':fingerprint};audit['cases'].append(row)
 try:
  run_tcl(cfg,'inspect_page_objects.tcl',[str(target),str(out),'connections'],d);actual=json.loads(out.read_text(encoding='utf-8'))
  row.update(connectionObjectsMatch=actual==baseline,outputUnchanged=sha256(target)==fingerprint,objectCount=len(actual['objects']))
  row['passed']=row['connectionObjectsMatch'] and row['outputUnchanged']
 except Exception as e:row['error']=str(e);row['passed']=False
audit['sourceAfter']=sha256(source);audit['passed']=audit['sourceAfter']==before and all(c['passed'] for c in audit['cases'])
(root/'connection-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit))
