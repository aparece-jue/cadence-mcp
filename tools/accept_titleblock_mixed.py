"""Actual MCP titleblock mixed-vector, bitmap byte and all-pose control-point acceptance."""
import argparse,asyncio,copy,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256

def corners(box):
 x,y,xx,yy=box;return [[x,y],[xx,y],[xx,yy],[x,yy]]
def points(v):
 if v[0]=='line':return v[1:3]
 if v[0] in ('box','ellipse'):return corners(v[1])
 if v[0]=='arc':return corners(v[1])+v[2:4]
 if v[0] in ('polygon','polyline','bezier'):return v[1]
 if v[0]=='text':return [v[2]]+corners(v[3])
 if v[0]=='bitmap':return [v[2]]+corners(v[1])
 raise AssertionError(v)
def transform(p,pose):
 x,y=p
 if pose['mirrorCode']:x=-x
 x,y=[(x,y),(y,-x),(-x,-y),(-y,x)][pose['rotationCode']]
 return [pose['location'][0]+x,pose['location'][1]+y]
async def run(a,root,report):
 fixture=a.fixture_root;source=fixture/'design.dsn';oracle=fixture/'expected.json';expected=json.loads(oracle.read_text(encoding='utf8'));inputs={p:sha256(p) for p in [source,oracle,*fixture.glob('*.bmp')]};prefix=[['line',[-30,10],[140,90],0,0],['box',[-30,10,140,90],0,0,1,0],['ellipse',[0,20,80,70],0,0,0,0],['arc',[-20,20,100,80],[-20,50],[40,20],0,0],['text','标题 Ω 00123\nRevision A',[0,20],[0,20,100,40],['Arial',-10,0,0,0,400,0,0,0,0,7,0,1,16]]];want=prefix+expected['appendedDescriptors'];params=StdioServerParameters(command=sys.executable,args=['-B','-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(fixture)],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
   schemas={t.name:t.output_schema for t in (await client.list_tools()).tools}
   async def call(name,args,error=None):
    r=await client.call_tool(name,args);Draft202012Validator(schemas[name]).validate(r.structured_content)
    if error:assert r.is_error and r.structured_content['error']['code']==error,r.structured_content
    else:assert not r.is_error,r.structured_content
    return r.structured_content['data']
   ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];pages=(await call('capture_query',{'sessionId':sid,'entity':'page','scope':{'kind':'design'},'limit':1000}))['items'];names={p['objectId']:p['name'] for p in pages};titles=(await call('capture_query_graphics',{'sessionId':sid,'entity':'titleblock','limit':1000}))['items'];assert len(titles)==9
   for title in titles:
    attrs=title['attributes'];pose=next(p for p in expected['originalPoses'] if p['page']==names[title['pageId']] and p['rotationCode']==attrs['rotationCode'] and p['mirrorCode']==attrs['mirrorCode']);assert pose['location']==attrs['location'];key={'sessionId':sid,'titleblockId':title['objectId']};data=await call('capture_query_titleblock_vectors',{**key,'limit':1000});assert data['total']==11 and data['unsupportedCount']==1 and not data['supportedGeometryComplete'] and not data['renderedBoundsVerified'];rows=data['items']
    for index,desc in enumerate(want):
     actual=rows[index];local=actual['localDescriptor'];assert (local[:-1] if desc[0]=='text' else local)==desc,(index,local,desc)
     assert actual['pageControlPoints']==[transform(p,pose) for p in points(desc)],(index,actual['pageControlPoints']);assert actual['nativeId'] is None and actual['titleblockId']==title['objectId']
    assert rows[-1]['kind']=='unsupported' and rows[-1]['localDescriptor'] is None and not rows[-1]['pageControlPoints'];paged=[];cursor=None
    while True:
     page=await call('capture_query_titleblock_vectors',{**key,'limit':2,**({'cursor':cursor} if cursor else {})});paged.extend(page['items']);cursor=page['nextCursor']
     if cursor is None:break
    assert paged==rows;report['cases'].append({'page':names[title['pageId']],'rotationCode':pose['rotationCode'],'mirrorCode':pose['mirrorCode'],'vectors':11,'bitmapDibHashes':[r['localDescriptor'][-1] for r in rows if r['kind']=='bitmap'],'passed':True});print(json.dumps(report['cases'][-1]),flush=True)
   key={'sessionId':sid,'titleblockId':titles[0]['objectId']};first=await call('capture_query_titleblock_vectors',{**key,'limit':2});await call('capture_query_titleblock_vectors',{'sessionId':sid,'titleblockId':titles[1]['objectId'],'limit':2,'cursor':first['nextCursor']},'stale_cursor')
   copy=root/'work'/ws['workspaceId']/'design.dsn';copy.write_bytes(copy.read_bytes()+b'owned negative');await call('capture_query_titleblock_vectors',key,'target_changed');await call('capture_close',{'sessionId':sid});await call('capture_query_titleblock_vectors',key,'session_lost');report.update(cachedSourceTamperRefused=True,crossTitleCursorRefused=True,closedSessionRefused=True,passed=True)
 except BaseException:report['error']=traceback.format_exc()
 finally:report['sourceAndOracleUnchanged']=all(sha256(p)==h for p,h in inputs.items());report['inputSha256']={p.name:h for p,h in inputs.items()};report['passed']=report['passed'] and report['sourceAndOracleUnchanged']

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('install-root','fixture-root','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();a.fixture_root=a.fixture_root.resolve();root=a.output.resolve();root.mkdir(exist_ok=False);report={'passed':False,'fullC05Accepted':False,'cases':[]};asyncio.run(run(a,root,report));(root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'error':report.get('error')}));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
