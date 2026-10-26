import argparse,asyncio,json,os,re,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser(description='Audit the fixed LowPassFilters source/parameter/NET/ALS/CIR/plan/DAT cycle including fresh-server idempotence.')
for name in ('property-root','dsn-oracle','native-inputs-root','cycle-root','netlist-before','netlist-after','workspace-root','install-root'):p.add_argument('--'+name,type=Path,required=True)
args=p.parse_args();r=Path(__file__).resolve().parents[1];root=args.workspace_root.resolve();root.mkdir(exist_ok=False);property_root=args.property_root.resolve(strict=True);prop=json.loads((property_root/'property-report.json').read_text());oracle=json.loads((property_root/'expected.json').read_text());gold=json.loads(args.dsn_oracle.read_text());native_root=args.native_inputs_root.resolve(strict=True);native=json.loads((native_root/'report.json').read_text());cycle_root=args.cycle_root.resolve(strict=True);cycle=json.loads((cycle_root/'report.json').read_text());
assert prop['passed'] and cycle['passed'];report={'passed':False,'fullP05Accepted':False,'formalNativeInputMcpAvailable':False,'noDesktopActionsUsed':True,'sourcePinOracleSha256':sha256(args.dsn_oracle.resolve(strict=True)),'cases':{}}
initial={p['reference'].casefold():{} for p in gold['pins']}
for p in gold['pins']:initial[p['reference'].casefold()][p['name'] if p['reference'].upper().startswith('V') else p['number']]=p['net']
base_lines=(args.netlist_before.resolve(strict=True)/'generated.net').read_text().splitlines();after_lines=(args.netlist_after.resolve(strict=True)/'generated.net').read_text().splitlines();assert len(base_lines)==len(after_lines)
changed=[]
for index,(before_line,after_line) in enumerate(zip(base_lines,after_lines)):
 if before_line==after_line:continue
 at,bt=before_line.split(),after_line.split();assert at[0]==bt[0]=='R_R1' and at[3]=='500' and bt[3]=='1k' and at[:3]+at[4:]==bt[:3]+bt[4:];changed.append(index)
assert len(changed)==1;assert oracle['sourceFingerprint']==prop['sourceBefore']==gold['sourceFingerprint'];assert native['cases']['after']['sourceDesignSha256']==prop['modifiedDesignSha256']
for label,netroot in [('before',args.netlist_before.resolve(strict=True)),('after',args.netlist_after.resolve(strict=True))]:
 nr=json.loads((netroot/'report.json').read_text());case=cycle['cases'][label];generated=Path(native['cases'][label]['root']);sim=generated/'project/LowPassFilters-PSpiceFiles/LPFilters';source_cir=Path(native['cases'][label]['circuit']);assert nr['activeDesignUnchanged'] and nr['activeBindingPreserved'] and nr['sourceUnchanged'];assert sha256(sim/'LPFilters.net')==sha256(netroot/'generated.net')==nr['targetSha256'];assert sha256(sim/'LPFilters.als')==sha256(netroot/'generated.als');
 aliases={}
 for line in (sim/'LPFilters.als').read_text().splitlines():
  if line.strip() in ('.ALIASES','.ENDALIASES'):continue
  m=re.fullmatch(r'([RCLV]_[A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\(([^()]*)\)\s+CN\s+\S+',line.strip());assert m
  device,reference,pins=m.groups();assert device[2:]==reference and reference.casefold() not in aliases
  tokens=[item.split('=') for item in pins.split()];assert len(dict(tokens))==len(tokens);aliases[reference.casefold()]=dict(tokens)
 assert aliases==initial
 assert sha256(source_cir)==case['prepared']['sourceFingerprint']==case['sourceCircuitSha256']
 prepared=cycle_root/'work'/case['prepared']['simulationId'];manifest=json.loads((prepared/'input-manifest.json').read_text());expected_sources={str(source_cir):sha256(source_cir),str(sim/'LPFilters.net'):sha256(sim/'LPFilters.net'),str(sim/'LPFilters.als'):sha256(sim/'LPFilters.als'),str(generated/'own-unused.lib'):sha256(generated/'own-unused.lib')};assert {str(Path(f['sourcePath'])):f['sourceSha256'] for f in manifest['files']}==expected_sources
 job=cycle_root/'work/isolated-jobs/pspice_cli_run'/('plan-'+case['plan']['planId']);plan=json.loads((job/'plan.json').read_text());assert plan['plan']['payload']['expectedSamples']==oracle['cases'][label] and plan['plan']['payload']['sourceFingerprint']==sha256(source_cir);assert plan['state']=='verified'
 receipt=json.loads((job/'cli-receipt.json').read_text());assert receipt['nativeHashes']=={name:sha256(job/name) for name in ['input.dat','input.out']};assert case['dat']['jobAssociationVerified'] and case['result']['numericalAcceptanceVerified'];assert case['nativeOutputHashes']=={name:sha256(job/name) for name in ['input.dat','input.out','cli-receipt.json']}
 report['cases'][label]={'jobDirectory':str(job),'beforeRestartHashes':{str(p.relative_to(job)):sha256(p) for p in job.rglob('*') if p.is_file()},'sourceDesignSha256':nr['sourceSha256'],'sourceCircuitSha256':sha256(source_cir),'netlistSha256':sha256(sim/'LPFilters.net'),'aliasSha256':sha256(sim/'LPFilters.als'),'firstOutputReal':case['firstSample']['real']}
assert cycle['staleWorkerNotStarted'] and cycle['staleOutputRejection']['error']['code']=='preexisting_cli_output';report['aliasPinsMatchedInBothCases']=14;report['onlyR1NetlistValueChanged']=True;report['completeFourFileClosureBound']=True;report['staleWorkerNotStarted']=True
env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(args.install_root.resolve(strict=True)),'--workspace-root',str(cycle_root/'work'),'--read-root',str(native_root),'--timeout-seconds','60'],env=env)
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as c:
   for label in ['before','after']:
    case=cycle['cases'][label];key={k:case['plan'][k] for k in ['planId','planDigest']};out=await c.call_tool('pspice_apply_cli_run',{**key,'idempotencyKey':'p05-fresh-'+label});assert not out.is_error and out.structured_content['data']==case['result']
   report['freshServerIdempotenceAccepted']=True
  for label,item in report['cases'].items():
   d=Path(item['jobDirectory']);assert all(sha256(d/name)==digest for name,digest in item['beforeRestartHashes'].items())
  report['allCompletedJobBytesUnchanged']=True;report['passed']=True
 except Exception as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report.get(k) for k in ['passed','error','onlyR1NetlistValueChanged','completeFourFileClosureBound','freshServerIdempotenceAccepted','allCompletedJobBytesUnchanged']}))
asyncio.run(main())

if not report["passed"]:raise SystemExit(1)
