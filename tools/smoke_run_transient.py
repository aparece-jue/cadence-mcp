"""MCP transient job + whole RC response numerical oracle."""
import argparse,asyncio,json,math,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=root/'source';source.mkdir();repo=Path(__file__).resolve().parents[1]
circuit=source/'rc.cir';circuit.write_text('* independent persistent RC transient\nV1 IN 0 PULSE(0 1 0 1n 1n 10m 20m)\nR1 IN OUT 1k\nC1 OUT 0 1u IC=0\n.OPTIONS RELTOL=1e-6 ABSTOL=1p VNTOL=1u\n.TRAN 10u 5m 0 10u UIC\n.PROBE\n.END\n',encoding='ascii')
expected={'tauSeconds':0.001,'response':'1-exp(-t/tau)','pointwiseAbsoluteTolerance':2e-4,'tauRelativeTolerance':0.01,'firstOutput':0.0}
(root/'expected.json').write_text(json.dumps(expected,indent=2));before=sha256(circuit)
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(source),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'sourceHashBefore':before}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            async def call(name,args):
                r=await client.call_tool(name,args);assert not r.is_error,r.content
                return r.structured_content['data']
            prepared=await call('pspice_prepare',{'sourceCircuit':str(circuit)})
            plan=await call('pspice_plan_run',{'simulationId':prepared['simulationId'],'analysis':'transient','expectedSamples':[{'traceName':'V(OUT)','row':0,'real':0.0,'absoluteTolerance':1e-8}]});key={k:plan[k] for k in ('planId','planDigest')};report['plan']=plan
            result=await call('pspice_apply_run',{**key,'idempotencyKey':'transient-rc'});report['result']=result
            dat=await call('pspice_open_run_dat',key);assert dat['jobAssociationVerified'] and dat['producedByPlan']==key['planId']
            async def trace(name):
                values=[];offset=0
                while True:
                    page=await call('pspice_dat_samples',{'datId':dat['datId'],'block':0,'traceName':name,'offset':offset,'limit':200});assert page['jobAssociationVerified'];values+=page['items'];offset=page['nextOffset']
                    if offset is None:return values
            times=await trace('Time');values=await trace('V(OUT)');assert len(times)==len(values)>2
            pairs=[(t['real'],v['real']) for t,v in zip(times,values)];assert pairs[0][0]<=1e-9 and pairs[-1][0]>=0.005-1e-8
            errors=[abs(v-(1-math.exp(-t/expected['tauSeconds']))) for t,v in pairs];assert max(errors)<=expected['pointwiseAbsoluteTolerance'],max(errors)
            threshold=1-math.exp(-1);cross=None
            for (ta,va),(tb,vb) in zip(pairs,pairs[1:]):
                if va<=threshold<=vb and vb>va:cross=ta+(tb-ta)*(threshold-va)/(vb-va);break
            assert cross is not None and abs(cross/expected['tauSeconds']-1)<=expected['tauRelativeTolerance'],cross
            report.update(sampleCount=len(pairs),maxAbsoluteError=max(errors),observedTauSeconds=cross,passed=True)
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    finally:
        report['sourceHashAfter']=sha256(circuit)
        if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
        (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'error':report.get('error'),'rows':report.get('sampleCount'),'tau':report.get('observedTauSeconds'),'report':str(root/'report.json')}))
asyncio.run(main())
