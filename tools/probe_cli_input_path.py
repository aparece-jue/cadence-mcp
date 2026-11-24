"""Owned native CLI path comparison using the original fixed 2.5 V fixture."""
import argparse
import json
import shutil
from pathlib import Path

from cadence_mcp.core import Config, sha256
from cadence_mcp.environment import process_env
from cadence_mcp.process_tree import run_owned_process
from cadence_mcp.pspice_dat import PSpiceDat

SOURCE_SHA256 = '7f4adbbd2dab3a05b0c4e6f762259fc10030c9c986ec474ac9c51e2a2f32b81d'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'install-root', 'output', 'short-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    assert source.suffix.lower() == '.cir' and sha256(source) == SOURCE_SHA256
    root, short = args.output.resolve(), args.short_root.resolve()
    assert root != short and root not in short.parents and short not in root.parents
    assert not root.exists() and not short.exists()
    root.mkdir()
    report = dict(sourceSha256=SOURCE_SHA256, licenseSelectionModified=False,
                  numericalOracle=dict(trace='V(2)', real=2.5, absoluteTolerance=1e-6), cases=[])
    long = root / ('context_' + 'a' * 60)
    for mode, directory, relative in (
            ('short_absolute', short, False),
            ('long_relative', long / 'relative', True),
            ('long_absolute', long / 'absolute', False)):
        directory.mkdir(parents=True, exist_ok=False)
        target = directory / 'input.cir'
        shutil.copyfile(source, target)
        config = Config(args.install_root, directory / 'work', (directory,), 20)
        row = dict(mode=mode, inputPathLength=len(str(target)), passed=False)
        report['cases'].append(row)
        try:
            row['process'] = run_owned_process(
                [args.install_root / 'tools/bin/psp_cmd.exe', '/r', 'input.cir' if relative else target],
                directory, process_env(config), 20)
            row['outProduced'] = (directory / 'input.out').is_file()
            row['datProduced'] = (directory / 'input.dat').is_file()
            assert row['process']['returnCode'] == 0 and row['process']['remainingOwnedProcesses'] == 0
            assert row['outProduced'] and row['datProduced']
            text = (directory / 'input.out').read_text(encoding='cp1252')
            assert 'JOB CONCLUDED' in text and 'JOB STATISTICS SUMMARY' in text
            data = PSpiceDat(config)
            opened = data.open(str(directory / 'input.dat'))
            ident = opened['datId']
            try:
                values = data.samples(ident, 0, 'V(2)', 0, 10)['items']
                assert len(values) == 1 and abs(values[0]['real'] - 2.5) <= 1e-6
                row.update(passed=True, samples=values,
                           outSha256=sha256(directory / 'input.out'),
                           datSha256=sha256(directory / 'input.dat'))
            finally:
                data.close(ident)
        except Exception as error:
            row.update(error=str(error), errorType=type(error).__name__)
        row['inputUnchanged'] = sha256(target) == SOURCE_SHA256
        row['sourceUnchanged'] = sha256(source) == SOURCE_SHA256
        (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
        print(json.dumps(row), flush=True)
    assert all(row['inputUnchanged'] and row['sourceUnchanged'] for row in report['cases'])


if __name__ == '__main__':
    main()
