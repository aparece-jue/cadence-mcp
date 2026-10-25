"""Calibrate native pin-swap metadata bounds on new isolated libraries."""
import argparse,copy,json
from pathlib import Path
from library_create_fixtures import specs
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--values',nargs='+',type=int,default=[-1,0,31,32,63,64,99,100,101,127,128,202,4095]);a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root,(root,),45);writer=LibraryCreates(cfg,LibraryService(cfg));report={'scope':'native NewPinNumber swapId range calibration on simple2pin package only','cases':[]}
for value in a.values:
 row={'swapId':value,'verified':False};report['cases'].append(row);spec=copy.deepcopy(specs()['resistor']);spec['packageName']='MCP_SWAP_'+str(value).replace('-','NEG')
 for mapping in spec['devices'][0]['mapping']:mapping['swapId']=value
 try:
  plan=writer.plan(spec);row['planId']=plan['planId'];result=writer.apply(plan['planId'],plan['planDigest'],'swap-'+str(value));row['verified']=result['declaredGraphVerified'];row['result']=result
 except CadenceError as e:row['errorCode']=e.code
 if row.get('planId'):
  d=writer.root/('plan-'+row['planId']);receipt=d/'native-result.json'
  if receipt.exists():row['receipt']=json.loads(receipt.read_text())
  ledger=json.loads((d/'plan.json').read_text());row['process']=ledger.get('process');assert row['process']['remainingOwnedProcesses']==0
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(value,row['verified'],row.get('errorCode'),row.get('receipt'),flush=True)

