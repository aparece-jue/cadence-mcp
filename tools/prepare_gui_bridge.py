"""Prepare a user-private binding; run locally, never via an MCP tool."""
import argparse
import csv
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import uuid

from cadence_mcp.core import sha256
from cadence_mcp.bridge_rpc import process_image

def prepare(directory: Path, design: Path, pid: int, allow_property_write: bool = False) -> Path:
    if os.name != "nt":
        raise RuntimeError("Windows private ACL preparation is required")
    design=design.resolve(strict=True)
    if design.suffix.lower() != ".dsn" or pid <= 0:
        raise ValueError("Expected copied DSN and Capture PID")
    if allow_property_write:
        manifest=json.loads((design.parent/'write-fixture.json').read_text(encoding='utf-8'))
        if (manifest.get('kind')!='cadence-mcp-write-fixture-v1' or Path(manifest['design']).resolve()!=design
                or Path(manifest['source']).resolve()==design or manifest['sourceFingerprint']!=sha256(design)):
            raise ValueError('Write access requires an unchanged isolated fixture copy')
    directory.mkdir(parents=True, exist_ok=True)
    private=Path(tempfile.mkdtemp(prefix="gui-bridge-",dir=directory)).resolve()
    # Protect the directory before writing the capability token.
    who=subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],capture_output=True,text=True,check=True)
    sid=list(csv.reader(who.stdout.splitlines()))[-1][-1]
    if not sid.startswith("S-1-"):
        raise RuntimeError("Cannot resolve current user SID")
    subprocess.run(["icacls",str(private),"/inheritance:r","/grant:r",f"*{sid}:(OI)(CI)F"],
                   capture_output=True,check=True)
    executable=process_image(pid)
    if executable.name.lower() != "capture.exe":raise ValueError("PID does not identify Capture.exe")
    config=private/"binding.json"
    with config.open("x",encoding="utf-8") as stream:
        json.dump({"protocol":1,"token":secrets.token_hex(32),"instanceId":uuid.uuid4().hex,
                   "expectedPid":pid,"expectedDesign":str(design),"sourceFingerprint":sha256(design),"expectedExecutable":str(executable),"executableFingerprint":sha256(executable),"allowPropertyWrite":allow_property_write,"writeLeaseId":secrets.token_hex(32) if allow_property_write else None},stream)
    return config

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--private-root",type=Path,required=True)
    parser.add_argument("--copied-design",type=Path,required=True)
    parser.add_argument("--capture-pid",type=int,required=True)
    parser.add_argument("--allow-property-write", action="store_true")
    args=parser.parse_args()
    print(prepare(args.private_root,args.copied_design,args.capture_pid,args.allow_property_write))
