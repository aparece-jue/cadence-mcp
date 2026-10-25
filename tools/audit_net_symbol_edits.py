"""Read-only integrity audit; never promotes failed native cases."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import sha256,write_json
p=argparse.ArgumentParser()
for key in ('report-root','source-root','disconnect-root'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();report_path=a.report_root/'report.json';before=sha256(report_path);report=json.loads(report_path.read_text());fault_path=a.disconnect_root/'report.json';fault_before=sha256(fault_path);fault=json.loads(fault_path.read_text())
assert len(report['cases'])==10 and sum(r['passed'] for r in report['cases'])==4
rows=[]
for root,doc in ((a.report_root,report),(a.disconnect_root,fault)):
 for row in doc['cases']:
  kind=row['case'].split('-',1)[0];source=a.source_root/kind/'design.dsn';target=root/row['case']/'design.dsn'
  value={'report':str(root/'report.json'),'case':row['case'],'originalAcceptancePassed':row['passed'],'sourceUnchanged':sha256(source)==row['sourceBefore'],'remainingOwnedProcesses':row['process']['remainingOwnedProcesses'],'saved':row['receipt']['saved'],'targetSha256':sha256(target)}
  assert value['sourceUnchanged'] and value['remainingOwnedProcesses']==0
  if row['receipt']['saved']:
   value['savedOutputHashMatches']=value['targetSha256']==row['outputSha256'];assert value['savedOutputHashMatches']
  else:
   value['unsavedCopyUnchanged']=value['targetSha256']==row['sourceBefore'];assert value['unsavedCopyUnchanged']
  rows.append(value)
assert sha256(report_path)==before and sha256(fault_path)==fault_before
write_json(a.report_root/'integrity-audit.json',{'integrityPassed':True,'originalReportUnchanged':True,'originalNativeAcceptancePassed':report['passed'],'originalDisconnectAcceptancePassed':fault['passed'],'reportSha256':before,'disconnectReportSha256':fault_before,'cases':rows,'scope':'file integrity and owned process exit only; does not reaccept failed electrical/pose gates'})
print(json.dumps({'integrityPassed':True,'originalNativeAcceptancePassed':report['passed'],'acceptedCases':sum(r['passed'] for r in report['cases']),'totalNativeCases':len(report['cases']),'disconnectCases':len(fault['cases'])}))
