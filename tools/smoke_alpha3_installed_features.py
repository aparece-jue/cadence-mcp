"""Installed alpha-only verification; reuse fixed oracles without importing source modules."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
import cadence_mcp
r=Path(__file__).resolve().parents[1];root=r/'.local/alpha311/new-features-v2';root.mkdir(exist_ok=False)
assert cadence_mcp.__version__=='0.1.1a1' and Path(cadence_mcp.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
cases=[('parts','smoke_part_vectors_mcp.py','part-vectors-mcp-20261027',[]),('contacts','smoke_symbol_contacts_mcp_v2.py','symbol-contacts-mcp-v2-20261028',[]),('titleblocks','smoke_titleblock_vectors.py',None,['--workspace-root',str(root/'titleblocks')]),('user-strings','smoke_native_user_string_contract_v2.py','native-user-string-contract-v2-20261028',[]),('inventory','smoke_connection_inventory_current.py',None,['--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'inventory'),'--fixture-root',str(r/'.local/c04-wire-first-20261028'),'--nc-source',str(r/'.local/shared-unit-nc-guard-20261024/design.dsn')])]
env=os.environ.copy();env.pop('PYTHONPATH',None);proofs=[]
for name,source,oldroot,args in cases:
 original=r/'tools'/source;code=original.read_text(encoding='utf-8');assert code.count('r=Path(__file__).resolve().parents[1]')==1 or name=='inventory'
 code=code.replace('r=Path(__file__).resolve().parents[1]','r=Path('+repr(r.as_posix())+')')
 if name=='inventory':code=code.replace("env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')","env.pop('PYTHONPATH',None)")
 else:code=code.replace("env['PYTHONPATH']=str(r/'src')","env.pop('PYTHONPATH',None)")
 assert "env['PYTHONPATH']" not in code
 if oldroot:code=code.replace("r/'.local/"+oldroot+"'","Path("+repr((root/name).as_posix())+")")
 if name=='parts':
  assert code.count('assert len(tools)==222')==1;code=code.replace('assert len(tools)==222','assert len(tools)==224')
 if name=='contacts':
  assert code.count('assert len(tools)==223')==1;code=code.replace('assert len(tools)==223','assert len(tools)==224')
 guard="import sys as _sys\nfrom pathlib import Path as _Path\nimport cadence_mcp as _pkg\nassert _pkg.__version__=='0.1.1a1' and _Path(_pkg.__file__).resolve().is_relative_to(_Path(_sys.prefix).resolve())\n"
 generated=root/(name+'-installed.py');generated.write_text(guard+code,encoding='utf-8')
 log=root/(name+'.log')
 with log.open('w',encoding='utf-8') as out:result=subprocess.run([sys.executable,str(generated),*args],cwd=root,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=300)
 report=json.loads((root/name/'report.json').read_text(encoding='utf-8'));assert result.returncode==0 and report['passed'],(name,log)
 proofs.append({'name':name,'passed':True,'originalHarness':source,'originalHarnessSha256':hashlib.sha256(original.read_bytes()).hexdigest(),'installedHarnessSha256':hashlib.sha256(generated.read_bytes()).hexdigest(),'reportRelativePath':(root/name/'report.json').relative_to(r).as_posix()});print(json.dumps({'installedFeatureAccepted':name}),flush=True)
(root/'report.json').write_text(json.dumps({'passed':True,'version':cadence_mcp.__version__,'importPath':cadence_mcp.__file__,'sourcePythonPathExcluded':True,'cases':proofs},indent=2)+'\n',encoding='utf-8')
