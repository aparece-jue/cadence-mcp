"""Audit all preserved native nominal-library inputs; execution refusal stays a failure."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import sha256
from cadence_mcp.pspice_runs import execution_preflight
p=argparse.ArgumentParser();p.add_argument('--mcp-root',type=Path,required=True);p.add_argument('--workspace-root',type=Path,required=True);a=p.parse_args();root=a.workspace_root.resolve();root.mkdir(exist_ok=False);job=a.mcp_root.resolve();run=json.loads((job/'report.json').read_text(encoding='utf-8'));directory=job/'work'/run['prepared']['simulationId'];manifest=json.loads((directory/'input-manifest.json').read_text(encoding='utf-8'));assert manifest['fileCount']==215 and manifest['inputEncoding']=='preserve-bytes' and manifest['inputBudget']=='extended';rows=[];refused=[];opaque=0
for f in manifest['files']:
 src=Path(f['sourcePath']);original=directory/f['originalRelativePath'];prepared=directory/f['relativePath'];assert sha256(src)==sha256(original)==f['sourceSha256'];assert sha256(prepared)==f['preparedSha256'];raw=original.read_bytes();text=raw.decode('utf-8-sig',errors='surrogateescape');lines=text.splitlines(keepends=True)
 for ref in f['references']:
  old=lines[ref['line']-1];ending='\r\n' if old.endswith('\r\n') else '\n' if old.endswith('\n') else '\r' if old.endswith('\r') else '';lines[ref['line']-1]='.'+ref['directive']+' "'+(directory/ref['targetRelativePath']).as_posix()+'"'+ending
 expected=''.join(lines).encode('utf-8',errors='surrogateescape');expected=(b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+expected;assert expected==prepared.read_bytes();opaque+=f['opaqueByteCount'];rows.append({'relativePath':f['relativePath'],'sha256':sha256(prepared),'sourceSha256':sha256(src),'references':len(f['references'])})
 try:execution_preflight(prepared.read_bytes().decode('utf-8-sig',errors='surrogateescape'))
 except Exception as e:refused.append({'relativePath':f['relativePath'],'code':getattr(e,'code',None)})
result={'passed':True,'scope':'Complete215-file prepared byte and source provenance audit only; not engine acceptance','filesChecked':len(rows),'opaqueBytesPreserved':opaque,'executionAccepted':False,'executionRefusedFiles':refused,'sourceUnchanged':True,'originalMcpRunPassed':run['passed'],'files':rows};assert refused and not run['passed'];(root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='files'}))
