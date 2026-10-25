"""Private prototype: embed installed Tcl and copy only a validated HGLOBAL DIB in-process."""
import argparse,ctypes,hashlib,json,os,re,sys
from ctypes import wintypes as w
from pathlib import Path
from cadence_mcp.core import sha256
from cadence_mcp.environment import ADAPTERS
p=argparse.ArgumentParser()
for k in ('install-root','library','expected-bmp','output'):p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();install=a.install_root.resolve(strict=True);source=a.library.resolve(strict=True);before=sha256(source)
report={'passed':False,'scope':'owned same-process official GetDib/GlobalLock copy; private fixed fixture only'}
interp=None;tcl=None
try:
 paths=[os.add_dll_directory(str(install/'tcltk/bin')),os.add_dll_directory(str(install/'tools/bin'))]
 tcl=ctypes.CDLL(str(install/'tcltk/bin/tcl86.dll'))
 signatures={
  'Tcl_FindExecutable':([ctypes.c_char_p],None),'Tcl_CreateInterp':([],ctypes.c_void_p),
  'Tcl_Init':([ctypes.c_void_p],ctypes.c_int),'Tcl_DeleteInterp':([ctypes.c_void_p],None),
  'Tcl_GetStringResult':([ctypes.c_void_p],ctypes.c_char_p),
  'Tcl_EvalFile':([ctypes.c_void_p,ctypes.c_char_p],ctypes.c_int),
  'Tcl_Eval':([ctypes.c_void_p,ctypes.c_char_p],ctypes.c_int),
  'Tcl_NewListObj':([ctypes.c_int,ctypes.c_void_p],ctypes.c_void_p),
  'Tcl_NewStringObj':([ctypes.c_char_p,ctypes.c_int],ctypes.c_void_p),
  'Tcl_NewIntObj':([ctypes.c_int],ctypes.c_void_p),
  'Tcl_ListObjAppendElement':([ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p],ctypes.c_int),
  'Tcl_SetVar2Ex':([ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_int],ctypes.c_void_p)}
 for name,(arguments,result) in signatures.items():getattr(tcl,name).argtypes=arguments;getattr(tcl,name).restype=result
 tcl.Tcl_FindExecutable(str(install/'tcltk/bin/tclsh.exe').encode('utf-8'));interp=tcl.Tcl_CreateInterp();assert interp
 def require(code):
  if code:raise RuntimeError(tcl.Tcl_GetStringResult(interp).decode('utf-8',errors='replace'))
 require(tcl.Tcl_Init(interp));argv=tcl.Tcl_NewListObj(0,None)
 for value in (str(install),str(source)):
  encoded=value.encode('utf-8');require(tcl.Tcl_ListObjAppendElement(interp,argv,tcl.Tcl_NewStringObj(encoded,len(encoded))))
 assert tcl.Tcl_SetVar2Ex(interp,b'argv',None,argv,1)
 assert tcl.Tcl_SetVar2Ex(interp,b'argc',None,tcl.Tcl_NewIntObj(2),1)
 require(tcl.Tcl_EvalFile(interp,str(ADAPTERS/'embedded_bitmap_data.tcl').encode('utf-8')))
 result=json.loads(tcl.Tcl_GetStringResult(interp).decode('utf-8'));report['dibSize']=result['dibSize']
 token=result['dibHandle'];report['nativeHandleType']=token.split('_p_')[-1] if '_p_' in token else 'integer'
 if re.fullmatch(r'[0-9]+',token):handle=int(token)
 elif re.fullmatch(r'0x[0-9a-fA-F]+',token):handle=int(token,16)
 else:
  match=re.fullmatch(r'_([0-9a-fA-F]+)_p_[A-Za-z0-9_]+',token)
  if not match:raise ValueError('Unsupported native HGLOBAL representation: '+token)
  packed=bytes.fromhex(match[1])
  if len(packed)!=ctypes.sizeof(ctypes.c_void_p):raise ValueError('Unsupported native pointer width')
  handle=int.from_bytes(packed,sys.byteorder);report['handleEncoding']='SWIG_native_byte_sequence'
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 kernel.GlobalSize.argtypes=[w.HGLOBAL];kernel.GlobalSize.restype=ctypes.c_size_t
 kernel.GlobalLock.argtypes=[w.HGLOBAL];kernel.GlobalLock.restype=ctypes.c_void_p
 kernel.GlobalUnlock.argtypes=[w.HGLOBAL];kernel.GlobalUnlock.restype=w.BOOL
 ctypes.set_last_error(0)
 capacity=kernel.GlobalSize(handle);report['globalCapacity']=capacity;report['globalSizeError']=ctypes.get_last_error()
 if report['nativeHandleType']=='HGLOBAL' and capacity==ctypes.sizeof(ctypes.c_void_p) and result['dibSize']>capacity:
  wrapper=kernel.GlobalLock(handle)
  if not wrapper:raise OSError(ctypes.get_last_error(),'Cannot lock native HGLOBAL value wrapper')
  try:handle=int.from_bytes(ctypes.string_at(wrapper,capacity),sys.byteorder)
  finally:kernel.GlobalUnlock(int.from_bytes(packed,sys.byteorder))
  capacity=kernel.GlobalSize(handle);report['nativeValueWrapperBytes']=ctypes.sizeof(ctypes.c_void_p);report['globalCapacity']=capacity
 if not 0<result['dibSize']<=capacity<=32*1024*1024:raise ValueError('DIB/global allocation bounds differ')
 address=kernel.GlobalLock(handle)
 if not address:raise OSError(ctypes.get_last_error(),'GlobalLock failed')
 try:blob=ctypes.string_at(address,result['dibSize'])
 finally:kernel.GlobalUnlock(handle)
 expected=a.expected_bmp.read_bytes()[14:];report['dibSha256']=hashlib.sha256(blob).hexdigest();report['expectedDibSha256']=hashlib.sha256(expected).hexdigest()
 report['bytesMatchIndependentBmpDib']=blob==expected
 report['sourceUnchanged']=sha256(source)==before
 report['passed']=report['bytesMatchIndependentBmpDib'] and report['sourceUnchanged']
except BaseException as e:
 import traceback
 report.update(error=str(e),traceback=traceback.format_exc())
finally:
 if interp and tcl:
  tcl.Tcl_Eval(interp,b'if {[info commands cmcp::closeBitmapData] ne ""} {cmcp::closeBitmapData}')
  tcl.Tcl_DeleteInterp(interp)
a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)


