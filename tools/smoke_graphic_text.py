"""Native text/pose/font preservation test with a prewritten Unicode oracle."""
import argparse,json,shutil
from collections import Counter
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_edit import definition_baseline
from cadence_mcp.capture_wire import inventory,connection_digest
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser()
for key in ('install-root','workspace-root','source'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);source=a.source.resolve(strict=True)
target=root/'design.dsn';shutil.copyfile(source,target);c=Config(a.install_root.resolve(strict=True),root,(source.parent,),60)
expected={'text':'MCP说明 Ω\nR101 / R102','location':[300,450],'rotationCode':0,'mirrorCode':0,'font':{'name':'Arial','Height':-11,'Width':0,'Escapement':0,'Orientation':0,'Weight':400,'Italic':0,'Underline':0,'StrikeOut':0,'CharSet':0,'OutPrecision':7,'ClipPrecision':0,'Quality':1,'PitchAndFamily':16}}
(root/'expected.json').write_text(json.dumps({'addedText':expected,'definitionsAndPinNetsUnchanged':True,'connectionObjectsUnchanged':True},ensure_ascii=False,indent=2),encoding='utf-8')
report={'passed':False,'sourceHashBefore':sha256(source),'phase':'before'}
def snapshot(label):
    cap=CaptureService(c);cap.workspaces[label]={'directory':root,'manifest':{'copiedFingerprint':sha256(target)}};sid=cap.open(label)['sessionId']
    try:
        data=cap.sessions[sid]['data'];return {'definitions':definition_baseline(data),'connections':connection_digest(data,inventory(cap,sid))}
    finally:cap.close(sid)
def native(operation,label):
    out=root/(label+'.json');cmd=[c.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'graphic_text_probe.tcl',c.install_root,target,out,'HALFADD','MCP_PLACE','300','450','180','40',expected['text'],operation]
    result=run_owned_process(list(map(str,cmd)),root,process_env(c),60);report.setdefault('native',{})[label]=result
    data=json.loads(out.read_text(encoding='utf-8')) if out.is_file() else None
    assert result['returnCode']==0 and result['remainingOwnedProcesses']==0,(result,data)
    return data
try:
    before=snapshot('before');old=native('read','texts-before')['texts'];report['phase']='add'
    assert native('add','add')=={'saved':True,'operation':'add_comment_text'}
    report['phase']='independent_reopen';after=snapshot('after');saved=native('read','texts-after')['texts'];assert before==after,(before,after)
    key=lambda row:json.dumps(row,sort_keys=True)
    assert Counter(map(key,saved))==Counter(map(key,old))+Counter([key(expected)]),(old,saved,expected)
    report.update(passed=True,addedText=expected,definitionsAndPinNetsUnchanged=True,connectionObjectsUnchanged=True,notChecked=['rendered_glyphs','page_clipping','bounding_box_semantics','other_graphic_types','titleblock_editing','native_drc'])
except BaseException as error:report.update(error=str(error),errorType=type(error).__name__)
finally:
    report['sourceHashAfter']=sha256(source)
    if report['sourceHashBefore']!=report['sourceHashAfter']:report['passed']=False
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'phase':report['phase'],'error':report.get('error'),'report':str(root/'report.json')},ensure_ascii=False))
