"""Durable text export with a frozen table and independently reopened native DAT."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from .core import CadenceError, Config, checked_path, new_id, sha256, write_json
from .isolated_jobs import IsolatedJobs, digest
from .environment import process_env
from .process_tree import run_owned_process
from .pspice_dat import PSpiceDat, unit_for
from .pspice_export_format import render_data, validate_table, MAX_BYTES

ORIGIN_KEYS = ('provenance', 'jobAssociationVerified', 'solverSuccessVerified',
               'producedByPlan', 'runManifestSha256', 'numericalAcceptanceVerified')


def collect_table(data, ident, block, requested, offset, count, origin):
    session, selected, canonical, values = data._all_samples(ident, block, requested)
    if canonical == selected['axis']:
        axis = values
    else:
        _, _, _, axis = data._all_samples(ident, block, selected['axis'])
    if len(axis) != len(values):
        raise CadenceError('export_axis_mismatch', 'Axis and trace row counts differ.')
    if type(offset) is not int or type(count) is not int or not 0 <= offset < len(values) or not 1 <= count <= 100000 or offset + count > len(values):
        raise CadenceError('invalid_export_range', 'Choose a nonempty range within the native trace rows.')
    trace = next(t for t in session['traces'][block] if t['name'] == canonical)
    metadata = {'schemaVersion': '1.0', 'sourceDatSha256': session['manifest']['revision'],
                'block': block, 'blockMetadata': selected, 'traceMetadata': trace,
                'requestedTrace': requested, 'canonicalTrace': canonical, 'axis': selected['axis'],
                'axisUnits': unit_for(selected['axis'], selected['axis']),
                'valueUnits': unit_for(canonical, selected['axis']), 'offset': offset,
                'rowCount': count, 'totalRows': len(values), 'sourceProvenance': origin,
                'exportedRowsNumericalOracleVerified': False}
    rows = [{'index': i, 'axisReal': axis[i]['real'], 'axisImaginary': axis[i]['imaginary'],
             'real': values[i]['real'], 'imaginary': values[i]['imaginary']}
            for i in range(offset, offset + count)]
    data._session(ident)
    return validate_table({'metadata': metadata, 'samples': rows})


class PSpiceExports(IsolatedJobs):
    kind = 'pspice_dat_export'

    def __init__(self, config, data):
        super().__init__(config)
        self.data = data

    def plan(self, ident, block, trace, format='csv', offset=0, count=None):
        if format not in ('csv', 'json') or not isinstance(trace, str) or not trace or len(trace) > 512:
            raise CadenceError('invalid_export', 'Choose CSV/JSON and one exact bound analog trace.')
        with self.data.lock:
            session = self.data._session(ident)
            selected = self.data._block(session, block)
            if type(offset) is not int:
                raise CadenceError('invalid_export_range', 'Export offset must be an integer.')
            if count is None:
                count = selected['rowCount'] - offset
            origin = {k: session['manifest'].get(k) for k in ORIGIN_KEYS}
            table = collect_table(self.data, ident, block, trace, offset, count, origin)
            render_data(table, format)
            source = session['directory'] / 'imported.dat'
            manifest = session['directory'] / 'manifest.json'
            if manifest.stat().st_size > 65536 or json.loads(manifest.read_text(encoding='utf-8')) != session['manifest']:
                raise CadenceError('target_changed', 'DAT provenance differs from its session.')
            directory = self.config.workspace_root / new_id('export-input')
            directory.mkdir()
            directory = checked_path(str(directory), (self.config.workspace_root,))
            frozen = directory / 'table.json'
            write_json(frozen, table)
            if frozen.stat().st_size > MAX_BYTES:
                raise CadenceError('export_limit', 'Frozen export table exceeds32MiB.')
            self.data._session(ident)
            payload = {'sourceDat': str(source), 'sourceFingerprint': session['manifest']['revision'],
                       'sourceManifest': str(manifest), 'sourceManifestHash': sha256(manifest),
                       'tablePath': str(frozen), 'tableSha256': sha256(frozen),
                       'tableDigest': digest(table), 'metadata': table['metadata'], 'format': format}
            return self.create_plan(payload)

    def preview(self, p):
        return {'operation': 'export_dat_samples', 'format': p['format'], **p['metadata']}

    def preflight(self, p):
        if p['format'] not in ('csv', 'json'):
            raise CadenceError('invalid_export', 'Unsupported export format.')
        for key, checksum in [('sourceDat', 'sourceFingerprint'), ('sourceManifest', 'sourceManifestHash'), ('tablePath', 'tableSha256')]:
            path = checked_path(p[key], (self.config.workspace_root,))
            if path.stat().st_size > MAX_BYTES or sha256(path) != p[checksum]:
                raise CadenceError('target_changed', 'Frozen export source or declaration changed.')
        table = json.loads(Path(p['tablePath']).read_text(encoding='utf-8'))
        validate_table(table)
        manifest = json.loads(Path(p['sourceManifest']).read_text(encoding='utf-8'))
        if (digest(table) != p['tableDigest'] or table['metadata'] != p['metadata']
            or p['metadata']['sourceDatSha256'] != p['sourceFingerprint']
            or manifest['revision'] != p['sourceFingerprint']
            or {k: manifest.get(k) for k in ORIGIN_KEYS} != p['metadata']['sourceProvenance']):
            raise CadenceError('invalid_plan', 'Frozen export identity differs from its plan.')

    def native_command(self, d, p):
        return [sys.executable, '-m', 'cadence_mcp.pspice_export_worker',
                '--table', p['tablePath'], '--table-sha', p['tableSha256'],
                '--source', p['sourceDat'], '--source-sha', p['sourceFingerprint'],
                '--format', p['format'], '--directory', str(d)]

    def execute(self, d, p, cancel, on_started):
        self.preflight(p)
        return run_owned_process(self.native_command(d, p), d, process_env(self.config),
                                 self.config.timeout_seconds, cancel=cancel, on_started=on_started)

    def worker_error(self, d, p, process):
        return CadenceError('export_worker_failed', 'Fixed export serializer did not finish successfully.', 'worker')

    def verify(self, d, p, native_completed):
        self.preflight(p)
        source = checked_path(str(d / 'source.dat'), (d,))
        datafile = checked_path(str(d / ('samples.' + p['format'])), (d,))
        if max(source.stat().st_size, datafile.stat().st_size) > MAX_BYTES or sha256(source) != p['sourceFingerprint']:
            raise CadenceError('target_changed', 'Export source snapshot changed.')
        before = sha256(datafile)
        meta = p['metadata']
        reader = PSpiceDat(Config(self.config.install_root, self.config.workspace_root, (d,), self.config.timeout_seconds))
        ident = reader.open(str(source))['datId']
        try:
            table = collect_table(reader, ident, meta['block'], meta['requestedTrace'],
                                  meta['offset'], meta['rowCount'], meta['sourceProvenance'])
        finally:
            reader.close(ident)
        if digest(table) != p['tableDigest'] or datafile.read_bytes() != render_data(table, p['format']):
            raise CadenceError('export_mismatch', 'Export differs from independently reopened native values.', 'verify')
        if native_completed:
            receipt = checked_path(str(d / 'receipt.json'), (d,))
            if receipt.stat().st_size > 4096 or json.loads(receipt.read_text(encoding='utf-8')) != {'saved': True, 'format': p['format'], 'rowCount': meta['rowCount'], 'dataSha256': before}:
                raise CadenceError('invalid_worker_result', 'Export receipt differs from the verified file.')
        self.preflight(p)
        if sha256(source) != p['sourceFingerprint'] or sha256(datafile) != before:
            raise CadenceError('target_changed', 'Export changed during verification.')
        manifest = {'schemaVersion': '1.0', 'format': p['format'], 'metadata': meta,
                    'dataFile': datafile.name, 'dataSha256': before, 'dataBytes': datafile.stat().st_size,
                    'validationScope': 'stored_sample_identity_not_new_electrical_oracle', 'nativeReopenVerified': True}
        target = d / 'export-manifest.json'
        if target.exists():
            target = checked_path(str(target), (d,))
            if target.stat().st_size > 65536 or json.loads(target.read_text(encoding='utf-8')) != manifest:
                raise CadenceError('export_mismatch', 'Existing export manifest differs; do not overwrite.')
        else:
            write_json(target, manifest)
        ident = d.name.removeprefix('plan-')
        artifact = {'artifactId': 'export-' + ident, 'kind': 'pspice_numeric_export',
                    'workspaceRelativePath': target.name, 'sha256': sha256(target), 'size': target.stat().st_size,
                    'producedByJob': ident, 'sourceFingerprint': p['sourceFingerprint'], 'sourceKind': 'file_fingerprint',
                    'createdAt': datetime.now(timezone.utc).isoformat(), 'validationState': 'validated'}
        files = [{'workspaceRelativePath': path.name, 'sha256': sha256(path), 'size': path.stat().st_size}
                 for path in (source, datafile, target)]
        return {'planId': ident, 'state': 'verified' if native_completed else 'verified_recovered',
                'artifact': artifact, 'files': files, 'format': p['format'], 'rowCount': meta['rowCount'],
                'workerCompletionVerified': native_completed, 'nativeReopenVerified': True,
                'sampleIdentityVerified': True, 'sourceProvenance': meta['sourceProvenance'], 'sourceModified': False,
                'outputWorkspaceRelativePath': d.relative_to(self.config.workspace_root).as_posix(),
                'notChecked': ['digital_logic_samples', 'undocumented_native_units', 'new_numerical_oracle', 'circuit_safety']}

    def _verified_result(self, d, row):
        result = super()._verified_result(d, row)
        expected = {'source.dat', 'samples.' + result['format'], 'export-manifest.json'}
        if len(result['files']) != 3 or {f['workspaceRelativePath'] for f in result['files']} != expected:
            raise CadenceError('invalid_worker_result', 'Unexpected export file set.')
        for record in result['files']:
            path = checked_path(str(d / record['workspaceRelativePath']), (d,))
            if path.stat().st_size != record['size'] or sha256(path) != record['sha256']:
                raise CadenceError('target_changed', 'Previously verified export bytes changed.')
        return result
