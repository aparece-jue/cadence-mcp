"""Preserve exact local Git objects over GitHub API when smart-HTTP transport resets."""
import base64,datetime,json,os,re,subprocess,urllib.error,urllib.request
from pathlib import Path
r=Path(r'D:\workspace\git\cadence-mcp');g=['git','-c','safe.directory='+r.as_posix()];base='https://api.github.com/repos/aparece-jue/cadence-mcp';target=json.loads((r/'.local/alpha311/candidate-receipt.json').read_text(encoding='utf-8'))['commit']
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never')
child=subprocess.run([*g,'credential','fill'],cwd=r,input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,env=env,timeout=20);token=dict(line.split('=',1) for line in child.stdout.splitlines() if '=' in line).get('password');assert token
def git(*args):return subprocess.check_output([*g,*args],cwd=r)
def api(path,data=None,method=None,optional=False):
 req=urllib.request.Request(base+path,data=json.dumps(data,ensure_ascii=False).encode('utf-8') if data is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'cadence-mcp-alpha2-git-object-sync'})
 try:
  with urllib.request.urlopen(req,timeout=60) as response:return json.load(response)
 except urllib.error.HTTPError as e:
  if optional and e.code==404:return None
  raise SystemExit('GitHub API failed: HTTP '+str(e.code)) from None
def identity(value):
 match=re.fullmatch(r'(.*) <([^<>]*)> (\d+) ([+-])(\d{2})(\d{2})',value);assert match,value
 name,email,stamp,sign,hours,minutes=match.groups();offset=(int(hours)*60+int(minutes))*(1 if sign=='+' else -1)
 return dict(name=name,email=email,date=datetime.datetime.fromtimestamp(int(stamp),datetime.timezone(datetime.timedelta(minutes=offset))).isoformat())

receipt=json.loads((r/'.local/alpha311/candidate-receipt.json').read_text(encoding='utf-8'))
before=api('/git/ref/heads/develop')['object']['sha'];assert before==receipt['parentDevelop']
old_alpha='64e7ca9bb61bb04d80575d7289104405a2c2afe9'
frozen={'release':'e59f888607bdc647c3dbcec1a235663fc3b3eeb4','main':'0a31dda05dfce224fc27cb1f6a950e9fedb4b6fc'}
for branch,sha in frozen.items():assert api('/git/ref/heads/'+branch)['object']['sha']==sha
assert api('/git/ref/heads/alpha')['object']['sha'] in (old_alpha,target)
commits=git('rev-list','--reverse',before+'..'+target).decode().splitlines();assert commits and len(commits)<=10
for sha in commits:
 if api('/git/commits/'+sha,optional=True):continue
 raw=git('cat-file','commit',sha).decode('utf-8');headers,message=raw.split('\n\n',1);fields={}
 for line in headers.splitlines():
  k,v=line.split(' ',1);fields.setdefault(k,[]).append(v)
 assert set(fields)=={'tree','parent','author','committer'} and len(fields['parent'])==1
 parent=fields['parent'][0];parent_commit=api('/git/commits/'+parent);assert parent_commit
 entries=[];names=git('diff-tree','--no-commit-id','--name-only','--no-renames','-r','-z',parent,sha).decode('utf-8').split('\0')
 for name in filter(None,names):
  assert name.startswith(('src/','docs/','tests/','tools/','contracts/','examples/')) or name in ('AGENTS.md','README.md','pyproject.toml','requirements.lock.txt')
  tree=git('ls-tree','-z',sha,'--',name).decode('utf-8').strip('\0')
  if not tree:entries.append(dict(path=name,mode='100644',type='blob',sha=None));continue
  desc,path=tree.split('\t',1);mode,kind,blobsha=desc.split();assert kind=='blob' and mode in ('100644','100755') and path==name
  blob=git('cat-file','blob',blobsha)
  try:entry=dict(path=name,mode=mode,type='blob',content=blob.decode('utf-8'))
  except UnicodeDecodeError:
   created=api('/git/blobs',dict(content=base64.b64encode(blob).decode(),encoding='base64'),'POST');assert created['sha']==blobsha;entry=dict(path=name,mode=mode,type='blob',sha=blobsha)
  entries.append(entry)
 tree=api('/git/trees',dict(base_tree=parent_commit['tree']['sha'],tree=entries),'POST');assert tree['sha']==fields['tree'][0],('tree_identity_mismatch',sha)
 created=api('/git/commits',dict(message=message,tree=tree['sha'],parents=[parent],author=identity(fields['author'][0]),committer=identity(fields['committer'][0])),'POST')
 assert created['sha']==sha,('commit_identity_mismatch',sha,created['sha'])
 print(json.dumps(dict(exactCommitUploaded=sha,files=len(entries))),flush=True)

tag=receipt['tag'];existing=api('/git/ref/tags/'+tag,optional=True)
if existing is None:
 raw=git('cat-file','tag','refs/tags/'+tag).decode('utf-8');headers,message=raw.split('\n\n',1);fields=dict(line.split(' ',1) for line in headers.splitlines())
 assert fields['object']==target and fields['type']=='commit' and fields['tag']==tag
 created=api('/git/tags',dict(tag=tag,message=message,object=target,type='commit',tagger=identity(fields['tagger'])),'POST');assert created['sha']==receipt['tagObject']
 api('/git/refs',dict(ref='refs/tags/'+tag,sha=created['sha']),'POST')
ref=api('/git/ref/tags/'+tag);assert ref['object']['sha']==receipt['tagObject'];assert api('/git/tags/'+ref['object']['sha'])['object']['sha']==target
current=api('/git/ref/heads/alpha')['object']['sha'];assert current in (old_alpha,target)
if current!=target:api('/git/refs/heads/alpha',dict(sha=target,force=False),'PATCH')
assert api('/git/ref/heads/alpha')['object']['sha']==target
assert api('/git/ref/heads/develop')['object']['sha']==before
for branch,sha in frozen.items():assert api('/git/ref/heads/'+branch)['object']['sha']==sha
for oldtag,sha in [('v0.1.0-alpha.2',old_alpha),('v0.1.0',frozen['release'])]:
 ref=api('/git/ref/tags/'+oldtag);assert api('/git/tags/'+ref['object']['sha'])['object']['sha']==sha
old_local=subprocess.run([*g,'rev-parse','--verify','refs/remotes/origin/alpha'],cwd=r,capture_output=True,text=True)
expected=old_local.stdout.strip() if old_local.returncode==0 else '0'*40
assert expected in (old_alpha,target,'0'*40)
subprocess.run([*g,'update-ref','refs/remotes/origin/alpha',target,expected],cwd=r,check=True)
result=dict(commit=target,tag=tag,alphaVerified=True,developPreserved=before,releaseMainAndOldTagsUnchanged=True,exactCommitAndAnnotatedTagIdentityVerified=True)
(r/'.local/alpha311/alpha-push-receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result),flush=True)
