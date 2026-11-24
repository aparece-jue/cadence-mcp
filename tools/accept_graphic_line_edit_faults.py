"""Native precondition refusals and a saved wrong-color worker output never certified."""
import argparse
import asyncio
import copy
import json
import os
import shutil
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_graphic_line_edit import CaptureGraphicLineEdits
from cadence_mcp.capture_page_vectors import query_page_vectors
from cadence_mcp.core import CadenceError,Config,sha256
from cadence_mcp.environment import ADAPTERS,process_env
from cadence_mcp.process_tree import run_owned_process


class WrongColorWorker(CaptureGraphicLineEdits):
    def native_command(self,directory,payload):
        command=super().native_command(directory,payload)
        spec=directory/'line-spec.json';value=json.loads(spec.read_text());value['change']['lineColor']=1
        spec.write_text(json.dumps(value),encoding='utf8')
        return command


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('install-root','plan-file','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();plan_file=a.plan_file.resolve(strict=True);original_plan_hash=sha256(plan_file)
    original=json.loads(plan_file.read_text());payload=original['plan']['payload'];source=Path(payload['sourceDesign']).resolve(strict=True)
    assert '.local' in source.parts and sha256(source)==payload['sourceFingerprint']
    before=sha256(source);root=a.output.resolve();root.mkdir(exist_ok=False);config=Config(a.install_root,root/'work',(source.parent,),60)
    spec=dict(schema=1,**{k:copy.deepcopy(payload[k]) for k in ('operation','schematicName','pageName','targetIndex','targetNativeId','oldLine','change')})
    assert spec['operation']=='update' and spec['change']['lineColor']==47
    report=dict(passed=False,sourceSha256=before,originalPlanSha256=original_plan_hash,nativePreconditions=[])
    for mode in ('wrong_id','wrong_index','wrong_old_location','wrong_old_color'):
        directory=root/mode;directory.mkdir();target=directory/'design.dsn';shutil.copyfile(source,target);changed=copy.deepcopy(spec)
        if mode=='wrong_id':changed['targetNativeId']+=1
        elif mode=='wrong_index':changed['targetIndex']+=1
        elif mode=='wrong_old_location':changed['oldLine']['location'][0]+=1
        else:changed['oldLine']['lineColor']=47
        spec_path=directory/'spec.json';spec_path.write_text(json.dumps(changed),encoding='utf8')
        process=run_owned_process([a.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'write_graphic_line.tcl',a.install_root,target,spec_path,directory/'native.json'],directory,process_env(config),45)
        receipt=json.loads((directory/'native.json').read_text());unchanged=sha256(target)==before
        assert process['returnCode']==1 and process['remainingOwnedProcesses']==0 and not receipt['saved'] and unchanged
        expected_error='target_identity_changed' if mode in ('wrong_id','wrong_index') else 'old_line_changed'
        assert receipt['error']==expected_error,receipt
        report['nativePreconditions'].append(dict(case=mode,process=process,receipt=receipt,copiedDesignUnchanged=unchanged,passed=True))
    capture=CaptureService(config);sid=capture.open(capture.create_workspace(str(source))['workspaceId'])['sessionId']
    page,=[p for p in capture.sessions[sid]['data']['page'] if p['name']=='MCP_PLACE']
    graphic=query_page_vectors(capture,sid,page['objectId'],limit=1000)['items'][0]
    writer=WrongColorWorker(config,capture);plan=writer.plan_edit(sid,graphic['objectId'],'update',payload['change']);key={k:plan[k] for k in ('planId','planDigest')}
    try:writer.apply(key['planId'],key['planDigest'],'wrong-color')
    except CadenceError as error:assert error.code=='graphic_line_mismatch',error.code
    else:raise AssertionError('Wrong native color unexpectedly certified')
    directory,_,row=writer._load(key['planId']);assert row['state']=='failed' and row['process']['remainingOwnedProcesses']==0
    assert json.loads((directory/'native-result.json').read_text())['saved']
    files={name:(sha256(directory/name),(directory/name).stat().st_mtime_ns) for name in ('design.dsn','line-spec.json','native-result.json')}
    for action in ('recover','apply'):
        try:
            if action=='recover':writer.recover(key['planId'],key['planDigest'])
            else:writer.apply(key['planId'],key['planDigest'],'wrong-color')
        except CadenceError:pass
        else:raise AssertionError('Failed wrong-color job unexpectedly recovered/replayed')
    assert files=={name:(sha256(directory/name),(directory/name).stat().st_mtime_ns) for name in files}
    params=StdioServerParameters(command=sys.executable,args=['-B','-m','cadence_mcp.server','--install-root',str(a.install_root),
        '--workspace-root',str(config.workspace_root),'--read-root',str(source.parent)],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
    async def check_open():
        async with Client(params,mode='legacy',read_timeout_seconds=120) as client:
            value=await client.call_tool('capture_open_edit_result',{**key,'kind':'graphic_line'})
            assert value.is_error;return value.structured_content['error']['code']
    report['wrongSavedColor']=dict(planId=key['planId'],nativeSaveSucceeded=True,verificationError='graphic_line_mismatch',state=row['state'],
        process=row['process'],recoveryAndReplayRefused=True,nativeFilesAndTimesUnchanged=True,openError=asyncio.run(check_open()))
    capture.close(sid);report['inputsUnchanged']=sha256(source)==before and sha256(plan_file)==original_plan_hash;report['passed']=report['inputsUnchanged']
    (root/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))


if __name__=='__main__':main()
