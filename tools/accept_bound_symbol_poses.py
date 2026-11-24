"""Actual MCP bound symbol pose/lead acceptance against independent OLB-frame oracles."""
import argparse,asyncio,json,os,sys,traceback
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.core import sha256

def rotate(point,r,m):
 x,y=point
 if m:x=-x
 return [(x,y),(y,-x),(-x,-y),(-y,x)][r]
def origin(definition,r,m,anchor):
 left,top,right,bottom=definition['bounds'];corners=[rotate([x,y],r,m) for x in (left,right) for y in (top,bottom)];x,y=rotate(definition['pins'][0],r,m);return [anchor[0]-x+min(p[0] for p in corners),anchor[1]-y+min(p[1] for p in corners)]
async def run(a,root,report):
 definitions=json.loads(a.definitions.read_text(encoding='utf8'))['definitions'];cases=[]
 for kind in a.kinds:
  definition=next(d for d in definitions if d['kind']==kind)
  for mirror in (0,1):
   for rotation in range(4):cases.append({'kind':kind,'location':origin(definition,rotation,mirror,[220,310]),'rotation':rotation,'mirror':mirror,'expectedHotSpot':[220,310],'oldWirePoints':[[240,310],[290,310]],'newWirePoints':[[220,310],[290,310]]})
 (root/'expected.json').write_text(json.dumps({'sourceOLBFrameSha256':sha256(a.definitions),'definitions':definitions,'cases':cases},indent=2)+'\n',encoding='utf8');before={p:sha256(p) for p in [a.definitions,root/'expected.json',*[a.fixture_root/k/'design.dsn' for k in ('global','offpage')]]};report['inputSha256']={str(p):h for p,h in before.items()};params=StdioServerParameters(command=sys.executable,args=['-B','-m','cadence_mcp.server','--install-root',str(a.install_root),'--workspace-root',str(root/'work'),'--read-root',str(a.fixture_root),'--timeout-seconds','60'],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')});keys=[]
 async with Client(params,mode='legacy',read_timeout_seconds=180) as client:
  async def call(name,args):
   result=await client.call_tool(name,args);assert not result.is_error,result.structured_content;return result.structured_content['data']
  for kind in a.kinds:
   source=a.fixture_root/kind/'design.dsn';ws=await call('cadence_create_workspace',{'sourceDesign':str(source)});sid=(await call('capture_open',{'workspaceId':ws['workspaceId']}))['sessionId'];symbols=(await call('capture_query_connections',{'sessionId':sid,'entity':kind,'limit':1000}))['items'];target=next(s for s in symbols if s['attributes']['name']==('MCP_SUPPLY' if kind=='global' else 'MCP_LINK'));wires=(await call('capture_query_connections',{'sessionId':sid,'entity':'wire','limit':1000}))['items'];wire=next(w for w in wires if w['pageId']==target['pageId'] and w['attributes']['points']==[[240,310],[290,310]])
   for case in [c for c in cases if c['kind']==kind][:a.limit]:
    row={'case':case,'passed':False};report['cases'].append(row);args={'sessionId':sid,'symbolId':target['objectId'],'wireId':wire['objectId'],'operation':'set_pose','allowSourceCacheRebind':kind=='offpage' and (case['rotation'],case['mirror'])!=(0,0),**{k:case[k] for k in ('location','rotation','mirror','expectedHotSpot')}}
    try:
     plan=await call('capture_plan_net_symbol_edit',args);row['plan']=plan;assert plan['preview']['pose']['newWirePoints']==case['newWirePoints'];key={k:plan[k] for k in ('planId','planDigest')};ident=kind+str(case['rotation'])+str(case['mirror']);result=await call('capture_apply_net_symbol_edit',{**key,'idempotencyKey':ident});row['result']=result;assert result['nativePagePartitionsVerified']
     opened=await call('capture_open_edit_result',{**key,'kind':'net_symbol_edit'});out_sid=opened['sessionId'];saved=(await call('capture_query_connections',{'sessionId':out_sid,'entity':kind,'limit':1000}))['items'];symbol=next(s for s in saved if s['attributes']['name']==target['attributes']['name'] and s['pageId']==target['pageId']);attrs=symbol['attributes'];assert all(attrs[k]==case[v] for k,v in [('location','location'),('hotSpot','expectedHotSpot'),('rotationCode','rotation'),('mirrorCode','mirror')]);saved_wires=(await call('capture_query_connections',{'sessionId':out_sid,'entity':'wire','limit':1000}))['items'];assert next(w for w in saved_wires if w['nativeId']==wire['nativeId'] and w['pageId']==wire['pageId'])['attributes']['points']==case['newWirePoints'];await call('capture_close',{'sessionId':out_sid});job=root/'work'/result['outputWorkspaceRelativePath'];keys.append((ident,key,job/'design.dsn',sha256(job/'design.dsn')));row['passed']=True
    except BaseException:row['error']=traceback.format_exc();raise
    finally:
     (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'kind':kind,'rotation':case['rotation'],'mirror':case['mirror'],'passed':row['passed'],'error':row.get('error')}),flush=True)
   await call('capture_close',{'sessionId':sid})
 async with Client(params,mode='legacy',read_timeout_seconds=180) as fresh:
  for ident,key,path,h in keys:
   result=await fresh.call_tool('capture_apply_net_symbol_edit',{**key,'idempotencyKey':ident});assert not result.is_error and not result.structured_content['data']['mutationReplayed'];recovered=await fresh.call_tool('capture_recover_net_symbol_edit',key);assert not recovered.is_error;assert sha256(path)==h
 report['freshRecoveryNoReplay']=True;report['sourceAndOracleUnchanged']=all(sha256(p)==h for p,h in before.items());report['inputSha256']={str(p):h for p,h in before.items()};assert report['sourceAndOracleUnchanged'];report['passed']=True

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('install-root','fixture-root','definitions','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--kinds',nargs='+',choices=('global','offpage'),default=['global','offpage']);p.add_argument('--limit',type=int,default=8);a=p.parse_args();a.fixture_root=a.fixture_root.resolve();a.definitions=a.definitions.resolve();root=a.output.resolve();root.mkdir(exist_ok=False);report={'passed':False,'fullD04Accepted':False,'cases':[]}
 try:asyncio.run(run(a,root,report))
 except BaseException:report['error']=traceback.format_exc()
 finally:
  report['sourceAndOracleUnchanged']=all(sha256(Path(p))==h for p,h in report.get('inputSha256',{}).items());report['passed']=report['passed'] and report['sourceAndOracleUnchanged']
  (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
 return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
