"""Deterministic numeric export with fixed CSV headers and explicit metadata."""
import csv
import io
import json
import math

COLUMNS = ('index', 'axisReal', 'axisImaginary', 'real', 'imaginary')
MAX_BYTES = 32 * 1024 * 1024


def validate_table(table):
    if not isinstance(table, dict) or set(table) != {'metadata', 'samples'} or not isinstance(table['metadata'], dict):
        raise ValueError('Invalid export table')
    rows, meta = table['samples'], table['metadata']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100000 or type(meta.get('rowCount')) is not int or meta['rowCount'] != len(rows):
        raise ValueError('Invalid export row count')
    if type(meta.get('offset')) is not int or meta['offset'] < 0:
        raise ValueError('Invalid export offset')
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != set(COLUMNS) or type(row['index']) is not int or row['index'] != meta['offset'] + index:
            raise ValueError('Invalid export row identity')
        for name in COLUMNS[1:]:
            value = row[name]
            if value is None and name in ('axisImaginary', 'imaginary'):
                continue
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('Invalid finite export value')
    return table


def render_data(table, format):
    validate_table(table)
    if format == 'json':
        raw = (json.dumps(table, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    elif format == 'csv':
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(COLUMNS)
        for row in table['samples']:
            writer.writerow([row[name] for name in COLUMNS])
        raw = stream.getvalue().encode('utf-8')
    else:
        raise ValueError('Unsupported export format')
    if len(raw) > MAX_BYTES:
        raise ValueError('Export exceeds byte limit')
    return raw
