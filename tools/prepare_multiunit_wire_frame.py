"""Private VCC/GND wire-only frame with frozen full definition/object oracle."""
import argparse,copy,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256,write_json
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_wire import connection_digest
from cadence_mcp.environment import ADAPTERS,process_env,run_tcl
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','source','library-root','power-oracle'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True);libroot=a.library_root.resolve(strict=True);cfg=Config(a.install_root,root,(root,),60)
def read(script,path,name,extra):
 out=root/(name+'.json');run_tcl(cfg,script,[str(path),str(out),*extra],root);return json.loads(out.read_text(encoding='utf-8'))
before=sha256(source);lib=libroot/'library.olb';lib_hash=sha256(lib);spec=json.loads((libroot/'spec.json').read_text(encoding='utf-8'));oracle=json.loads(a.power_oracle.read_text(encoding='utf-8'));data=read('inspect.tcl',source,'baseline',['100000']);objects=read('inspect_page_objects.tcl',source,'old-objects',['connections'])['objects'];pid=next(p['objectId'] for p in data['page'] if p['name']=='MCP_PLACE');wanted=copy.deepcopy(objects);paths=[];labels={}
for net,network in oracle['netPaths'].items():
 labels[str(len(paths)+1)]=net;paths.extend(network)
 for wire in network:wanted.append({'kind':'wire','pageId':pid,'attributes':{'points':wire,'net':net}})
 wanted.append({'kind':'alias','pageId':pid,'attributes':{'name':net,'location':network[0][0],'wireId':'declared-'+net}})
expected={'definitionDigest':definition_baseline(data),'connectionDigest':connection_digest(data,wanted)};write_json(root/'expected.json',expected);request={'packageName':spec['packageName'],'cacheName':'MCP_FRAME','reference':'U501','schematicName':'HALFADD','pageName':'MCP_PLACE','units':[],'wires':paths,'wireAliases':labels};write_json(root/'request.json',request);shutil.copyfile(source,root/'design.dsn');shutil.copyfile(lib,root/'library.olb');process=run_owned_process([str(cfg.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_multiunit_group.tcl'),str(cfg.install_root),str(root/'design.dsn'),str(root/'library.olb'),str(root/'request.json'),str(root/'receipt.json')],root,process_env(cfg),60);assert process['returnCode']==0
saved=sha256(root/'design.dsn');actual=read('inspect.tcl',root/'design.dsn','definition',['100000']);actual_objects=read('inspect_page_objects.tcl',root/'design.dsn','objects',['connections'])['objects'];report={'passed':definition_baseline(actual)==expected['definitionDigest'] and connection_digest(actual,actual_objects)==expected['connectionDigest'] and before==sha256(source) and sha256(lib)==lib_hash and sha256(root/'design.dsn')==saved and process['remainingOwnedProcesses']==0,'process':process,'sourceBefore':before,'libraryBefore':lib_hash,'outputSha256':saved};write_json(root/'report.json',report);print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)
