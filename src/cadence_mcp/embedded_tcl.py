"""Fixed installed-Tcl graphics adapters with a same-process DIB hash callback.

Internal subprocess entry point only. No user script, eval or native handle API.
Native faults remain isolated in the worker process just as with tclsh.
"""
import argparse
import ctypes
import os
from pathlib import Path
import sys

from .bitmap_dib import DibDigests

READERS = frozenset({'inspect_part_vectors.tcl', 'inspect_page_vectors.tcl', 'inspect_library_vectors.tcl', 'inspect_library_create.tcl', 'inspect_placed_view.tcl'})
SCRIPTS = READERS | frozenset({'edit_place.tcl', 'edit_multiunit_place.tcl', 'edit_library_vector.tcl'})


def command(install_root, script, args):
    if script not in SCRIPTS:
        raise ValueError('Unsupported embedded reader')
    return [sys.executable, '-m', 'cadence_mcp.embedded_tcl',
            '--install-root', str(install_root), '--adapter', script, '--', *map(str, args)]


def run(install, script, args):
    if script not in SCRIPTS or os.name != 'nt' or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise ValueError('Unsupported embedded runtime')
    install = Path(install).resolve(strict=True)
    paths = [install / 'tcltk/bin', install / 'tools/bin']
    for path in [*paths, install / 'tcltk/bin/tcl86.dll', install / 'tcltk/bin/tclsh.exe']:
        if not path.resolve(strict=True).is_relative_to(install):
            raise ValueError('Runtime path outside configured installation')
    directories = [os.add_dll_directory(str(path)) for path in paths]
    tcl = ctypes.CDLL(str(install / 'tcltk/bin/tcl86.dll'))
    ptr = ctypes.c_void_p
    signatures = {
        'Tcl_FindExecutable': ([ctypes.c_char_p], None), 'Tcl_CreateInterp': ([], ptr),
        'Tcl_Init': ([ptr], ctypes.c_int), 'Tcl_DeleteInterp': ([ptr], None),
        'Tcl_EvalFile': ([ptr, ctypes.c_char_p], ctypes.c_int),
        'Tcl_Eval': ([ptr, ctypes.c_char_p], ctypes.c_int),
        'Tcl_GetString': ([ptr], ctypes.c_char_p),
        'Tcl_GetStringResult': ([ptr], ctypes.c_char_p),
        'Tcl_NewListObj': ([ctypes.c_int, ptr], ptr),
        'Tcl_NewStringObj': ([ctypes.c_char_p, ctypes.c_int], ptr),
        'Tcl_NewIntObj': ([ctypes.c_int], ptr),
        'Tcl_ListObjAppendElement': ([ptr, ptr, ptr], ctypes.c_int),
        'Tcl_SetVar2Ex': ([ptr, ctypes.c_char_p, ctypes.c_char_p, ptr, ctypes.c_int], ptr),
        'Tcl_SetObjResult': ([ptr, ptr], None),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(tcl, name)
        function.argtypes, function.restype = arguments, result
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    for name, result in [('GlobalSize', ctypes.c_size_t), ('GlobalLock', ptr), ('GlobalUnlock', ctypes.c_int)]:
        function = getattr(kernel, name)
        function.argtypes, function.restype = [ptr], result
    digests = DibDigests(kernel)
    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ptr, ptr, ctypes.c_int, ctypes.POINTER(ptr))

    @callback_type
    def digest_callback(client_data, interp, count, objects):
        try:
            if count != 3:
                raise ValueError('Invalid DIB callback arguments')
            token = tcl.Tcl_GetString(objects[1]).decode('ascii')
            size_text = tcl.Tcl_GetString(objects[2]).decode('ascii')
            if not size_text.isdecimal() or len(size_text) > 9:
                raise ValueError('Invalid DIB size')
            value = digests.digest(token, int(size_text))
            code = 0
        except Exception:
            value, code = 'bitmap_byte_identity_unavailable', 1
        encoded = value.encode('ascii')
        tcl.Tcl_SetObjResult(interp, tcl.Tcl_NewStringObj(encoded, len(encoded)))
        return code

    tcl.Tcl_CreateObjCommand.argtypes = [ptr, ctypes.c_char_p, callback_type, ptr, ptr]
    tcl.Tcl_CreateObjCommand.restype = ptr
    tcl.Tcl_FindExecutable(str(install / 'tcltk/bin/tclsh.exe').encode('utf-8'))
    interp = tcl.Tcl_CreateInterp()
    if not interp:
        raise RuntimeError('Cannot create installed Tcl interpreter')
    try:
        def require(code):
            if code:
                # Fixed adapters emit their own sanitized diagnostics. No opaque native token output.
                raise RuntimeError('Fixed installed Tcl reader failed')
        require(tcl.Tcl_Init(interp))
        require(tcl.Tcl_Eval(interp, b'namespace eval cmcp {}'))
        if not tcl.Tcl_CreateObjCommand(interp, b'cmcp::bitmapDigest', digest_callback, None, None):
            raise RuntimeError('Cannot register DIB hash callback')
        argv = tcl.Tcl_NewListObj(0, None)
        for value in [str(install), *args]:
            encoded = value.encode('utf-8')
            require(tcl.Tcl_ListObjAppendElement(interp, argv, tcl.Tcl_NewStringObj(encoded, len(encoded))))
        if not tcl.Tcl_SetVar2Ex(interp, b'argv', None, argv, 1):
            raise RuntimeError('Cannot set fixed reader arguments')
        if not tcl.Tcl_SetVar2Ex(interp, b'argc', None, tcl.Tcl_NewIntObj(len(args) + 1), 1):
            raise RuntimeError('Cannot set fixed reader argument count')
        adapter = Path(__file__).parent / 'adapters' / script
        require(tcl.Tcl_EvalFile(interp, str(adapter).encode('utf-8')))
    finally:
        tcl.Tcl_DeleteInterp(interp)
        for directory in directories:
            directory.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install-root', required=True)
    parser.add_argument('--adapter', choices=sorted(SCRIPTS), required=True)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    values = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    try:
        run(args.install_root, args.adapter, values)
    except Exception:
        print('CADENCE_DBO_ERROR: fixed graphics worker failed', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
