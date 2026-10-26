"""Actual stdio MCP native library metadata acceptance; no solver/referenced library execution."""
import asyncio,json,os,sys,shutil
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256
r=Path(__file__).resolve().parents[1];root=r/'.local/library-metadata-mcp-v2-20261026';root.mkdir(exist_ok=False);sources=root/'sources';sources.mkdir();library=sources/'own.lib';library.write_text('* independently declared metadata\n.MODEL D_META D(IS=1e-14)\n.MODEL D_AKO AKO:D_META D(IS=2e-14)\n.SUBCKT RC_META IN OUT PARAMS:R=1k\nR1 IN OUT {R}\n.ENDS RC_META\n.SUBCKT THREE_META A B C\nR1 A B 1k\nR2 B C 2k\n.ENDS THREE_META\n',encoding='utf-8');(sources/'reference.lib').write_text('.LIB other.lib\n',encoding='utf-8');shutil.copy2(Path(r'D:\Program Files\Cadence\SPB_24.1/tools/pspice/library/breakout.lib'),sources/'breakout.lib');before={p.name:sha256(p) for p in sources.iterdir()};env=os.environ.copy();env['PYTHONPATH']=str(r/'src');params=StdioServerParameters(command=sys.executable,args=['-m','cadence_mcp.server','--install-root',r'D:\Program Files\Cadence\SPB_24.1','--workspace-root',str(root/'work'),'--read-root',str(sources),'--timeout-seconds','60'],env=env);report={'passed':False,'cases':[]}
async def main():
 try:
  async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
   tools=(await client.list_tools()).tools;assert len(tools)==203;schema=next(t.output_schema for t in tools if t.name=='pspice_inspect_library')
   async def call(args):
    v=await client.call_tool('pspice_inspect_library',args);assert not v.is_error,v.structured_content;Draft202012Validator(schema).validate(v.structured_content);return v.structured_content['data']
   allrows=(await call({'sourceLibrary':str(library)}))['items'];assert {x['name'] for x in allrows}=={'D_META','D_AKO','RC_META','THREE_META'};assert next(x for x in allrows if x['name']=='D_AKO')['akoReference']=='D_META';report['cases'].append('all_four_definitions_and_ako')
   for pins,name in [(2,'RC_META'),(3,'THREE_META')]:
    data=await call({'sourceLibrary':str(library),'pinCount':pins});assert [x['name'] for x in data['items'] if x.get('matchesPinCount')]==[name];assert not data['dependencyClosureVerified'] and not data['modelValidityVerified'];report['cases'].append('formal_ports_'+str(pins))
   a=await call({'sourceLibrary':str(library),'limit':2});b=await call({'sourceLibrary':str(library),'offset':2,'limit':2});assert a['hasMore'] and not b['hasMore'] and a['items']+b['items']==allrows;report['cases'].append('paging')
   for args,code in [({'sourceLibrary':str(sources/'reference.lib')},'unsupported_library_reference'),({'sourceLibrary':str(library),'pinCount':-1},None),({'sourceLibrary':str(library),'script':'never'},None)]:
    v=await client.call_tool('pspice_inspect_library',args);assert v.is_error
    if code:assert v.structured_content['error']['code']==code
   report['cases'].append('reference_bounds_extra_field_refused')
   v=await client.call_tool('pspice_inspect_library',{'sourceLibrary':str(sources/'breakout.lib'),'limit':1000});report['officialBreakout']={'isError':v.is_error,'result':v.structured_content};report['passed']=not v.is_error
   if not v.is_error:
    official=v.structured_content['data'];assert official['total']==75 and official['localDefinitionsNotReturned']==32 and official['definitionScope']=='top_level'
 except Exception as e:
  import traceback
  report.update(error=str(e),traceback=traceback.format_exc())
 finally:
  report['sourcesUnchanged']=before=={p.name:sha256(p) for p in sources.iterdir()};report['passed']=report['passed'] and report['sourcesUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'passed':report['passed'],'cases':report['cases'],'officialBreakoutError':report.get('officialBreakout',{}).get('isError'),'error':report.get('error')}),flush=True)
asyncio.run(main())
