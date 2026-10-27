import json,shutil,traceback
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
r=Path(__file__).resolve().parents[1];root=r/'.local/nested-bundle-probe-v2-20261027';root.mkdir(exist_ok=False);source=r/'.local/editor-session-wire-20261026/before.dsn';before=sha256(source);assert before=='971c4675e25441783520afdd86a898647a39f05f377cc217d5e23c2bfb671dda'
expected={'B_CHILD':{'READY':{'type':1},'DATA[7..0]':{'type':2,'width':8}},'B_TOP':{'CTRL':{'type':1},'B_CHILD':{'type':0}}}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8');oracle=sha256(root/'expected.json');target=root/'design.dsn';shutil.copy2(source,target);config=Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(root,),30);report=dict(passed=False,sourceBefore=before,expectedSha256=oracle,scope='nested_bundle_definitions_only',fullH04Accepted=False)
try:
 run_tcl(config,str(r/'tools/probe_nested_bundle_v2.tcl'),[str(target),str(root/'create.json'),'create'],root)
 after=sha256(target);run_tcl(config,str(r/'tools/probe_nested_bundle_v2.tcl'),[str(target),str(root/'read.json'),'read'],root)
 data=json.loads((root/'read.json').read_text(encoding='utf-8'));assert data['passed'];assert {b['name'] for b in data['bundles']}==set(expected)
 for bundle in data['bundles']:
  observed={m['name']:m for m in bundle['members']};wanted=expected[bundle['name']];assert len(observed)==len(bundle['members']) and set(observed)==set(wanted),(bundle,wanted)
  for name,fields in wanted.items():
   for key,value in fields.items():assert observed[name][key]==value,(name,key,observed[name],value)
 run_tcl(config,'inspect.tcl',[str(target),str(root/'definitions.json'),'100000'],root);defs=json.loads((root/'definitions.json').read_text(encoding='utf-8'));assert {k:len(v) for k,v in defs.items()}==dict(schematic=1,page=1,part=0,pin=0)
 assert sha256(target)==after;report.update(passed=True,independentProcessReopen=True,originalEmptyDefinitionsPreserved=True,targetSha256=after)
except BaseException:report['error']=traceback.format_exc()
report.update(sourceUnchanged=sha256(source)==before,oracleUnchanged=sha256(root/'expected.json')==oracle);report['passed']=report['passed'] and report['sourceUnchanged'] and report['oracleUnchanged']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
