"""Original named-node selectors vs official bracket-forced forms; unchanged oracles."""
import asyncio,json,math,os,re,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
repo=Path(__file__).resolve().parents[1];old=repo/'.local/engine-analog-20261023';root=repo/'.local/named-selectors-mcp-20261025';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir()
expected=json.loads((old/'expected.json').read_text());(root/'expected.json').write_bytes((old/'expected.json').read_bytes());oracle=sha256(root/'expected.json')
originals={name:sha256(old/'sources'/(name+'.cir')) for name in ('dc','ac','transient')}
for form in ('original','wrapped','square'):
 for name in ('dc','ac','transient'):
  text=(old/'sources'/(name+'.cir')).read_text(encoding='ascii');lines=[]
  for line in text.splitlines():
   if line.startswith(('.PRINT ','.PROBE ')) and form!='original':
    for node in ('IN','OUT'):line=line.replace('V('+node+')','V(['+node+'])' if form=='wrapped' else 'V['+node+']')
   lines.append(line)
  (sources/(form+'-'+name+'.cir')).write_text('\n'.join(lines)+'\n',encoding='ascii')
before={p.name:sha256(p) for p in sources.iterdir()};env=os.environ.copy();env['PYTHONPATH']=str(repo/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(sources),'--timeout-seconds','60'],env=env)
report={'passed':False,'cases':[],'originalSourceBefore':originals,'oracleSha256':oracle,'checks':{}};keys=[]
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==173;schemas={t.name:t.output_schema for t in tools}
   async def call(name,args):
    result=await client.call_tool(name,args);assert not result.is_error,(name,result.structured_content)
    Draft202012Validator(schemas[name]).validate(result.structured_content);return result.structured_content['data']
   async def samples(ident,trace):
    rows=[];offset=0
    while True:
     result=await call('pspice_dat_samples',{'datId':ident,'block':0,'traceName':trace,'offset':offset,'limit':1000});rows+=result['items'];offset=result['nextOffset']
     if offset is None:return rows
   for form in ('original','wrapped','square'):
    for name in ('dc','ac','transient'):
     label=form+'-'+name;row={'case':label,'passed':False};report['cases'].append(row)
     prepared=await call('pspice_prepare',{'sourceCircuit':str(sources/(label+'.cir'))})
     point={'block':0,'traceName':'V(OUT)','row':0 if name!='ac' else 1,'real':2.5 if name=='dc' else 0.5 if name=='ac' else 0.0,'imaginary':-0.5 if name=='ac' else None,'absoluteTolerance':1e-6,'relativeTolerance':0.0}
     plan=await call('pspice_plan_run',{'simulationId':prepared['simulationId'],'analysis':name,'expectedSamples':[point]});key={k:plan[k] for k in ('planId','planDigest')};row['plan']=plan
     if form=='original':
      result=await client.call_tool('pspice_apply_run',{**key,'idempotencyKey':label});assert result.is_error and result.structured_content['error']['code']=='pspice_output_error',result.structured_content
      failure=await call('pspice_inspect_run_failure',key);assert any(d['code']=='ORPSIM-15090' for d in failure['output']['diagnostics']);row['failure']=failure;row['passed']=True;print(label,'original rejection confirmed',flush=True);continue
     result=await call('pspice_apply_run',{**key,'idempotencyKey':label});row['result']=result;assert result['numericalAcceptanceVerified'] and result['nativeCompletionVerified']
     opened=await call('pspice_open_run_dat',key);ident=opened['datId'];blocks=await call('pspice_dat_query',{'datId':ident,'entity':'block','limit':100});assert len(blocks['items'])==1
     block=blocks['items'][0];axis=await samples(ident,block['axis']);out=await samples(ident,'V(OUT)');vin=await samples(ident,'V(IN)');assert len(axis)==len(out)==len(vin)>0
     if name=='dc':
      assert len(out)==1 and abs(out[0]['real']-expected['dc']['outputVolts'])<=expected['dc']['absoluteTolerance'] and abs(vin[0]['real']-5)<=1e-6
      directory=root/'work/isolated-jobs/pspice_engine_run'/('plan-'+key['planId']);text=(directory/'result.out').read_text(encoding='cp1252');printed=None;lines=text.splitlines()
      for i,line in enumerate(lines):
       if re.fullmatch(r'\s*V1\s+V(?:\(\[?OUT\]?\)|\[OUT\])\s*',line,re.I):
        for following in lines[i+1:i+8]:
         m=re.fullmatch(r'\s*([+\-0-9.Ee]+)\s+([+\-0-9.Ee]+)\s*',following)
         if m and abs(float(m[1])-5)<=1e-6:printed=float(m[2])
      assert printed is not None and abs(printed-2.5)<=1e-6;row.update(outputVolts=out[0]['real'],printedVolts=printed)
     elif name=='ac':
      assert len(out)==3 and block['complex'];points=[]
      for f,v,source in zip(axis,out,vin):
       h=1/(1+1j*2*math.pi*f['real']*expected['ac']['R']*expected['ac']['C']);tol=expected['ac']['absoluteTolerance']
       assert abs(v['real']-h.real)<=tol and abs(v['imaginary']-h.imag)<=tol and abs(source['real']-1)<=tol and abs(source['imaginary'])<=tol
       points.append({'frequency':f['real'],'expectedReal':h.real,'expectedImaginary':h.imag,'actual':v})
      assert any(abs(v['imaginary'])>0.1 for v in out)
      fc=1/(2*math.pi*expected['ac']['R']*expected['ac']['C']);assert abs(axis[1]['real']/fc-1)<=expected['ac']['cutoffRelativeTolerance'] and abs(abs(complex(out[1]['real'],out[1]['imaginary']))-1/math.sqrt(2))<=tol;row.update(samples=points,cutoffHz=axis[1]['real'])
     else:
      pairs=[(t['real'],v['real']) for t,v in zip(axis,out)];tau=expected['transient']['tauSeconds'];errors=[abs(v-(1-math.exp(-t/tau))) for t,v in pairs];assert pairs[-1][0]>=0.005-1e-8 and max(errors)<=expected['transient']['absoluteTolerance']
      threshold=1-math.exp(-1);cross=None
      for (ta,va),(tb,vb) in zip(pairs,pairs[1:]):
       if va<=threshold<=vb and vb>va:cross=ta+(tb-ta)*(threshold-va)/(vb-va);break
      assert cross is not None and abs(cross/tau-1)<=expected['transient']['tauRelativeTolerance'];row.update(maxAbsoluteError=max(errors),observedTauSeconds=cross)
     row.update(passed=True,sampleCount=len(out));keys.append((label,key));await call('pspice_dat_close',{'datId':ident});print(label,'numeric oracle passed',flush=True)
  async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
   for label,key in keys:
    r=await fresh.call_tool('pspice_apply_run',{**key,'idempotencyKey':label});assert not r.is_error and not r.structured_content['data']['mutationReplayed']
    r=await fresh.call_tool('pspice_recover_run',key);assert not r.is_error
  report['checks']={'fresh_lifecycle_no_replay':True,'original_failing_sources_unchanged':originals=={name:sha256(old/'sources'/(name+'.cir')) for name in originals},'test_sources_and_original_oracle_unchanged':before=={p.name:sha256(p) for p in sources.iterdir()} and sha256(root/'expected.json')==oracle==sha256(old/'expected.json')}
  report['passed']=len(report['cases'])==9 and len(keys)==6 and all(c['passed'] for c in report['cases']) and all(report['checks'].values())
 except BaseException as error:
  import traceback
  report.update(error=str(error),traceback=traceback.format_exc())
 finally:(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(root/'report.json')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
