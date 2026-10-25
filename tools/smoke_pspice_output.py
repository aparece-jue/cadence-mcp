"""Verify OUT import against two installed official samples; does not run the solver."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from cadence_mcp.core import sha256

parser = argparse.ArgumentParser()
parser.add_argument('--install-root', type=Path, required=True)
parser.add_argument('--workspace-root', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
install = args.install_root.resolve(strict=True)
directory = args.workspace_root.resolve()
directory.mkdir(exist_ok=False)
paths = [install / 'share/orcad/tutorial/tutorial-PSpiceFiles/SCHEMATIC1/TRAN/Tran.out',
         install / 'share/orcad/examples/PSpice/TI/DRV8837/DRV8837-PSpiceFiles/SCHEMATIC1/trans/trans.out']

async def main():
    env = os.environ.copy()
    env['PYTHONPATH'] = str(repo / 'src')
    params = StdioServerParameters(command=sys.executable, args=['-m', 'cadence_mcp.server',
        '--install-root', str(install), '--workspace-root', str(directory / 'work'),
        '--read-root', str(install / 'share/orcad')], env=env)
    report = {'createdAt': datetime.now(timezone.utc).isoformat(), 'passed': False, 'cases': [],
              'scope': 'imported official OUT parser; not a current solver run'}
    try:
        async with Client(params, mode='legacy', read_timeout_seconds=30) as client:
            tools = (await client.list_tools()).tools
            (directory / 'tools-list.json').write_text(json.dumps([t.model_dump(mode='json', by_alias=True) for t in tools], indent=2), encoding='utf-8')
            report['toolCount'] = len(tools)
            tool = next(t for t in tools if t.name == 'pspice_inspect_output')
            Draft202012Validator.check_schema(tool.input_schema)
            Draft202012Validator.check_schema(tool.output_schema)
            for path in paths:
                before = sha256(path)
                result = await client.call_tool(tool.name, {'sourceOutput': str(path)})
                assert not result.is_error, result.content
                Draft202012Validator(tool.output_schema).validate(result.structured_content)
                row = result.structured_content['data']
                assert row['reportedVersions'] == ['17.4.0 (Nov 2018)']
                assert len(row['jobConcludedLines']) == 1 and not row['hasErrorDiagnostics']
                assert not row['solverSuccessVerified'] and not row['jobAssociationVerified']
                assert sha256(path) == before == row['sourceFingerprint']
                if path == paths[0]:
                    values = {v['node']: v['value'] for v in row['biasVoltages']}
                    assert values['5V'] == 4.050e-12 and values['3V3'] == 751.3e-6
                    assert values['OUT1'] == 751.3e-6 and values['OUT2'] == 0
                    assert 'IN9' not in values  # Digital block is outside the analog voltage table.
                else:
                    assert not row['biasVoltages']  # No table in this official OUT.
                report['cases'].append({'source': str(path), 'hashBefore': before, 'hashAfter': sha256(path),
                                        'passed': True, 'result': row})
            report['passed'] = True
    finally:
        (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'toolCount': report['toolCount'], 'cases': len(report['cases']), 'report': str(directory / 'report.json')}))
asyncio.run(main())
