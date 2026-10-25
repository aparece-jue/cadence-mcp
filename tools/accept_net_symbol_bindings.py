"""Selected native symbol/wire/pin object binding positive and negative cases."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import run_tcl
p=argparse.ArgumentParser()
for k in ('install-root','workspace-root','positive-root','negative-root'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);cfg=Config(a.install_root,root/'work',(root,),60);report={'passed':False,'scope':'selected page-native symbol/lead/pin binding, no cross-page or flat-net claim','cases':[]}
for case,kind,name in [('global','global','MCP_SUPPLY'),('offpage','offpage','MCP_LINK'),('global90','global','MCP_GROUND'),('offpage90','offpage','MCP_LINK')]:
 for mode,base,bound in [('lead',a.positive_root,True),('coincident',a.negative_root,False)]:
  src=(base/case/'design.dsn').resolve(strict=True);before=sha256(src);row={'case':case,'mode':mode,'passed':False,'beforeSha256':before};report['cases'].append(row)
  try:
   out=root/(case+'-'+mode+'.json');run_tcl(cfg,'inspect_net_symbol_bindings.tcl',[str(src),str(out)],root);rows=json.loads(out.read_text(encoding='utf-8'));selected=[r for r in rows if (r['schematicName'],r['pageName'])==('HALFADD','MCP_PLACE')]
   symbol=next(r for r in selected if r['kind']==kind and r['name']==name);pin=next(r for r in selected if r['kind']=='pin' and r['reference']=='R101' and r['number']=='1')
   if bound:
    wire=next(r for r in selected if r['kind']=='wire' and sorted(r['points'])==[[240,310],[290,310]])
    assert symbol['group'] is not None and symbol['group']==pin['group']==wire['group'];assert symbol['netName']==pin['netName']==wire['netName']==name;row['nativeBindingVerified']=True
   else:
    assert pin['group'] is None;row['noPinConnectionVerified']=True
   row['observedSymbolGroup']=symbol['group'];row['observedPinGroup']=pin['group'];row['fileUnchanged']=before==sha256(src);row['passed']=row['fileUnchanged']
  except Exception as e:row['error']=str(e)
  (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(case,mode,row['passed'],row.get('error'),flush=True)
report['passed']=all(c['passed'] for c in report['cases']);(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
