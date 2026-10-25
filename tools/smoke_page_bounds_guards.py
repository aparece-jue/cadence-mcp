"""Native traversal boundary faults and immutable-session cache guards for page bounds."""
import argparse,asyncio,json,os,sys,shutil
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve();cfg=Config(a.install_root,root/'work',(root,source.parent),60);before=sha256(source);reader=ADAPTERS/'inspect_page_dimensions.tcl';code=reader.read_text(encoding='utf-8');reader_hash=sha256(reader);report={'passed':False,'sourceSha256':before,'readerSha256':reader_hash,'nativeCases':[],'checks':{}}
for mode in ('normal','page','view'):
 d=root/mode;d.mkdir();shutil.copy2(ADAPTERS/'json.tcl',d/'json.tcl');out=d/'dimensions.json';script=code
 if mode!='normal':
  script=script.replace('set session "";set rc [catch {','proc cmcp::fault {method args} {switch -- $method {Failed {return 1} Code {return 3969} default {error unexpected_fault_method}}}\nset session "";set rc [catch {',1)
  needle='set p [$pi NextPage $st]' if mode=='page' else 'set v [$vi NextView $st]';var='p' if mode=='page' else 'v';assert script.count(needle)==1
  replacement='if {[llength $matches]>0} {set f [open [file join [file dirname $output] injected.txt] w];puts $f 3969;close $f;rename $st ${st}_native;interp alias {} $st {} cmcp::fault;set '+var+' NULL} else {'+needle+'}'
  script=script.replace(needle,replacement,1)
 adapter=d/'reader.tcl';adapter.write_text(script,encoding='utf-8');proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',adapter,cfg.install_root,source,out,'HALFADD','BOUND_MAIN'],d,process_env(cfg),60)
 if mode=='normal':accepted=proc['returnCode']==0 and out.exists() and json.loads(out.read_text(encoding='utf-8'))['docUnits']==[970,720]
 else:accepted=proc['returnCode']!=0 and not out.exists() and (d/'injected.txt').read_text().strip()=='3969'
 accepted=accepted and proc['remainingOwnedProcesses']==0;report['nativeCases'].append({'mode':mode,'acceptedExpected':accepted,'process':proc,'outputExists':out.exists()});print(json.dumps({'mode':mode,'acceptedExpected':accepted}),flush=True)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--timeout-seconds','60'],env=env)
async def main():
 async with Client(params,mode='legacy',read_timeout_seconds=120) as c:
  async def call(n,args):
   r=await c.call_tool(n,args);assert not r.is_error,(n,r.structured_content);return r.structured_content['data']
  ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'] if p['name']=='BOUND_MAIN');args={'sessionId':sid,'pageId':page['objectId']}
  first=await call('capture_get_page_dimensions',args);assert first==await call('capture_get_page_dimensions',args);await call('capture_check_page_graphic_bounds',args)
  copied=root/'work'/ws['workspaceId']/'design.dsn';assert copied!=source
  with copied.open('ab') as f:f.write(b'controlled private revision guard')
  for name in ('capture_get_page_dimensions','capture_check_page_graphic_bounds'):
   bad=await c.call_tool(name,args);assert bad.is_error and bad.structured_content['error']['code']=='target_changed'
  await call('capture_close',{'sessionId':sid});report['checks']['cached_dimensions_and_graphics_reject_changed_private_revision']=True
 report['sourceUnchanged']=sha256(source)==before;report['readerUnchanged']=sha256(reader)==reader_hash;report['passed']=all(c['acceptedExpected'] for c in report['nativeCases']) and all(report['checks'].values()) and report['sourceUnchanged'] and report['readerUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed']}),flush=True)
asyncio.run(main())
