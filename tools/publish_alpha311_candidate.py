"""Publish only the explicitly authorized alpha.2 prerelease; never alter existing public releases."""
import hashlib,json,os,subprocess,urllib.error,urllib.parse,urllib.request
from pathlib import Path
r=Path(r'D:\workspace\git\cadence-mcp');repo='aparece-jue/cadence-mcp';tag='v0.1.1-alpha.1';base='https://api.github.com/repos/'+repo;assets=r/'dist/alpha311'
commit=json.loads((r/'.local/alpha311/alpha-push-receipt.json').read_text(encoding='utf-8'))['commit']
token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
if not token:
 env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never')
 child=subprocess.run(['git','-c','safe.directory='+r.as_posix(),'credential','fill'],cwd=r,input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,env=env,timeout=30)
 token=dict(line.split('=',1) for line in child.stdout.splitlines() if '=' in line).get('password')
if not token:raise SystemExit('GitHub authentication unavailable; no credentials displayed.')
def api(path='',data=None,method=None,url=None,not_found=False):
 body=json.dumps(data).encode('utf-8') if isinstance(data,dict) else data
 request=urllib.request.Request(url or base+path,data=body,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json' if not isinstance(data,bytes) else 'application/octet-stream','User-Agent':'cadence-mcp-alpha2-release'})
 try:
  with urllib.request.urlopen(request,timeout=50) as response:return json.load(response)
 except urllib.error.HTTPError as error:
  if not_found and error.code==404:return None
  raise SystemExit('GitHub request failed: HTTP '+str(error.code)) from None
ref=api('/git/ref/tags/'+tag);assert ref['object']['type']=='tag';assert api('/git/tags/'+ref['object']['sha'])['object']['sha']==commit
release=api('/releases/tags/'+tag,not_found=True)
if release is None:
 release=api('/releases',dict(tag_name=tag,name=tag+' — Windows Capture/PSpice 测试版',body=(r/'docs/releases/v0.1.1-alpha.1.md').read_text(encoding='utf-8'),draft=True,prerelease=True),'POST')
assert release['tag_name']==tag and release['prerelease']
expected={p.name:p for p in assets.iterdir() if p.is_file()};assert len(expected)==3
if release['draft']:
 present={a['name']:a for a in release['assets']}
 assert not(set(present)-set(expected))
 for name,path in sorted(expected.items()):
  fingerprint='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
  if name in present:assert present[name].get('digest')==fingerprint and present[name]['size']==path.stat().st_size;continue
  uploaded=api(data=path.read_bytes(),method='POST',url=release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(name))
  assert uploaded['size']==path.stat().st_size;print(json.dumps(dict(uploaded=name,bytes=uploaded['size'])),flush=True)
 release=api('/releases/'+str(release['id']),dict(draft=False,prerelease=True),'PATCH')
remote={a['name']:a for a in release['assets']};assert set(remote)==set(expected);checks={}
for name,path in expected.items():
 request=urllib.request.Request(remote[name]['browser_download_url'],headers={'User-Agent':'cadence-mcp-alpha2-verification'})
 with urllib.request.urlopen(request,timeout=50) as response:blob=response.read(16*1024*1024+1)
 expected_hash=hashlib.sha256(path.read_bytes()).hexdigest();assert len(blob)==path.stat().st_size and hashlib.sha256(blob).hexdigest()==expected_hash
 checks[name]=expected_hash
receipt=dict(releaseUrl=release['html_url'],commit=commit,tag=tag,prerelease=release['prerelease'],publicDownloadsSha256Verified=checks,installedCliSmokePassed=None,cliKnownLimitation='Cadence Product Choices requires local product selection')
(r/'.local/alpha311/release-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
