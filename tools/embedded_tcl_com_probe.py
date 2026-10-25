"""Private diagnostic: initialize COM on the thread hosting configured native Tcl."""
import argparse,ctypes,os,sys
from pathlib import Path
p=argparse.ArgumentParser()
for k in ('install-root','script','source','target','receipt'):p.add_argument('--'+k,type=Path,required=True)
p.add_argument('--com',choices=('none','sta','mta'),required=True)
a=p.parse_args();root=a.install_root.resolve(strict=True)
handles=[os.add_dll_directory(str(root/'tcltk/bin')),os.add_dll_directory(str(root/'tools/bin'))]
os.environ['TCL_LIBRARY']=str(root/'tcltk/lib/tcl8.6')
ole=ctypes.OleDLL('ole32');ole.CoInitializeEx.argtypes=[ctypes.c_void_p,ctypes.c_ulong];ole.CoInitializeEx.restype=ctypes.c_long
initialized=False
if a.com!='none':
 result=ole.CoInitializeEx(None,2 if a.com=='sta' else 0);initialized=result in (0,1)
 if not initialized:raise RuntimeError('COM initialization did not succeed')
tcl=ctypes.CDLL(str(root/'tcltk/bin/tcl86.dll'))
tcl.Tcl_FindExecutable.argtypes=[ctypes.c_char_p];tcl.Tcl_FindExecutable(str(root/'tcltk/bin/tclsh.exe').encode('utf-8'))
tcl.Tcl_CreateInterp.restype=ctypes.c_void_p;interp=tcl.Tcl_CreateInterp()
tcl.Tcl_Init.argtypes=[ctypes.c_void_p];tcl.Tcl_Init.restype=ctypes.c_int
tcl.Tcl_GetStringResult.argtypes=[ctypes.c_void_p];tcl.Tcl_GetStringResult.restype=ctypes.c_char_p
tcl.Tcl_SetVar.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];tcl.Tcl_SetVar.restype=ctypes.c_char_p
tcl.Tcl_Merge.argtypes=[ctypes.c_int,ctypes.POINTER(ctypes.c_char_p)];tcl.Tcl_Merge.restype=ctypes.c_void_p
tcl.Tcl_Free.argtypes=[ctypes.c_void_p];tcl.Tcl_EvalFile.argtypes=[ctypes.c_void_p,ctypes.c_char_p];tcl.Tcl_EvalFile.restype=ctypes.c_int
tcl.Tcl_DeleteInterp.argtypes=[ctypes.c_void_p]
try:
 if tcl.Tcl_Init(interp):raise RuntimeError(tcl.Tcl_GetStringResult(interp).decode('utf-8','replace'))
 args=[str(root),str(a.source.resolve()),str(a.target.resolve()),'legacy',str(a.receipt.resolve())];encoded=[v.encode('utf-8') for v in args];vector=(ctypes.c_char_p*len(encoded))(*encoded);merged=tcl.Tcl_Merge(len(encoded),vector)
 try:tcl.Tcl_SetVar(interp,b'argv',ctypes.cast(merged,ctypes.c_char_p),1)
 finally:tcl.Tcl_Free(merged)
 tcl.Tcl_SetVar(interp,b'argc',str(len(args)).encode(),1)
 code=tcl.Tcl_EvalFile(interp,str(a.script.resolve(strict=True)).encode('utf-8'))
 if code:raise RuntimeError(tcl.Tcl_GetStringResult(interp).decode('utf-8','replace'))
finally:
 tcl.Tcl_DeleteInterp(interp)
 if initialized:ole.CoUninitialize()

