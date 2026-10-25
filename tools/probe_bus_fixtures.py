"""Owned 8-bit bus/entry probes with independent declared member/geometry tables."""
import argparse,json,shutil
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for n in ('install-root','workspace-root','blank-fixture-root'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
old=json.loads((a.blank_fixture_root/'report.json').read_text(encoding='utf-8'));source=a.blank_fixture_root/'work'/old['result']['outputWorkspaceRelativePath']/'design.dsn'
config=Config(a.install_root,root/'work',(source.parent,),60)
expected={'descending':[f'DATA{i}' for i in range(7,-1,-1)],'ascending':[f'DATA{i}' for i in range(8)],
 'scalarNames':[f'DATA{i}' for i in range(8)],'busPoints':[[600,200],[600,700]],
 'entryPoints':[[600,220+50*i] for i in range(8)],'endPoints':[[620,240+50*i] for i in range(8)]}
(root/'expected.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
report={'passed':False,'sourceHashBefore':sha256(source),'cases':[]}
for mode in ('descending','ascending','missing_member','detached_entry'):
    row={'mode':mode,'passed':False};report['cases'].append(row);directory=root/mode;directory.mkdir();target=directory/'design.dsn';shutil.copyfile(source,target)
    try:
        row['fixtureProcess']=run_owned_process([str(config.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'fixture_bus.tcl'),str(config.install_root),str(target),str(directory/'receipt.json'),mode],directory,process_env(config),60)
        if (directory/'receipt.json').exists():row['receipt']=json.loads((directory/'receipt.json').read_text(encoding='utf-8'))
        assert row['fixtureProcess']['state']=='exited' and row['fixtureProcess']['returnCode']==0,row.get('receipt')
        row['savedHash']=sha256(target)
        row['readProcess']=run_owned_process([str(config.install_root/'tcltk/bin/tclsh.exe'),str(ADAPTERS/'inspect_bus.tcl'),str(config.install_root),str(target),str(directory/'native.json')],directory,process_env(config),60)
        if (directory/'native.json.error.json').exists():row['nativeError']=json.loads((directory/'native.json.error.json').read_text(encoding='utf-8'))
        assert row['readProcess']['state']=='exited' and row['readProcess']['returnCode']==0,row.get('nativeError')
        data=json.loads((directory/'native.json').read_text(encoding='utf-8'));bus=[w for w in data['wires'] if w['isBus']];scalar=[w for w in data['wires'] if not w['isBus']]
        row.update(busCount=len(bus),scalarCount=len(scalar),entryCount=len(data['entries']))
        assert bus and all(w['width']==8 and not w['isBundle'] for w in bus)
        members=expected['ascending' if mode=='ascending' else 'descending']
        assert all([m['name'] for m in w['members']]==members for w in bus),[w['members'] for w in bus]
        wires={w['wireId']:w for w in data['wires']}
        complete=(len(scalar)==8 and sorted(w['name'] for w in scalar)==sorted(expected['scalarNames']) and len(data['entries'])==8
                  and sorted(e['entryPoint'] for e in data['entries'])==expected['entryPoints']
                  and sorted(e['endPoint'] for e in data['entries'])==expected['endPoints']
                  and all(e['entryWireId'] in wires and wires[e['entryWireId']]['isBus'] and e['endWireId'] in wires and not wires[e['endWireId']]['isBus'] for e in data['entries']))
        assert complete==(mode in ('descending','ascending')),{'complete':complete,'mode':mode,'data':data}
        assert sha256(target)==row['savedHash'];row.update(passed=True,completeVisualEntryStructure=complete)
    except BaseException as e:row.update(errorType=type(e).__name__,error=str(e))
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:row.get(k) for k in ('mode','passed','error')}),flush=True)
report['sourceHashAfter']=sha256(source);report['passed']=all(c['passed'] for c in report['cases']) and report['sourceHashBefore']==report['sourceHashAfter']
report['notChecked']=['physical_pin_net_oracle','hierarchical_bus_members','bundle_and_nested_types','native_drc']
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
