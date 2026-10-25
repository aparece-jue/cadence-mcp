"""Isolate copied symbol-name length behavior without replaying failed jobs."""
import argparse,json,shutil,sys
from pathlib import Path
from cadence_mcp.core import Config,write_json
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);install=a.install_root.resolve(strict=True);source=a.source.resolve(strict=True);cfg=Config(install,root/'work',(root,),60)
lib=install/'tools/capture/library/capsym.olb';report={'scope':'native diagnostic only; no original ledger replay','cases':[]}
for length in (24,31,32,40):
 d=root/str(length);d.mkdir();shutil.copyfile(source,d/'design.dsn');shutil.copyfile(lib,d/'library.olb')
 spec={'schematicName':'HALFADD','pageName':'MCP_PLACE','symbol':'VCC','symbolType':33,'cacheName':'MCP_'+('A'*(length-4)),'name':'MCP_SUPPLY','location':[230,300],'rotation':0,'mirror':0,'expectedHotSpot':[240,310],'kind':'global','leadEnabled':True,'leadEnd':[290,310]};write_json(d/'request.json',spec)
 process=run_owned_process([str(install/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'create_net_symbol.tcl'),str(install),str(d/'design.dsn'),str(d/'library.olb'),str(d/'request.json'),str(d/'receipt.json')],d,process_env(cfg),60)
 row={'length':length,'process':process,'receipt':json.loads((d/'receipt.json').read_text())};report['cases'].append(row);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(row),flush=True)
