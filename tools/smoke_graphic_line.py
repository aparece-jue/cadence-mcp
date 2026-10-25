"""Internal native graphic-line proof with a prewritten independent oracle."""
import argparse,json,shutil,uuid
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_wire import inventory,connection_digest
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False)
source=a.source.resolve(strict=True);target=root/'design.dsn';shutil.copyfile(source,target)
c=Config(a.install_root.resolve(strict=True),root,(source.parent,),60)
expected={'localStart':[0,0],'localEnd':[160,0],'location':[330,310],'start':[330,310],'end':[490,310],'rotationCode':0,'mirrorCode':0}
(root/'expected.json').write_text(json.dumps({'addedLine':expected,'allDefinitionsAndPinNetsUnchanged':True,'allConnectionObjectsUnchanged':True},indent=2))
report={'passed':False,'sourceHashBefore':sha256(source),'phase':'before'}
def snapshot(label):
    cap=CaptureService(c);cap.workspaces[label]={'directory':root,'manifest':{'copiedFingerprint':sha256(target)}}
    sid=cap.open(label)['sessionId']
    try:
        data=cap.sessions[sid]['data'];objects=inventory(cap,sid)
        return {'definitions':definition_baseline(data),'connections':connection_digest(data,objects)}
    finally:cap.close(sid)
def native(op,label):
    out=root/(label+'.json')
    cmd=[c.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'graphic_line_probe.tcl',c.install_root,target,out,'HALFADD','MCP_PLACE','330','310','490','310',op]
    result=run_owned_process(list(map(str,cmd)),root,process_env(c),60)
    report.setdefault('native',{})[label]=result
    data=json.loads(out.read_text(encoding='utf-8')) if out.is_file() else None
    assert result['returnCode']==0 and result['remainingOwnedProcesses']==0,(result,data)
    return data
try:
    before=snapshot('before');lines=native('read','lines-before')['lines']
    report['phase']='add';receipt=native('add','add');assert receipt=={'saved':True,'operation':'add_graphic_line'}
    report['phase']='independent_reopen';after=snapshot('after');saved=native('read','lines-after')['lines']
    assert before==after,(before,after)
    from collections import Counter
    key=lambda row:json.dumps(row,sort_keys=True)
    assert Counter(map(key,saved))==Counter(map(key,lines))+Counter([key(expected)]),(lines,saved,expected)
    report.update(passed=True,addedLine=expected,definitionsAndPinNetsUnchanged=True,connectionObjectsUnchanged=True,
        notChecked=['font','line_style_width_color','rendered_page_bounds','other_graphic_types','titleblock_editing','other_part_properties'])
except BaseException as error:
    report['error']=str(error);report['errorType']=type(error).__name__
finally:
    report['sourceHashAfter']=sha256(source)
    if report['sourceHashAfter']!=report['sourceHashBefore']:report['passed']=False
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'phase':report['phase'],'error':report.get('error'),'report':str(root/'report.json')}))
