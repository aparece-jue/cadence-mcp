"""Package the accepted installed alpha candidate; do not overwrite earlier assets."""
import hashlib,json,zipfile
from pathlib import Path
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/alpha311';dist=r/'dist/alpha311'
def read(p):return json.loads((r/p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
core=read('.local/alpha311/core/report.json');features=read('.local/alpha311/new-features-v2/report.json');wheelproof=read('.local/alpha311/wheel-proof.json')
assert core['passed'] and features['passed'] and wheelproof['passed'] and core['toolCount']==224
log='.local/alpha311/candidate-regression.txt';assert 'Ran 729 tests' in (r/log).read_text() and 'OK (skipped=1)' in (r/log).read_text()
assert 'No broken requirements found.' in (root/'pip-check.txt').read_text()
reg=dict(total=729,passed=728,skipped=1,errors=0,status='passed_with_skip',evidence=log)
bridge=(r/'docs/testing/alpha-2-bridge.md').read_text(encoding='utf-8').replace('v0.1.0-alpha.2','v0.1.1-alpha.1').replace('alpha.2','0.1.1-alpha.1').replace('cadence-mcp-alpha2','cadence-mcp-0.1.1-alpha.1').replace('alpha2','alpha3')
(r/'docs/testing/alpha-3-bridge.md').write_text(bridge,encoding='utf-8')
config=read('examples/mcp-client-alpha3.example.json');entry=next(iter(config['mcpServers'].values()));entry['args']+=['--gui-bridge-root','D:/cadence-mcp-0.1.1-alpha.1/bindings','--read-root','D:/cadence-mcp-0.1.1-alpha.1/controls'];(r/'examples/mcp-gui-client-alpha3.example.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
wheel=dist/'cadence_mcp-0.1.1a1-py3-none-any.whl';assert sha(wheel)==wheelproof['wheelSha256']
manifest=dict(version='0.1.1a1',tag='v0.1.1-alpha.1',tools=224,platform='Windows x64',verifiedCadence='24.1',fullRegression=reg,fullBusinessGates=dict(total=34,passed=8,remaining=26),sourceBaseCommit=read('.local/alpha311/preparation.json')['baseCommit'],packagedSourceFilesVerified=wheelproof['sourceFiles'],packagedSourceFingerprint=sha(root/'wheel-proof.json'),wheelSha256=sha(wheel),installedContractCaptureAndEngineDcDatPassed=True,installedNewFeaturesPassed=[x['name'] for x in features['cases']],installedSourcePythonPathExcluded=True,installedCliSmokePassed=None,cliStatus='not_retested; alpha2 Product Choices limitation retained',cadenceIncluded=False,realDesignsIncluded=False,fullGoalComplete=False)
mapping={'requirements.lock.txt':'requirements.lock.txt','docs/testing/alpha-3.md':'START-HERE.md','docs/releases/v0.1.1-alpha.1.md':'RELEASE-NOTES.md','docs/testing/alpha-3-bridge.md':'GUI-BRIDGE.md','examples/mcp-client-alpha3.example.json':'mcp-client.example.json','examples/mcp-gui-client-alpha3.example.json':'mcp-gui-client.example.json','contracts/tools.v0.1.json':'tools-contract.json','examples/divider.cir':'divider.cir','LICENSE':'LICENSE'}
for name in ['prepare_write_fixture.py','prepare_gui_bridge.py','load_gui_bridge.py','bridge_doctor.py']:mapping['tools/'+name]='tools/'+name
payload=dist/'cadence-mcp-0.1.1-alpha.1-windows.zip';assert not payload.exists()
with zipfile.ZipFile(payload,'x',zipfile.ZIP_DEFLATED) as z:
 z.write(wheel,wheel.name)
 for rel,name in mapping.items():z.write(r/rel,name)
 z.writestr('release-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(payload) as z:
 assert set(z.namelist())=={wheel.name,'release-manifest.json',*mapping.values()};assert z.read(wheel.name)==wheel.read_bytes()
 assert not any(n.lower().endswith(('.dsn','.olb','.exe','.dll','.pdf')) for n in z.namelist())
(dist/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in [wheel,payload]),encoding='ascii')
proofs=['.local/alpha311/core/report.json','.local/alpha311/new-features-v2/report.json','.local/alpha311/new-features/parts/report.json','.local/alpha311/wheel-proof.json',log,'.local/alpha311/pip-check.txt']+[x['reportRelativePath'] for x in features['cases']]
verification=dict(manifest,assets={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in [wheel,payload]},initialInstalledHarnessFailure='Historical part count222 rejected actual224 before native feature queries; old report retained. New fixed suite updates historical part/contact count only, keeps oracles, excludes source PYTHONPATH.',evidenceSha256={p:sha(r/p) for p in proofs})
(r/'docs/releases/alpha-3-verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'packaged':True,'assets':verification['assets'],'installedNewFeatures':manifest['installedNewFeaturesPassed']}),flush=True)
