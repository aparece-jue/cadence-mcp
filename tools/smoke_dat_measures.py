"""Use retained verified jobs; no resimulation or rewritten numerical oracle."""
import argparse,asyncio,json,math,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','dc-root','ac-root','transient-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);repo=Path(__file__).resolve().parents[1]
tau=0.001;duration=0.005
expected={'dc':2.5,'tauSeconds':tau,'cutoffHz':1/(2*math.pi*tau),'cutoffMagnitude':1/math.sqrt(2),'thresholdAtTau':1-math.exp(-1),'transientMaximum':1-math.exp(-duration/tau),'transientIntervalMean':1-tau/duration*(1-math.exp(-duration/tau)),'transientIntervalRms':math.sqrt(1-2*tau/duration*(1-math.exp(-duration/tau))+tau/(2*duration)*(1-math.exp(-2*duration/tau))),'transientAbsoluteTolerance':2e-4,'timeRelativeTolerance':0.01}
(root/'expected.json').write_text(json.dumps(expected,indent=2))
def job(name):
    base=getattr(a,name+'_root').resolve(strict=True);report=json.loads((base/'report.json').read_text())
    plan=report['lostReceiptPlan'] if name=='dc' else report['plan'] if name=='transient' else next(c['plan'] for c in report['cases'] if c['analysis']=='ac')
    sources=base/('sources' if name=='ac' else 'source');return base,sources,{k:plan[k] for k in ('planId','planDigest')}
async def main():
    report={'passed':False,'cases':[]}
    try:
        for name in ('dc','ac','transient'):
            base,sources,key=job(name);env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
            params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(base/'work'),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
            case={'analysis':name,'passed':False};report['cases'].append(case)
            async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
                tools=(await client.list_tools()).tools;assert len(tools)==82;schemas={t.name:t.output_schema for t in tools}
                for t in tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
                if name=='dc':(root/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
                async def call(tool,args):
                    r=await client.call_tool(tool,args);assert not r.is_error,r.content
                    Draft202012Validator(schemas[tool]).validate(r.structured_content);return r.structured_content['data']
                dat=await call('pspice_open_run_dat',key);ident=dat['datId'];trace='V(2)' if name=='dc' else 'V(OUT)';common={'datId':ident,'block':0,'traceName':trace}
                async def measure(**options):
                    result=await call('pspice_dat_measure',{**common,**options});assert result['jobAssociationVerified'] and result['producedByPlan']==key['planId'] and result['designPassed'] is None;return result
                summary=await measure();case['summary']=summary
                if name=='dc':
                    assert abs(summary['sampleMean']-expected['dc'])<=1e-6 and abs(summary['sampleRms']-expected['dc'])<=1e-6
                    assert summary['sampleCount']==1 and summary['intervalRms'] is None
                    assert (await client.call_tool('pspice_dat_measure',{**common,'component':'imaginary'})).is_error
                elif name=='ac':
                    mag=await measure(measurement='value_at',component='magnitude',atAxis=expected['cutoffHz']);imag=await measure(measurement='value_at',component='imaginary',atAxis=expected['cutoffHz'])
                    assert abs(mag['value']-expected['cutoffMagnitude'])<=1e-6 and abs(imag['value']+0.5)<=1e-6
                    crossing=await measure(measurement='first_crossing',component='magnitude',threshold=expected['cutoffMagnitude'],direction='falling')
                    assert crossing['found'] and abs(crossing['axisValue']/expected['cutoffHz']-1)<=0.01
                    case.update(cutoffMagnitude=mag,cutoffImaginary=imag,cutoffCrossing=crossing)
                else:
                    assert summary['sampleCount']==541
                    for key1,key2 in [('maximum','transientMaximum'),('intervalMean','transientIntervalMean'),('intervalRms','transientIntervalRms')]:assert abs(summary[key1]-expected[key2])<=expected['transientAbsoluteTolerance'],(key1,summary[key1],expected[key2])
                    at=await measure(measurement='value_at',atAxis=tau);assert abs(at['value']-expected['thresholdAtTau'])<=expected['transientAbsoluteTolerance']
                    crossing=await measure(measurement='first_crossing',threshold=expected['thresholdAtTau'],direction='rising');assert crossing['found'] and abs(crossing['axisValue']/tau-1)<=0.01
                    absent=await measure(measurement='first_crossing',threshold=2.0);assert absent['found'] is False and absent['axisValue'] is None
                    case.update(valueAtTau=at,timeConstant=crossing,absentCrossing=absent)
                for bad in [{'threshold':1.0},{'measurement':'value_at','atAxis':True},{'traceName':'V(MISSING)'},{'eval':'unsafe'}]:
                    r=await client.call_tool('pspice_dat_measure',{**common,**bad});assert r.is_error,r.content
                await call('pspice_dat_close',{'datId':ident});case['passed']=True
        report.update(passed=True,toolCount=82)
    except BaseException as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'cases':[{k:c.get(k) for k in ('analysis','passed')} for c in report['cases']],'error':report.get('error'),'report':str(root/'report.json')}))
asyncio.run(main())
