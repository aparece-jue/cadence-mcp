"""Apply strengthened typed partition verifier to frozen native evidence, no replay."""
import argparse,json
from pathlib import Path
from cadence_mcp.hierarchy_semantics import verify_reused_context,native_partition_rows
from cadence_mcp.core import sha256
p=argparse.ArgumentParser();p.add_argument('--evidence-root',type=Path,required=True);a=p.parse_args();r=a.evidence_root.resolve(strict=True)
files=[r/'before.json',r/'after.json',r/'report.json'];hashes={f.name:sha256(f) for f in files};before=json.loads(files[0].read_text());after=json.loads(files[1].read_text());result={'passed':False,'mutationReplayed':False}
try:
 result['checks']=verify_reused_context(native_partition_rows(before['pins']),native_partition_rows(after['pins']),'halfadd_A','halfadd_C',{'VCC','GND'});result['passed']=True
except Exception as e:result['error']=str(e)
result['evidenceUnchanged']=all(sha256(r/n)==h for n,h in hashes.items());result['passed'] &= result['evidenceUnchanged'];result['hashes']=hashes
(r/'typed-partition-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
