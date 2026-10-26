"""Recover a private read-only Capture binding after startup modal completion."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import sha256
from cadence_mcp.gui_loader import load
from cadence_mcp.bridge_rpc import RpcConnection
from prepare_gui_bridge import prepare
p=argparse.ArgumentParser()
for n in ('workspace-root','design'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--pid',type=int,required=True);a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);design=a.design.resolve();assert '.local' in design.parts and design.suffix.lower()=='.dsn';before=sha256(design);binding=prepare(root,design,a.pid,False);report={'ready':False,'sourceSha256':before,'bindingRelativePath':binding.relative_to(root).as_posix(),'expectedPid':a.pid}
try:
 report['loader']=load(binding,False,30);hello=RpcConnection(binding).call('hello',{});report['hello']={k:hello[k] for k in ('pid','instanceId','generation','data')};assert not hello['data']['bindingLost'];report['ready']=True
except Exception as e:report['error']=str(e);report['errorCode']=getattr(e,'code',None)
report['sourceUnchanged']=sha256(design)==before;report['ready']=report['ready'] and report['sourceUnchanged'];(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'ready':report['ready'],'sourceUnchanged':report['sourceUnchanged'],'bindingRelativePath':report['bindingRelativePath'],'error':report.get('error')}),flush=True)
