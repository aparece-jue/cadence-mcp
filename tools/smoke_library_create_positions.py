import argparse,json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.library import LibraryService
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);target=root/'fixture.olb';config=Config(a.install_root.resolve(strict=True),root/'reads',(root,),60)
expected={'1':['A',[-20,0],4,True,0],'2':['B',[20,0],4,True,1]};(root/'expected.json').write_text(json.dumps({'pins':expected,'counts':{'package':1,'device':1,'cell':1,'part':1,'pin':2},'footprint':'MCP_TEST_FOOTPRINT'},indent=2))
report={'passed':False,'phase':'native_create'}
try:
    report['process']=run_owned_process(list(map(str,[config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'create_library_positions.tcl',config.install_root,target])),root,process_env(config),60)
    if (root/'native-result.json').is_file():report['native']=json.loads((root/'native-result.json').read_text(encoding='utf-8'))
    assert report['process']['state']=='exited' and report['process']['returnCode']==0 and report['process']['remainingOwnedProcesses']==0,report.get('native',report['process'])
    report['phase']='independent_reopen';lib=LibraryService(config);opened=lib.open(str(target));ident=opened['libraryId'];pins=lib.query(ident,'pin','MCP_R_FIXTURE',None,100)['items']
    actual={pin['number']:[pin['name'],pin['hotSpot'],pin['pinType'],pin['visible'],pin['position']] for pin in pins};assert actual==expected,actual
    assert opened['counts']=={'package':1,'device':1,'cell':1,'part':1,'pin':2}
    packages=lib.query(ident,'package','MCP_R_FIXTURE',None,100)['items'];assert packages[0]['footprint']=='MCP_TEST_FOOTPRINT' and packages[0]['size']==1 and packages[0]['homogeneous'] is True
    devices=lib.query(ident,'device','MCP_R_FIXTURE',None,100)['items'];assert len(devices)==1 and devices[0]['designator']=='A' and devices[0]['position']==0
    cells=lib.query(ident,'cell','MCP_R_FIXTURE',None,100)['items'];assert [r['name'] for r in cells]==['MCP_R_CELL']
    parts=lib.query(ident,'part','MCP_R_FIXTURE',None,100)['items'];assert [r['name'] for r in parts]==['MCP_R_PART']
    report.update(passed=True,librarySha256=sha256(target),opened=opened,observedPins=actual)
except BaseException as error:report.update(error=str(error),errorType=type(error).__name__)
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'phase':report['phase'],'native':report.get('native'),'error':report.get('error'),'report':str(root/'report.json')}))
