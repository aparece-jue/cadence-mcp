"""Actual public geometry API against all source-frozen broad C03 pose cases."""
import asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];native=r/'.local/c03-general-frames-v2-20261028'
prior=json.loads((native/'report.json').read_text(encoding='utf-8'));assert prior['passed'] and len(prior['cases'])==24
oracle_path=native/'expected.json';oracle=sha256(oracle_path);expected=json.loads(oracle_path.read_text(encoding='utf-8'))
root=r/'.local/c03-general-frames-mcp-20261028';root.mkdir(exist_ok=False)
env=os.environ.copy();env['PYTHONPATH']=str(r/'src')
params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(native),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'cases':[],'fullC03Accepted':False,'sourceOracleSha256':oracle}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
   tools=(await client.list_tools()).tools;schemas={t.name:t.output_schema for t in tools};report['toolCount']=len(tools)
   async def call(name,args,error=None):
    value=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(value.structured_content)
    if error:assert value.is_error and value.structured_content['error']['code']==error,value
    else:assert not value.is_error,value
    return value.structured_content.get('data')
   first_sid=None
   for case,want in zip(prior['cases'],expected['cases']):
    assert (case['label'],case['rotation'],case['mirror'])==(want['label'],want['rotation'],want['mirror'])
    path=Path(case['target']);assert sha256(path)==case['targetSha256']
    ws=await call('cadence_create_workspace',{'sourceDesign':str(path)});opened=await call('capture_open',{'workspaceId':ws['workspaceId']});sid=opened['sessionId'];first_sid=first_sid or sid
    args={'sessionId':sid,'partId':want['partId']};got=await call('capture_get_part_geometry',args)
    assert got['location']==want['location'] and got['rotationCode']==want['rotation'] and got['mirrorCode']==want['mirror']
    key=lambda p:(p['number'],p['name'],p['hotSpot']);assert sorted(map(key,got['pins']))==sorted(map(key,want['pins']))
    assert len({p['pinId'] for p in got['pins']})==len(want['pins']) and all(p['pinId'].startswith(want['partId']+'/pin-') for p in got['pins'])
    assert got['revision']==opened['revision'] and got['readOnly'] and not got['electricalConnectivityVerified']
    await call('capture_get_part_geometry',{'sessionId':sid,'partId':'foreign'},'object_not_found')
    if case['label']=='original' and case['rotation']==0 and case['mirror']==0:
     duplicate=await call('capture_get_part_geometry',{'sessionId':sid,'partId':'schematic-1/page-1/part-3'})
     assert duplicate['reference']==got['reference']=='U3' and duplicate['partId']!=got['partId'] and duplicate['pins']!=got['pins']
     report['duplicateReferencePartIdIsolationAccepted']=True
    report['cases'].append({'label':case['label'],'rotation':case['rotation'],'mirror':case['mirror'],'passed':True,'actual':got})
    if case==prior['cases'][-1]:
     (root/'work'/ws['workspaceId']/'design.dsn').write_bytes(b'owned C03 immutable revision negative')
     await call('capture_get_part_geometry',args,'target_changed')
    await call('capture_close',{'sessionId':sid});await call('capture_get_part_geometry',args,'session_lost')
    print(json.dumps({'label':case['label'],'rotation':case['rotation'],'mirror':case['mirror'],'passed':True}),flush=True)
  async with Client(params,mode='legacy',read_timeout_seconds=90) as fresh:
   response=await fresh.call_tool('capture_get_part_geometry',{'sessionId':first_sid,'partId':expected['cases'][0]['partId']});assert response.is_error and response.structured_content['error']['code']=='session_lost'
  report.update(passed=True,all24PublicPoseReadsAccepted=True,wrongTargetStaleClosedAndFreshServerGuardsAccepted=True)
 except BaseException:report['error']=traceback.format_exc()
 report['sourcesUnchanged']=all(sha256(Path(c['target']))==c['targetSha256'] for c in prior['cases'])
 report['originalInputsUnchanged']=all(sha256(Path(s['source']))==s['sourceSha256'] for s in expected['sources'])
 report['oldFailedOraclesUnchanged']=all(sha256(r/p)==h for p,h in expected['originalEvidenceSha256'].items())
 report['oracleUnchanged']=sha256(oracle_path)==oracle
 report['passed']=report['passed'] and all(report[k] for k in ('sourcesUnchanged','originalInputsUnchanged','oldFailedOraclesUnchanged','oracleUnchanged'))
 (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'acceptedCases':len(report['cases']),'error':report.get('error')}),flush=True)
 return 0 if report['passed'] else 1
raise SystemExit(asyncio.run(main()))
