"""Private DAT10 header comparison against the unchanged original two-block oracle."""
import argparse
import json
from pathlib import Path

from cadence_mcp.core import Config, sha256
from cadence_mcp.environment import ADAPTERS, process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.pspice_dat import PSpiceDat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('install-root', 'expected-path', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(exist_ok=False)
    oracle = args.expected_path.resolve(strict=True)
    before = sha256(oracle)
    expected = json.loads(oracle.read_text(encoding='utf8'))
    assert expected['blocks'] == [
        dict(index=0, frequency=[10, 20, 30], gainReal=[10, 20, 30], gainImaginary=[-1, -2, -3]),
        dict(index=1, frequency=[10, 20, 30], gainReal=[110, 120, 130], gainImaginary=[-2, -3, -4])]
    original = ADAPTERS / 'fixture_complex_dat_v9.tcl'
    source_hash = sha256(original)
    source = original.read_text(encoding='utf8')
    config = Config(args.install_root, root / 'work', (root,), 45)
    report = dict(scope='synthetic writer only; not simulation or public DAT writer',
                  originalOracleSha256=before, originalFixtureScriptSha256=source_hash, cases=[])
    for mode in ('dat9_control', 'dat10_secondary_empty', 'dat10_secondary_step'):
        directory = root / mode
        directory.mkdir()
        code = source
        if mode != 'dat9_control':
            code = code.replace('step create $target 9', 'step create $target 10')
            # The installed QuickView writer copies SecondaryParamName, omitted by
            # the original synthetic fixture and previous full_header experiment.
            secondary = '{} ' if mode.endswith('_empty') else 'MCP_SWEEP '
            code = code.replace('  step addDataName Frequency 0;',
                '  foreach {key value} {CircuitSubtitle MCP_SUB SimulationTime 12:00:00 Date 11/24/2026 SecondaryParamName '
                + secondary + '} {step setHeaderData $key $value}\n  step addDataName Frequency 0;')
        script = directory / 'writer.tcl'
        script.write_text(code, encoding='utf8')
        row = dict(mode=mode, passed=False)
        report['cases'].append(row)
        try:
            row['process'] = run_owned_process(
                [args.install_root / 'tcltk/bin/tclsh.exe', script, args.install_root, directory],
                directory, process_env(config), 45)
            row['lastNativeSteps'] = (directory / 'fixture.log').read_text(encoding='utf8').splitlines()[-5:]
            assert row['process']['remainingOwnedProcesses'] == 0
            assert row['process']['returnCode'] == 0, 'native_writer_failed'
            data = PSpiceDat(config)
            opened = data.open(str(directory / 'complex.dat'))
            ident = opened['datId']
            try:
                blocks = data.query(ident, 'block', limit=1000)['items']
                assert len(blocks) == 2
                observed = []
                for want in expected['blocks']:
                    block = blocks[want['index']]
                    assert block['complex'] and block['rowCount'] == 3
                    freq = data.samples(ident, want['index'], 'Frequency', 0, 1000)['items']
                    gain = data.samples(ident, want['index'], 'Gain', 0, 1000)['items']
                    assert [v['real'] for v in freq] == want['frequency']
                    assert [v['imaginary'] for v in freq] == [0, 0, 0]
                    assert [v['real'] for v in gain] == want['gainReal']
                    assert [v['imaginary'] for v in gain] == want['gainImaginary']
                    observed.append(dict(block=block, frequency=freq, gain=gain))
                row.update(passed=True, observed=observed, datSha256=sha256(directory / 'complex.dat'))
            finally:
                data.close(ident)
        except Exception as error:
            row.update(error=str(error), errorType=type(error).__name__)
        report['inputsUnchanged'] = sha256(oracle) == before and sha256(original) == source_hash
        (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
        print(json.dumps(row), flush=True)
    assert report['inputsUnchanged']
    assert report['cases'][0]['passed'], 'DAT9 control must remain valid'


if __name__ == '__main__':
    main()
