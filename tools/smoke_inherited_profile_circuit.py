import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.bridge_rpc import GuiBridgeManager
from cadence_mcp.capture_pspice_netlist import CapturePSpiceNetlists
from cadence_mcp.pspice_profile_circuits import PSpiceProfileCircuits
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.pspice_cli_runs import PSpiceCliRuns
from cadence_mcp.pspice_dat import PSpiceDat

p=argparse.ArgumentParser()
for name in ('workspace-root','cycle-root','install-root','source-ini','oracle'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cycle=a.cycle_root.resolve(strict=True);old=json.loads((cycle/'report.json').read_text());assert old['passed']
net=old['cases']['before']['netlistPlan'];library=(a.install_root/'tools/pspice/library').resolve(strict=True);ini=a.source_ini.resolve(strict=True);source_hash=sha256(ini)
cfg=Config(a.install_root,cycle/'work',(ini.parent,library),60);inputs=PSpiceInputs(cfg)
def service():return PSpiceProfileCircuits(cfg,CapturePSpiceNetlists(cfg,CaptureService(cfg),GuiBridgeManager(())),inputs)
s=service();report={'passed':False,'inheritedGenerationAccepted':False,'defaultNominalSolverAccepted':False,'fullV04Accepted':False,'fullP05Accepted':False}
try:
 plan=s.plan(net['planId'],net['planDigest'],[],True,['.AC LIN 100 0.1 200','.OPTIONS ADVCONV','.PROBE64 V(alias(*)) I(alias(*)) W(alias(*)) D(alias(*)) NOISE(alias(*))'],'extended',configuration_ini=str(ini))
 report['plan']=plan;d,_,row=s._load(plan['planId']);origin=row['plan']['payload']['configurationOrigin'];report['origin']=origin
 assert origin['selectedLibraries']==[str(library/'nom.lib')]
 result=s.apply(plan['planId'],plan['planDigest'],'inherited-profile-'+plan['planId']);report['result']=result
 assert result['nativeCheckedIniSelection'] and result['configurationMode']=='inherited_global_library_selection'
 frozen={str(x.relative_to(d)):sha256(x) for x in d.rglob('*') if x.is_file()}
 assert service().apply(plan['planId'],plan['planDigest'],'inherited-profile-'+plan['planId'])==result
 assert {str(x.relative_to(d)):sha256(x) for x in d.rglob('*') if x.is_file()}==frozen
 report['freshServiceIdempotence']=True
 opened=s.open_input(plan['planId'],plan['planDigest']);report['prepared']=opened
 assert opened['inputBudget']=='extended';manifest=inputs.inputs[opened['simulationId']]['manifest']
 source_preserved=all(sha256(Path(f['sourcePath']))==f['sourceSha256'] for f in manifest['files']);assert source_preserved
 modelsroot,models=s._models(row['plan']['payload']);report['frozenModelFileCount']=len(models['files'])-1
 report['frozenModelOriginalBytes']=sum((modelsroot/f['originalRelativePath']).stat().st_size for f in models['files'][1:])
 assert len(models['files'])>200 and report['frozenModelOriginalBytes']>30*1024*1024
 cli=PSpiceCliRuns(cfg,inputs,PSpiceDat(cfg));before={x.name for x in cli.root.glob('plan-*')}
 try:cli.plan(opened['simulationId'],'ac',json.loads(a.oracle.read_text(encoding='utf-8'))['cases']['before'])
 except CadenceError as error:
  report['retainedDefaultModelRefusal']={'code':error.code,'message':str(error)};assert error.code=='unsupported_embedded_reference'
 else:raise AssertionError('Original encrypted/embedded model refusal unexpectedly disappeared')
 assert {x.name for x in cli.root.glob('plan-*')}==before;report['solverNotStarted']=True
 report.update(passed=True,inheritedGenerationAccepted=True,allPreparedSourcesPreserved=source_preserved,allPriorTaskFilesUnchanged=True)
except Exception as error:
 import traceback
 report.update(error=str(error),traceback=traceback.format_exc())
finally:
 report['sourceIniUnchanged']=sha256(ini)==source_hash;report['passed']=report['passed'] and report['sourceIniUnchanged']
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ('passed','error','inheritedGenerationAccepted','frozenModelFileCount','frozenModelOriginalBytes','retainedDefaultModelRefusal','solverNotStarted','sourceIniUnchanged')}))
if not report['passed']:raise SystemExit(1)
