"""Check predeclared noncentered frame hotspots through the actual MCP interface."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','matrix-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);matrix=a.matrix_root.resolve();expected_path=matrix/'expected.json';expected=json.loads(expected_path.read_text(encoding='utf-8'));assert expected['hypothesis']=='size'
sources={f"r{c['rotation']}-m{c['mirror']}":matrix/f"r{c['rotation']}-m{c['mirror']}"/'design.dsn' for c in expected['cases']}
before={k:sha256(v) for k,v in sources.items()};oracle=sha256(expected_path)
env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(matrix),'--timeout-seconds','60'],env=env)
async def main():
 report={'passed':False,'sourceSha256':before,'oracleSha256':oracle,'cases':[]}
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as c:
   async def call(name,args):
    r=await c.call_tool(name,args);assert not r.is_error,(name,r.structured_content);return r.structured_content['data']
   report['tools']=len((await c.list_tools()).tools)
   for case in expected['cases']:
    tag=f"r{case['rotation']}-m{case['mirror']}";sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(sources[tag])}))['workspaceId']}))['sessionId']
    part=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'] if p['reference']=='U3')
    data=await call('capture_get_part_geometry',{'sessionId':sid,'partId':part['objectId']})
    assert data['location']==case['location'] and data['rotationCode']==case['rotation'] and data['mirrorCode']==case['mirror']
    assert sorted((p['number'],p['name'],p['hotSpot']) for p in data['pins'])==sorted((p['number'],p['name'],p['hotSpot']) for p in case['pins'])
    assert data['readOnly'] and not data['electricalConnectivityVerified']
    await call('capture_close',{'sessionId':sid})
    closed=await c.call_tool('capture_get_part_geometry',{'sessionId':sid,'partId':part['objectId']});assert closed.is_error
    report['cases'].append({'case':tag,'passed':True,'geometry':data,'closedSessionRefused':True});print(json.dumps({'case':tag,'passed':True}),flush=True)
  report['sourceUnchanged']=all(sha256(sources[k])==h for k,h in before.items());report['oracleUnchanged']=sha256(expected_path)==oracle;report['passed']=len(report['cases'])==8 and report['sourceUnchanged'] and report['oracleUnchanged']
 except Exception as e:report['error']=str(e)
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')}),flush=True)
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
