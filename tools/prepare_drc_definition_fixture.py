import argparse,json,re,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','source-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);src=a.source_root.resolve();source=src/'lowpassfilters.dsn';before=sha256(source);target=root/'MCP_DRC_ERROR.dsn';shutil.copy2(source,target);cfg=Config(a.install_root,root/'work',(src,),60);adapter=Path(__file__).with_name('fixture_drc_definition_conflict.tcl');report={'passed':False,'sourceSha256':before}
for mode in ('write','read'):
 out=root/(mode+'.json');proc=run_owned_process([cfg.install_root/'tcltk/bin/tclsh.exe',adapter,cfg.install_root,target,out,mode],root,process_env(cfg),60);report[mode+'Process']=proc
 if out.exists():report[mode]=json.loads(out.read_text(encoding='utf-8'))
 if proc['returnCode']!=0:break
try:
 assert report['writeProcess']['returnCode']==0 and report['readProcess']['returnCode']==0
 old=report['write']['before'];expected=[{**p,'type':2} if (p['reference'],p['number']) in (('R1','2'),('R_load','2'),('R_Load1','2'),('C1','1')) else p for p in old];key=lambda p:(p['reference'],p['number']);assert len(expected)==14 and sorted(report['read']['after'],key=key)==sorted(expected,key=key)
 opj=(src/'LowPassFilters.opj').read_text(encoding='utf-8');opj=opj.replace('LowPassFilters','MCP_DRC_ERROR').replace('lowpassfilters','MCP_DRC_ERROR');opj=re.sub(r'\(Path "[A-Za-z]:[^"]*\.DSN"\)',lambda m:'(Path "'+target.as_posix()+'")',opj,flags=re.I);(root/'MCP_DRC_ERROR.opj').write_text(opj,encoding='utf-8');profile=root/'MCP_DRC_ERROR-PSpiceFiles/LPFilters/AC.sim';profile.parent.mkdir(parents=True);shutil.copy2(src/'LowPassFilters-PSpiceFiles/LPFilters/AC.sim',profile);report['passed']=True
except Exception as e:report['error']=str(e)
report['sourceUnchanged']=sha256(source)==before;report['passed']=report['passed'] and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'error':report.get('error'),'write':report.get('write')}),flush=True)
