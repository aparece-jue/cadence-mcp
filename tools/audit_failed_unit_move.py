"""Read-only differential of a retained failed move; never updates its oracle/ledger."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.environment import run_tcl
from cadence_mcp.isolated_jobs import digest
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','previous-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);previous=a.previous_root.resolve(strict=True);original=previous/'report.json';old_hash=sha256(original);old=json.loads(original.read_text(encoding='utf-8'));case=next(c for c in old['cases'] if c['case']=='move-shared-power-A');plan=case['plan'];job=(previous/'work/isolated-jobs/capture_part_edit'/('plan-'+plan['planId'])).resolve(strict=True);assert job.is_relative_to((previous/'work').resolve(strict=True));ledger_path=job/'plan.json';ledger_hash=sha256(ledger_path);ledger=json.loads(ledger_path.read_text(encoding='utf-8'));assert ledger['digest']==plan['planDigest']==digest(ledger['plan']) and ledger['state']=='failed' and ledger['process']['remainingOwnedProcesses']==0;payload=ledger['plan']['payload'];source=Path(payload['sourceDesign']).resolve(strict=True);target=job/'design.dsn';assert source.is_relative_to((previous/'work').resolve(strict=True));source_hash=sha256(source);target_hash=sha256(target);assert source_hash==payload['sourceFingerprint'];cfg=Config(a.install_root,root,(root,),60)
def inspect(path,label):
 out=root/(label+'.json');run_tcl(cfg,'inspect_net_symbol_bindings.tcl',[str(path),str(out)],root);return json.loads(out.read_text(encoding='utf-8'))
before=inspect(source,'before-bindings');after=inspect(target,'after-bindings');rows=[]
for pin in payload['expectedNativePins']:
 def select(data):
  found=[r for r in data if r['kind']=='pin' and r['schematicName']==payload['schematicName'] and r['pageName']==payload['pageName'] and all(r[k]==pin[k] for k in ('reference','number','name'))];assert len(found)==1;return {'connected':found[0]['group'] is not None,'net':found[0]['netName']}
 old=select(before);actual=select(after);wanted={k:pin[k] for k in ('connected','net')}
 if actual!=wanted:rows.append({'reference':pin['reference'],'number':pin['number'],'name':pin['name'],'before':old,'expected':wanted,'actual':actual})
report={'readOnlyAuditPassed':sha256(original)==old_hash and sha256(ledger_path)==ledger_hash and sha256(source)==source_hash and sha256(target)==target_hash,'originalAcceptancePassed':False,'originalReportSha256':old_hash,'ledgerSha256':ledger_hash,'sourceSha256':source_hash,'failedOutputSha256':target_hash,'mismatches':rows,'scope':'page-definition native object/name differential; no inferred flat/physical continuity and no repaired acceptance'};write_json(root/'report.json',report);print(json.dumps(report,indent=2));raise SystemExit(0 if report['readOnlyAuditPassed'] and rows else 1)
