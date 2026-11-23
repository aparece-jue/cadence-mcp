"""Compare native Boolean DBProps and fixed setters on isolated OLB copies."""
import argparse
import json
from pathlib import Path
import shutil
from cadence_mcp.core import Config, sha256, write_json
from cadence_mcp.environment import ADAPTERS, process_env
from cadence_mcp.process_tree import run_owned_process

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("install-root","source","output"):
        p.add_argument("--"+key,type=Path,required=True)
    args=p.parse_args()
    source=args.source.resolve(strict=True)
    if not source.is_file() or source.suffix.lower()!=".olb":
        p.error("source must be an existing OLB file")
    root=args.output.resolve()
    root.mkdir(parents=True,exist_ok=False)
    before=sha256(source)
    config=Config(args.install_root,root/"work",(source.parent,),45)
    report={"sourceSha256":before,"cases":[],"writeAcceptancePassed":False}
    for mode in ("setter","savepart","savesymbol","savepackage","typed"):
        directory=root/mode
        directory.mkdir()
        target=directory/"library.olb"
        shutil.copyfile(source,target)
        row={"mode":mode,"steps":[]}
        report["cases"].append(row)
        for label,operation in (("before","read"),("write",mode),("reopen","read")):
            out=directory/(label+".json")
            cmd=[args.install_root/"tcltk/bin/tclsh.exe",Path(__file__).with_suffix(".tcl"),
                 args.install_root,target,operation,out,ADAPTERS/"json.tcl"]
            result=run_owned_process(cmd,directory,process_env(config),45)
            step={"label":label,"process":result}
            row["steps"].append(step)
            if out.exists():
                step["result"]=json.loads(out.read_text(encoding="utf-8"))
            if result["returnCode"]!=0:
                break
        if len(row["steps"])==3 and all("result" in step for step in row["steps"]):
            original=row["steps"][0]["result"]["rows"]
            writes=row["steps"][1]["result"]["rows"]
            reopened=row["steps"][2]["result"]["rows"]
            row["immediateMatches"]=all(w["after"]==1-b["before"] for b,w in zip(original,writes))
            row["reopenMatches"]=all(a["before"]==1-b["before"] for b,a in zip(original,reopened))
            row["nativeBooleanTypesPreserved"]=all(a["nativeType"]==b["nativeType"]==3 for b,a in zip(original,reopened))
        print(mode,row.get("immediateMatches"),row.get("reopenMatches"),flush=True)
    report["sourceUnchanged"]=before==sha256(source)
    report["diagnosticCompleted"]=report["sourceUnchanged"] and all(
        len(row["steps"])==3 and all(
            "result" in step and step["process"]["state"]=="exited"
            and step["process"]["returnCode"]==0
            and step["process"]["remainingOwnedProcesses"]==0
            and len(step["result"]["rows"])==3
            for step in row["steps"]) for row in report["cases"])
    report["writeAcceptancePassed"]=report["sourceUnchanged"] and all(row.get("reopenMatches",False) for row in report["cases"])
    write_json(root/"report.json",report)
    return 0 if report["diagnosticCompleted"] else 1

if __name__=="__main__":
    raise SystemExit(main())
