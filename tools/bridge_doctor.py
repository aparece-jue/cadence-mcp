"""Read-only bridge diagnosis; no launch, write, retarget or retry."""
import argparse
import json
from pathlib import Path
from cadence_mcp.bridge_rpc import GuiBridgeManager,RpcConnection
from cadence_mcp.core import CadenceError

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding',type=Path,required=True)
    args=parser.parse_args()
    from cadence_mcp.bridge_diagnostics import diagnose
    row=diagnose(GuiBridgeManager((args.binding,)))
    print(json.dumps(row,ensure_ascii=False,indent=2))
    return 0 if row['status']=='ready' else 1

if __name__=='__main__':raise SystemExit(main())
