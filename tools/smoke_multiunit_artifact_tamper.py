"""Tamper only a retained private terminal group output; preserve original reports."""
import argparse,asyncio,json,os,shutil,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','previous-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);previous=a.previous_root.resolve(strict=True);original=previous/'report.json';report_hash=sha256(original);old=json.loads(original.read_text(encoding='utf-8'));case=old['secondGroupPreservesRepeatedReferences'];plan=case['plan'];key={k:plan[k] for k in ('planId','planDigest')};jobroot=(previous/'work').resolve(strict=True);target=(jobroot/case['result']['outputWorkspaceRelativePath']/'design.dsn').resolve(strict=True);assert target.is_relative_to(jobroot) and target.parent.name=='plan-'+key['planId'] and target.parent.parent.name=='capture_multiunit_placement';before=sha256(target);assert before==case['result']['artifact']['sha256'];shutil.copyfile(target,root/'retained-before-tamper.dsn');assert sha256(root/'retained-before-tamper.dsn')==before
intact={c['case']:sha256(jobroot/c['result']['outputWorkspaceRelativePath']/'design.dsn') for c in old['cases']};env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(jobroot),'--read-root',str(previous)],env=env)
async def main():
 report={'passed':False,'scope':'last private second-group output tamper; retained exact backup, original reports not rewritten','originalReportSha256':report_hash,'outputBefore':before}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   v=await client.call_tool('capture_open_edit_result',{**key,'kind':'multiunit_placement'});assert not v.is_error
   with target.open('ab') as f:f.write(b'controlled-multiunit-artifact-tamper')
   for tool,args in [('capture_open_edit_result',{**key,'kind':'multiunit_placement'}),('capture_recover_multiunit_placement',key),('capture_apply_multiunit_placement',{**key,'idempotencyKey':'second-group'})]:
    v=await client.call_tool(tool,args);assert v.is_error and v.structured_content['error']['code']=='target_changed',v.content
   report['openRecoverApplyRefused']=True
  report['otherOutputsUnchanged']=all(sha256(jobroot/c['result']['outputWorkspaceRelativePath']/'design.dsn')==intact[c['case']] for c in old['cases']);report['originalReportUnchanged']=sha256(original)==report_hash;report['backupUnchanged']=sha256(root/'retained-before-tamper.dsn')==before;report['passed']=report['otherOutputsUnchanged'] and report['originalReportUnchanged'] and report['backupUnchanged']
 except BaseException as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
