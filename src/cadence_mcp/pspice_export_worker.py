"""Fixed internal serializer subprocess, with no native DAT write or client code."""
import argparse
import json
import shutil
from pathlib import Path
from .core import sha256, write_json
from .pspice_export_format import render_data, MAX_BYTES


def main():
    parser = argparse.ArgumentParser()
    for key in ('table', 'source', 'directory'):
        parser.add_argument('--' + key, type=Path, required=True)
    for key in ('table-sha', 'source-sha'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--format', choices=('csv', 'json'), required=True)
    args = parser.parse_args()
    if args.table.stat().st_size > MAX_BYTES or args.source.stat().st_size > MAX_BYTES:
        raise ValueError('Input bound')
    if sha256(args.table) != args.table_sha or sha256(args.source) != args.source_sha:
        raise ValueError('Input changed')
    table = json.loads(args.table.read_text(encoding='utf-8'))
    raw = render_data(table, args.format)
    copied = args.directory / 'source.dat'
    with args.source.open('rb') as source, copied.open('xb') as target:
        shutil.copyfileobj(source, target)
    if sha256(copied) != args.source_sha or sha256(args.source) != args.source_sha or sha256(args.table) != args.table_sha:
        raise ValueError('Input changed during copy')
    target = args.directory / ('samples.' + args.format)
    with target.open('xb') as stream:
        stream.write(raw)
    write_json(args.directory / 'receipt.json', {'saved': True, 'format': args.format,
               'rowCount': len(table['samples']), 'dataSha256': sha256(target)})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
