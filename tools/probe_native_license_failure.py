"""One bounded child-only invalid-license experiment; never changes host licensing settings."""
import argparse,asyncio,hashlib,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

p=argparse.ArgumentParser()
for name in ('workspace-root','install-root'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=root/'source';source.mkdir()
cir=source/'divider.cir';cir.write_text('* Own license diagnostic divider\nV1 1 0 DC 5\nR1 1 2 1k\nR2 2 0 1k\n.DC V1 5 5 1\n.PROBE64 V([2])\n.END\n',encoding='ascii');source_hash=sha256(cir)
invalid=root/'no-license.lic';invalid.write_text('# Own acceptance fixture: deliberately no licenses.\n',encoding='ascii')
def env_hash():return hashlib.sha256(json.dumps({k:os.environ.get(k) for k in ('CDS_LIC_FILE','CDS_LIC_ONLY','LM_LICENSE_FILE')},sort_keys=True).encode()).hexdigest()
before=env_hash();env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');env['CDS_LIC_FILE']=str(invalid);env['LM_LICENSE_FILE']=str(invalid)
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(source),'--timeout-seconds','8'],env=env)
report={'nativeLicenseFailureAccepted':False,'globalConfigurationModified':False,'childOnlyOverrides':['CDS_LIC_FILE','LM_LICENSE_FILE'],'timeoutIsLicenseEvidence':False}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=60) as client:
   async def call(name,args):
    reply=await client.call_tool(name,args);assert not reply.is_error,reply.structured_content;return reply.structured_content['data']
   prepared=await call('pspice_prepare',{'sourceCircuit':str(cir)})
   plan=await call('pspice_plan_cli_run',{'simulationId':prepared['simulationId'],'analysis':'dc','timeoutSeconds':8,'expectedSamples':[{'block':0,'row':0,'traceName':'V(2)','real':2.5,'imaginary':None,'absoluteTolerance':1e-6,'relativeTolerance':0.0}]});key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
   result=await client.call_tool('pspice_apply_cli_run',{**key,'idempotencyKey':'invalid-license-once'});report['response']=result.structured_content
   if result.is_error:
    failure=await call('pspice_inspect_run_failure',{**key,'kind':'cli'});report['failure']=failure
    report['nativeLicenseFailureAccepted']=result.structured_content['error']['code']=='pspice_license_unavailable'
   else:report['unexpectedLicensedOrFallbackSuccess']=True
 except Exception as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:
  report['parentLicenseEnvironmentUnchanged']=env_hash()==before;report['sourceUnchanged']=sha256(cir)==source_hash
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
  response=report.get('response',{});print(json.dumps({'nativeLicenseFailureAccepted':report['nativeLicenseFailureAccepted'],'errorCode':response.get('error',{}).get('code') if response.get('error') else None,'parentLicenseEnvironmentUnchanged':report['parentLicenseEnvironmentUnchanged'],'sourceUnchanged':report['sourceUnchanged'],'unexpectedSuccess':report.get('unexpectedLicensedOrFallbackSuccess',False),'error':report.get('error')}))
asyncio.run(main())
