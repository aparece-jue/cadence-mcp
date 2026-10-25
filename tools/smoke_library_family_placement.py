import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','library-root','page-fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);libroot=a.library_root.resolve();library=libroot/'valid-first-output.olb';page_root=a.page_fixture_root.resolve();creation=next(c for c in json.loads((page_root/'report.json').read_text(encoding='utf-8'))['cases'] if c['operation']=='create');source=page_root/'work'/creation['opened']['workspaceId']/'design.dsn';assert sha256(source)==creation['sha256'] and creation['opened']['counts']['part']==0 and creation['opened']['counts']['pin']==0;page_name=creation['observed']['page'][0][1];specs=json.loads((libroot/'expected.json').read_text(encoding='utf-8'))['two_footprints']['packages'];before={'dsn':sha256(source),'olb':sha256(library)}
cases=[]
for index,spec in enumerate(specs):
 pins=[{'number':str(n),'name':name,'hotSpot':hot,'connected':False,'net':None} for n,name,hot in ([('1','A',[680,300]),('2','B',[720,300])] if index==0 else [('A1','A中文[x]$;',[680,300]),('A2','B',[720,300])])]
 cases.append({'package':spec['packageName'],'partName':spec['symbols'][0]['partName'],'reference':'R'+str(811+index),'footprint':spec['footprint'],'pins':pins})
(root/'expected.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');expected_hash=sha256(root/'expected.json');env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',str(a.install_root.resolve()),'--workspace-root',str(root/'work'),'--read-root',str(source.parent),'--read-root',str(library.parent),'--timeout-seconds','60'],env=env)
report={'passed':False,'sourceBefore':before,'cases':[]}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=240) as c:
   async def call(name,args):
    response=await c.call_tool(name,args);assert not response.is_error,(name,response.structured_content);return response.structured_content['data']
   lid=(await call('capture_library_open',{'sourceLibrary':str(library)}))['libraryId'];sid=(await call('capture_open',{'workspaceId':(await call('cadence_create_workspace',{'sourceDesign':str(source)}))['workspaceId']}))['sessionId'];page=next(p for p in (await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'] if p['name']==page_name)
   for case in cases:
    row={'case':case,'passed':False};report['cases'].append(row);part=next(p for p in (await call('capture_library_query',{'libraryId':lid,'entity':'part','packageName':case['package'],'limit':1000}))['items'] if p['name']==case['partName']);plan=await call('capture_plan_placement',{'sessionId':sid,'pageId':page['objectId'],'libraryId':lid,'libraryPartId':part['objectId'],'reference':case['reference'],'location':[700,300],'value':'FAMILY_81','expectedPins':case['pins'],'expectedExistingConnections':[]});row['plan']=plan;key={k:plan[k] for k in ('planId','planDigest')};row['result']=await call('capture_apply_placement',{**key,'idempotencyKey':case['reference']});opened=await call('capture_open_edit_result',{**key,'kind':'placement'});placed=next(p for p in (await call('capture_query',{'sessionId':opened['sessionId'],'entity':'part','scope':{'kind':'design'},'limit':1000}))['items'] if p['reference']==case['reference']);props=(await call('capture_get_part_properties',{'sessionId':opened['sessionId'],'partId':placed['objectId']}))['items'];assert [p['value'] for p in props if p['name']=='PCB Footprint']==[case['footprint']];row['passed']=True
  report['sourceAfter']={'dsn':sha256(source),'olb':sha256(library)};report['passed']=report['sourceBefore']==report['sourceAfter'] and all(c['passed'] for c in report['cases']) and expected_hash==sha256(root/'expected.json')
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc())
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'error':report.get('error')},ensure_ascii=False))
 if not report['passed']:raise SystemExit(1)
asyncio.run(main())
