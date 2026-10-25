"""Host-only trusted loader; never accepts a Tcl program from MCP."""
import argparse,json
from pathlib import Path
from cadence_mcp.gui_loader import load
from cadence_mcp.core import CadenceError
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--reload',action='store_true')
    parser.add_argument('--wait-seconds',type=int,choices=range(1,61),default=30,metavar='1..60')
    args=parser.parse_args()
    try:print(json.dumps(load(args.binding,args.reload,args.wait_seconds),ensure_ascii=False))
    except CadenceError as error:
        print(json.dumps({'status':'failed','code':error.code,'message':str(error)},ensure_ascii=False));raise SystemExit(1)
