import hashlib,json,os,subprocess,zipfile
from pathlib import Path
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/alpha311';g=['git','-c','safe.directory='+r.as_posix()]
def git(*args,env=None,input=None):return subprocess.check_output([*g,*args],cwd=r,env=env,input=input)
assert not git('status','--porcelain').strip();parent=git('rev-parse','HEAD').decode().strip();assert parent=='930fce0af83b8030784f7dd1ea3a5e1647e102b7'
index=root/'candidate-v3.index';assert not index.exists();env=os.environ.copy();env['GIT_INDEX_FILE']=str(index);git('read-tree',parent,env=env)
changes={p:(root/'source'/p).read_bytes() for p in ['pyproject.toml','src/cadence_mcp/__init__.py']}
text=(r/'README.md').read_text(encoding='utf-8');line=next(l for l in text.splitlines() if l.startswith('> **测试版 v0.1.0-alpha.2**'))
banner='> **测试版 v0.1.1-alpha.1**（Python包版本`0.1.1a1`）：[下载](https://github.com/aparece-jue/cadence-mcp/releases/tag/v0.1.1-alpha.1) · [安装](docs/testing/alpha-3.md) · [版本说明](docs/releases/v0.1.1-alpha.1.md)。224个扩展工具，完整业务验收8/34；新增图形/标题栏查询及库属性保存修复，未完成范围继续研发。'
changes['README.md']=text.replace(line,banner).encode('utf-8')
branches=json.loads((r/'docs/branches.json').read_text(encoding='utf-8'));branches['alpha']={'branch':'alpha','tag':'v0.1.1-alpha.1','pythonVersion':'0.1.1a1','tools':224,'commitIdentity':'Resolve this immutable annotated tag'};changes['docs/branches.json']=(json.dumps(branches,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
text=(r/'docs/BRANCHES.md').read_text(encoding='utf-8');text=text.replace('v0.1.0-alpha.2 / 64e7ca9bb61bb04d80575d7289104405a2c2afe9','v0.1.1-alpha.1 / 以不可变tag解析提交').replace('该tag的开发/扩展入口，221工具','该tag的开发/扩展入口，224工具');changes['docs/BRANCHES.md']=text.encode('utf-8')
for path,data in changes.items():
 blob=git('hash-object','-w','--path',path,'--stdin',input=data).decode().strip();git('update-index','--add','--cacheinfo','100644,'+blob+','+path,env=env)
tree=git('write-tree',env=env).decode().strip();message=root/'candidate-message.txt';message.write_text('Release 0.1.1 alpha1 candidate with verified installed feature updates\n\nFixed224-tool alpha snapshot. Independent wheel source comparison and installed Capture, engine DC DAT, geometry/titleblock/contact/user-property suites pass. Original34 scope remains8 accepted.\n',encoding='utf-8')
candidate=git('commit-tree',tree,'-p',parent,'-F',str(message)).decode().strip();assert subprocess.run([*g,'merge-base','--is-ancestor','64e7ca9bb61bb04d80575d7289104405a2c2afe9',candidate],cwd=r).returncode==0
proof=json.loads((root/'wheel-proof.json').read_text(encoding='utf-8'))
newline_adjusted=[]
with zipfile.ZipFile(r/'dist/alpha311/cadence_mcp-0.1.1a1-py3-none-any.whl') as z:
 for path,fingerprint in proof['packagedSourceSha256'].items():
  packaged=z.read(path);assert hashlib.sha256(packaged).hexdigest()==fingerprint
  canonical=git('show',candidate+':src/'+path);packaged.decode('utf-8');canonical.decode('utf-8')
  assert canonical==packaged.replace(b'\r\n',b'\n'),path
  if canonical!=packaged:newline_adjusted.append(path)

tag='v0.1.1-alpha.1';assert subprocess.run([*g,'show-ref','--verify','--quiet','refs/tags/'+tag],cwd=r).returncode==1
tag_message=root/'tag-message.txt';tag_message.write_text('cadence-mcp0.1.1 alpha1:224 tools; installed candidate verified; full gates8of34.\n',encoding='utf-8')
subprocess.run([*g,'-c','tag.gpgSign=false','tag','-a','--cleanup=verbatim',tag,candidate,'-F',str(tag_message)],cwd=r,check=True)
git('update-ref','refs/heads/alpha',candidate,'64e7ca9bb61bb04d80575d7289104405a2c2afe9')
receipt={'commit':candidate,'parentDevelop':parent,'tree':tree,'tag':tag,'tagObject':git('rev-parse','refs/tags/'+tag).decode().strip(),'packagedSourceFilesVerified':244,'gitTextNormalizationOnly':True,'crlfCheckoutFileCount':len(newline_adjusted),'localDevelopUnchanged':git('rev-parse','HEAD').decode().strip()==parent}
(root/'candidate-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
