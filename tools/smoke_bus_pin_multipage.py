import json
from pathlib import Path
from cadence_mcp.core import Config,sha256
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_bus import query_bus
r=Path(__file__).resolve().parents[1];root=r/'.local/bus-pin-multipage-20261027';root.mkdir(exist_ok=False)
plan=next((r/'.local/part-pose-centered-20261023/work/isolated-jobs/capture_part_edit').glob('plan-*/plan.json'));source=Path(json.loads(plan.read_text(encoding='utf-8'))['plan']['payload']['sourceDesign']);before=sha256(source)
capture=CaptureService(Config(Path(r'D:\Program Files\Cadence\SPB_24.1'),root/'work',(source.parent,),30));sid=capture.open(capture.create_workspace(str(source))['workspaceId'])['sessionId'];pages=capture.sessions[sid]['data']['page'];assert len(pages)>1
rows=query_bus(capture,sid,'pin_member');assert rows['complete'] and sha256(source)==before
report=dict(passed=True,pageCount=len(pages),pinCount=len(capture.sessions[sid]['data']['pin']),membershipPairCount=rows['total'],sourceUnchanged=True,scope='multi_page_no_bus_reader_control_only')
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
