"""Strict native receipt interpretation, independent of forwarder exit codes."""
import re
from .core import CadenceError


def decode_receipt(raw, nonce, pid):
    if (not isinstance(nonce, str) or not re.fullmatch('[a-f0-9]{32}', nonce) or type(pid) is not int or not 0 < pid < 2**32
            or not isinstance(raw, dict) or set(raw) != {'jobId', 'pid', 'invocationReturned', 'phase', 'nativeReturn', 'error', 'logs'}
            or raw['jobId'] != nonce or type(raw['pid']) is not int or raw['pid'] != pid
            or type(raw['invocationReturned']) is not bool or raw['phase'] not in ('load', 'generate', 'returned')
            or not isinstance(raw['nativeReturn'], str) or len(raw['nativeReturn']) > 128
            or not isinstance(raw['error'], str) or len(raw['error']) > 2048):
        raise CadenceError('invalid_native_receipt', 'Native netlist receipt does not match its exact job and Capture process.', 'verify')
    logs = raw['logs']
    if not isinstance(logs, list) or len(logs) != 4:
        raise CadenceError('invalid_native_receipt', 'Expected four bounded native log categories.', 'verify')
    expected = ['errors', 'warnings', 'session', 'netlist']
    for row, category in zip(logs, expected):
        if (not isinstance(row, dict) or set(row) != {'category', 'readable', 'lines'} or row['category'] != category
                or type(row['readable']) is not bool or not isinstance(row['lines'], list) or len(row['lines']) > 1000
                or any(not isinstance(line, str) or len(line) > 4096 for line in row['lines'])):
            raise CadenceError('invalid_native_receipt', 'Invalid native diagnostic shape, identity or bound.', 'verify')
    if not raw['invocationReturned'] or raw['phase'] != 'returned' or raw['nativeReturn'] != '1' or raw['error']:
        raise CadenceError('native_netlist_failed', 'Capture did not acknowledge successful native netlist generation; retain its receipt without replay.', 'verify')
    if not all(row['readable'] for row in logs):
        raise CadenceError('native_log_unavailable', 'A native diagnostic category was not completely read; success remains unproven.', 'verify')
    if logs[0]['lines']:
        raise CadenceError('native_netlist_failed', 'Native netlist error log is nonempty; no successful input artifact is certified.', 'verify')
    return {'jobId': nonce, 'pid': pid, 'nativeInvocationReturned': True,
            'nativeReturnVerified': True, 'errorLogEmpty': True,
            'warningCount': len(logs[1]['lines']), 'completionBasis': 'pid_nonce_bound_host_receipt',
            'forwarderExitIsCompletionProof': False}
