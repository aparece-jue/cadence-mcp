"""Accept imported official DAT reads against independent axis/source constraints."""
import argparse,asyncio,json,os,sys,math
from datetime import datetime,timezone
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
parser=argparse.ArgumentParser()
parser.add_argument('--install-root',type=Path,required=True)
parser.add_argument('--workspace-root',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
install=args.install_root.resolve(strict=True);directory=args.workspace_root.resolve();directory.mkdir(exist_ok=False)
source=install/'tools/pspice/capture_samples/advanls/rfamp/rf_amp-PSpiceFiles/schematic1/ac/AC.opt.dat'
async def main():
    report={'passed':False,'createdAt':datetime.now(timezone.utc).isoformat(),'sourceHashBefore':sha256(source),
            'scope':'imported DAT reader, not solver acceptance','cases':[]}
    env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
    params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(install),
        '--workspace-root',str(directory/'work'),'--read-root',str(install/'tools/pspice/capture_samples'),'--timeout-seconds','60'],env=env)
    try:
        async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
            tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools}
            (directory/'tools-list.json').write_text(json.dumps([t.model_dump(mode='json',by_alias=True) for t in tools],indent=2),encoding='utf-8')
            report['toolCount']=len(tools)
            async def call(name,values):
                result=await client.call_tool(name,values);assert not result.is_error,result.content
                Draft202012Validator(schemas[name]).validate(result.structured_content)
                return result.structured_content['data']
            opened=await call('pspice_dat_open',{'sourceDat':str(source)})
            ident=opened['datId'];assert opened['blockCount']==21
            blocks=[];offset=0
            while True:
                row=await call('pspice_dat_query',{'datId':ident,'entity':'block','offset':offset,'limit':4})
                blocks+=row['items'];offset=row['nextOffset']
                if offset is None:break
            assert [b['index'] for b in blocks]==list(range(21))
            assert all(b['rowCount']==61 and b['complex'] and b['axis']=='Frequency' for b in blocks)
            for block in (0,10,20):
                trace_rows=[];offset=0
                while True:
                    row=await call('pspice_dat_query',{'datId':ident,'entity':'trace','block':block,'offset':offset,'limit':11})
                    trace_rows+=row['items'];offset=row['nextOffset']
                    if offset is None:break
                assert len(trace_rows)==99
                for trace in ('Frequency','V(IN)','V(0)'):
                    values=[];offset=0
                    while True:
                        row=await call('pspice_dat_samples',{'datId':ident,'block':block,'traceName':trace,'offset':offset,'limit':17})
                        values+=row['items'];offset=row['nextOffset']
                        if offset is None:break
                    assert len(values)==61
                    for index,v in enumerate(values):
                        assert v['index']==index and abs(v['imaginary'])<=1e-10
                        expected=1000*10**(index/10) if trace=='Frequency' else 1 if trace=='V(IN)' else 0
                        assert math.isclose(v['real'],expected,rel_tol=1e-11,abs_tol=1e-10),(block,trace,index,v,expected)
                    report['cases'].append({'block':block,'trace':trace,'passed':True,'samples':values})
            assert (await client.call_tool('pspice_dat_samples',{'datId':ident,'block':0,'traceName':'missing'})).is_error
            await call('pspice_dat_close',{'datId':ident})
            assert (await client.call_tool('pspice_dat_query',{'datId':ident,'entity':'block'})).is_error
            real_source=install/'tools/pspice/capture_samples/anasim/example/example-PSpiceFiles/example/tran/TRAN.dat'
            real_before=sha256(real_source)
            real_open=await call('pspice_dat_open',{'sourceDat':str(real_source)})
            real_id=real_open['datId']
            async def all_real(trace):
                values=[];offset=0
                while True:
                    page=await call('pspice_dat_samples',{'datId':real_id,'block':0,'traceName':trace,'offset':offset,'limit':13})
                    assert page['complex'] is False
                    values+=page['items'];offset=page['nextOffset']
                    if offset is None:return values
            time=await all_real('Time')
            assert len(time)==59 and time[0]['real']==0 and abs(time[-1]['real']-1e-6)<=1e-12
            assert all(a['real']<b['real'] for a,b in zip(time,time[1:]))
            for trace in ('V(VDD)','V(VEE)','V(N00240)'):
                values=await all_real(trace)
                assert len(values)==59
                for t,v in zip(time,values):
                    expected=12 if trace=='V(VDD)' else -12 if trace=='V(VEE)' else 0.1*math.sin(2*math.pi*5e6*t['real'])
                    assert v['imaginary'] is None and abs(v['real']-expected)<=1e-8,(trace,t,v,expected)
                report['cases'].append({'trace':trace,'kind':'real_transient','passed':True,'samples':values})
            assert sha256(real_source)==real_before
            report['realSourceHashBefore']=real_before;report['realSourceHashAfter']=sha256(real_source)
            with (directory/'work'/real_id/'imported.dat').open('ab') as changed:changed.write(b'changed-for-negative-test')
            stale=await client.call_tool('pspice_dat_query',{'datId':real_id,'entity':'block'})
            assert stale.is_error and stale.structured_content['error']['code']=='target_changed'
            await call('pspice_dat_close',{'datId':real_id})
            report['staleCopyRejected']=True
            report['passed']=True
    except BaseException as error:
        report['error']=str(error);raise
    finally:
        report['sourceHashAfter']=sha256(source)
        if report['sourceHashAfter']!=report['sourceHashBefore']:report['passed']=False
        (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'tools':report['toolCount'],'report':str(directory/'report.json')}))
asyncio.run(main())
