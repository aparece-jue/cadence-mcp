"""Synthetic GDI print test; does not load or render a Capture design."""
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime
from pathlib import Path
import json
import sys

def main():
    destination = Path(sys.argv[1]).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    printer = 'Microsoft Print to PDF'
    spool = c.WinDLL('winspool.drv', use_last_error=True)
    gdi = c.WinDLL('gdi32', use_last_error=True)
    spool.OpenPrinterW.argtypes = [w.LPWSTR, c.POINTER(w.HANDLE), c.c_void_p]
    spool.OpenPrinterW.restype = w.BOOL
    spool.ClosePrinter.argtypes = [w.HANDLE]
    spool.DocumentPropertiesW.argtypes = [w.HWND,w.HANDLE,w.LPWSTR,c.c_void_p,c.c_void_p,w.DWORD]
    spool.DocumentPropertiesW.restype = w.LONG
    gdi.CreateDCW.argtypes = [w.LPCWSTR,w.LPCWSTR,w.LPCWSTR,c.c_void_p]
    gdi.CreateDCW.restype = w.HDC
    class DocInfo(c.Structure):
        _fields_ = [('cbSize',c.c_int),('name',w.LPCWSTR),('output',w.LPCWSTR),('datatype',w.LPCWSTR),('flags',w.DWORD)]
    gdi.StartDocW.argtypes = [w.HDC,c.POINTER(DocInfo)]
    gdi.StartDocW.restype = c.c_int
    for name in ['StartPage','EndPage','EndDoc','AbortDoc','DeleteDC']:
        getattr(gdi,name).argtypes = [w.HDC]
        getattr(gdi,name).restype = c.c_int
    gdi.TextOutW.argtypes = [w.HDC,c.c_int,c.c_int,w.LPCWSTR,c.c_int]
    gdi.TextOutW.restype = w.BOOL
    gdi.GetDeviceCaps.argtypes = [w.HDC,c.c_int]
    gdi.GetDeviceCaps.restype = c.c_int
    handle = w.HANDLE()
    if not spool.OpenPrinterW(printer,c.byref(handle),None):
        raise c.WinError(c.get_last_error())
    dc = None
    started = False
    try:
        size = spool.DocumentPropertiesW(None,handle,printer,None,None,0)
        if size < 220:
            raise RuntimeError(f'Invalid DEVMODE size: {size}')
        mode = c.create_string_buffer(size)
        if spool.DocumentPropertiesW(None,handle,printer,mode,None,2) != 1:
            raise RuntimeError('Cannot obtain driver settings')
        # DEVMODEW public layout: dmFields offset 72, dmOrientation offset 76.
        c.c_uint32.from_buffer(mode,72).value |= 1
        c.c_short.from_buffer(mode,76).value = 2
        if spool.DocumentPropertiesW(None,handle,printer,mode,mode,10) != 1:
            raise RuntimeError('Driver rejected per-job landscape settings')
        if c.c_short.from_buffer(mode,76).value != 2:
            raise RuntimeError('Driver did not retain landscape')
        dc = gdi.CreateDCW('WINSPOOL',printer,None,mode)
        if not dc:
            raise c.WinError(c.get_last_error())
        width,height = (gdi.GetDeviceCaps(dc,key) for key in [110,111])
        if width <= height:
            raise RuntimeError(f'Device is not landscape: {width}x{height}')
        info = DocInfo(c.sizeof(DocInfo),'Cadence MCP synthetic printer test',str(destination),None,0)
        job = gdi.StartDocW(dc,c.byref(info))
        if job <= 0:
            raise c.WinError(c.get_last_error())
        started = True
        if gdi.StartPage(dc) <= 0:
            raise RuntimeError('StartPage failed')
        for row,line in enumerate(['SYNTHETIC DRIVER TEST - NOT A CAPTURE SCHEMATIC','CARRY_OUT U1A X_BAR','Microsoft Print to PDF / per-job landscape / explicit output path']):
            if not gdi.TextOutW(dc,300,300+row*180,line,len(line)):
                raise RuntimeError('TextOutW failed')
        if gdi.EndPage(dc) <= 0 or gdi.EndDoc(dc) <= 0:
            raise RuntimeError('Print completion failed')
        started = False
        print(json.dumps({'printer':printer,'orientation':'landscape','physicalPixels':[width,height],'jobId':job,'destination':str(destination),'captureRendered':False,'globalDefaultsChanged':False}))
    finally:
        if dc:
            if started:
                gdi.AbortDoc(dc)
            gdi.DeleteDC(dc)
        spool.ClosePrinter(handle)

if __name__ == '__main__':
    main()
