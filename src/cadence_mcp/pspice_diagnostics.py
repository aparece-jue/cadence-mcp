"""Conservative classifications from explicit native error lines, never elapsed time."""
import re
from .core import CadenceError

def category(code,message):
    normalized=(code or '').upper()
    if re.search(r'\bconvergence problem in\b|\bfailed to converge\b|\bconvergence failed\b',message,re.I):return 'nonconvergence'
    if re.search(r'\btime step (?:is )?too small\b',message,re.I):return 'time_step_failure'
    if normalized=='ORPSIM-15113' and re.search(r'\bmodel\b.*\bundefined\b',message,re.I):return 'missing_model'
    if normalized=='ORPSIM-15143' and re.search(r'\b(?:voltage source|inductor)\b.*\bloop\b',message,re.I):return 'topology_error'
    if re.search(r'\bunable to (?:check[ -]?out|obtain)\b.*\blicen[cs]e\b|\blicen[cs]e check[ -]?out failed\b|\blicen[cs]e (?:is )?not available\b',message,re.I):return 'license_unavailable'
    return 'unclassified'

def summary(diagnostics):
    failures=[r for r in diagnostics if r['severity'] in ('error','fatal')]
    return {'errorCategories':sorted({category(r['code'],r['message']) for r in failures}),
            'errorCount':len(failures),'warningCount':sum(r['severity']=='warning' for r in diagnostics),
            'basis':'explicit_native_error_lines','timeoutIsLicenseEvidence':False}

def failure_for_output(parsed,phase='verify'):
    if not parsed['hasErrorDiagnostics']:return None
    categories=summary(parsed['diagnostics'])['errorCategories']
    if 'license_unavailable' in categories:return CadenceError('pspice_license_unavailable','Native OUT explicitly reports a license checkout failure; inspect bound diagnostics.',phase)
    if 'nonconvergence' in categories or 'time_step_failure' in categories:return CadenceError('pspice_nonconvergence','Native OUT explicitly reports convergence or time-step failure; no successful result certified.',phase)
    return CadenceError('pspice_output_error','Native OUT reports an error; inspect bound diagnostics.',phase)
