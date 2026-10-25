"""Accept retained fresh engine artifacts through actual public DAT tools."""
import argparse,asyncio,json,math,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
from cadence_mcp.pspice_output import parse_out
p=argparse.ArgumentParser();p.add_argument('--install-root',type=Path,required=True);p.add_argument('--fixture-root',type=Path,required=True);p.add_argument('--workspace-root',type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);fixture=a.fixture_root.resolve(strict=True);repo=Path(__file__).resolve().parents[1]
proof=json.loads((fixture/'report.json').read_text());expected=json.loads((fixture/'expected.json').read_text());expected_hash=sha256(fixture/'expected.json')
env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve(strict=True)),'--workspace-root',str(root/'work'),'--read-root',str(fixture),'--timeout-seconds','60'],env=env)
async def main():
    report={'passed':False,'fixtureReportSha256':sha256(fixture/'report.json'),'prewrittenExpectedSha256':expected_hash,'cases':[],'jobServiceVerified':False}
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            report['toolCount']=len((await client.list_tools()).tools)
            async def call(name,args):
                r=await client.call_tool(name,args);assert not r.is_error,r.content
                return r.structured_content['data']
            async def samples(ident,trace):
                rows=[];offset=0
                while True:
                    page=await call('pspice_dat_samples',{'datId':ident,'block':0,'traceName':trace,'offset':offset,'limit':1000});rows+=page['items'];offset=page['nextOffset']
                    if offset is None:return rows
            for original in proof['cases']:
                name=original['analysis'];task=fixture/original['taskRelativePath'];case={'analysis':name,'passed':False,'phase':'provenance'};report['cases'].append(case)
                try:
                    source=fixture/'sources'/(name+'.cir');assert sha256(source)==proof['sourceHashesBefore'][name]==proof['sourceHashesAfter'][name]
                    process=original['process'];assert process['state']=='exited' and process['returnCode']==0 and process['remainingOwnedProcesses']==0
                    receipt=json.loads((task/'receipt.json').read_text());assert receipt['caught']==0
                    assert all(receipt['returns'][key]=='0' for key in ('setupReturn','analysisReturn','finishReturn','cleanupReturn'))
                    assert not parse_out((task/'result.out').read_text(encoding='ascii'))['hasErrorDiagnostics']
                    case['phase']='public_dat_open';opened=await call('pspice_dat_open',{'sourceDat':str(task/'result.dat')});ident=opened['datId'];case['opened']=opened
                    try:
                        blocks=(await call('pspice_dat_query',{'datId':ident,'entity':'block'}))['items'];assert len(blocks)==1
                        block=blocks[0];axis=await samples(ident,block['axis']);out=await samples(ident,'V(OUT)');vin=await samples(ident,'V(IN)');assert len(axis)==len(out)==len(vin)>0
                        # Unknown names must be rejected by the host, without native get on absent names.
                        assert (await client.call_tool('pspice_dat_samples',{'datId':ident,'block':0,'traceName':'V(MISSING)'})).is_error
                        case.update(phase='numeric_oracle',block=block,sampleCount=len(out))
                        if name=='dc':
                            spec=expected['dc'];assert not block['complex'] and len(out)==1
                            assert abs(vin[0]['real']-spec['inputVolts'])<=spec['absoluteTolerance'] and abs(out[0]['real']-spec['outputVolts'])<=spec['absoluteTolerance']
                            case['observedVolts']=out[0]['real']
                        elif name=='ac':
                            spec=expected['ac'];assert block['complex'] and len(out)==3;checked=[]
                            for f,v,source_value in zip(axis,out,vin):
                                frequency=f['real'];h=1/(1+1j*2*math.pi*frequency*spec['R']*spec['C'])
                                assert abs(f['imaginary'])<=spec['absoluteTolerance']
                                assert abs(source_value['real']-1)<=spec['absoluteTolerance'] and abs(source_value['imaginary'])<=spec['absoluteTolerance']
                                assert abs(v['real']-h.real)<=spec['absoluteTolerance'] and abs(v['imaginary']-h.imag)<=spec['absoluteTolerance'],(frequency,v,h)
                                checked.append({'frequency':frequency,'expectedReal':h.real,'expectedImaginary':h.imag,'actual':v})
                            assert any(abs(v['imaginary'])>0.1 for v in out)
                            cutoff=axis[1]['real'];assert abs(cutoff/(1/(2*math.pi*spec['R']*spec['C']))-1)<=spec['cutoffRelativeTolerance']
                            assert abs(abs(complex(out[1]['real'],out[1]['imaginary']))-1/math.sqrt(2))<=spec['absoluteTolerance']
                            case.update(samples=checked,cutoffHz=cutoff,nonzeroImaginaryVerified=True)
                        else:
                            spec=expected['transient'];assert not block['complex'];pairs=[(t['real'],v['real']) for t,v in zip(axis,out)]
                            assert pairs[0][0]<=1e-9 and pairs[-1][0]>=0.005-1e-8
                            errors=[abs(v-(1-math.exp(-t/spec['tauSeconds']))) for t,v in pairs];assert max(errors)<=spec['absoluteTolerance'],max(errors)
                            threshold=1-math.exp(-1);cross=None
                            for (ta,va),(tb,vb) in zip(pairs,pairs[1:]):
                                if va<=threshold<=vb and vb>va:cross=ta+(tb-ta)*(threshold-va)/(vb-va);break
                            assert cross is not None and abs(cross/spec['tauSeconds']-1)<=spec['tauRelativeTolerance'],cross
                            case.update(maxAbsoluteError=max(errors),observedTauSeconds=cross)
                        case.update(passed=True,sourceSha256=sha256(source),artifacts=[{'name':p.name,'sha256':sha256(p),'size':p.stat().st_size} for p in (task/'input.cir',task/'result.out',task/'result.dat',task/'receipt.json')])
                    finally:await call('pspice_dat_close',{'datId':ident})
                except BaseException as error:case.update(error=str(error),errorType=type(error).__name__)
        assert sha256(fixture/'expected.json')==expected_hash
        report['passed']=all(c['passed'] for c in report['cases']) and len(report['cases'])==3
    except BaseException as error:report['error']=str(error)
    finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'cases':[{k:c.get(k) for k in ('analysis','passed','phase','error','observedVolts','cutoffHz','observedTauSeconds')} for c in report['cases']],'report':str(root/'report.json')}))
asyncio.run(main())
