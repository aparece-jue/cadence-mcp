"""Create an isolated DSN copy and an explicit opt-in marker, never modify source."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from cadence_mcp.core import sha256

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    args=parser.parse_args()
    source=args.source.resolve(strict=True)
    if source.suffix.lower()!='.dsn':raise ValueError('Expected a DSN source')
    before=sha256(source)
    args.output_root.mkdir(parents=True,exist_ok=True)
    directory=Path(tempfile.mkdtemp(prefix='gui-write-fixture-',dir=args.output_root)).resolve()
    target=directory/'write_fixture.dsn'
    shutil.copyfile(source,target)
    assert before==sha256(source)==sha256(target)
    (directory/'write-fixture.json').write_text(json.dumps({'kind':'cadence-mcp-write-fixture-v1',
        'source':str(source),'design':str(target),'sourceFingerprint':before},indent=2),encoding='utf-8')
    print(target)
