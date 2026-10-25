"""Read-only Win32 preflight for GUI writes. Never dismisses or operates a window."""
import ctypes as c
from ctypes import wintypes as w
from .core import CadenceError


def require_write_ready(pid):
    user=c.WinDLL('user32',use_last_error=True)
    user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
    user.GetWindow.argtypes=[w.HWND,w.UINT];user.GetWindow.restype=w.HWND
    user.IsWindowVisible.argtypes=[w.HWND];user.IsWindowEnabled.argtypes=[w.HWND]
    windows=[]
    callback_type=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    def inspect(hwnd,param):
        actual=w.DWORD();user.GetWindowThreadProcessId(hwnd,c.byref(actual))
        if actual.value==pid and user.IsWindowVisible(hwnd) and not user.GetWindow(hwnd,4):
            windows.append(bool(user.IsWindowEnabled(hwnd)))
        return True
    callback=callback_type(inspect)
    user.EnumWindows.argtypes=[callback_type,w.LPARAM]
    if not user.EnumWindows(callback,0) or not windows:
        raise CadenceError('gui_state_unknown','Cannot confirm an enabled Capture main window before writing.')
    if not all(windows):raise CadenceError('bridge_busy','Capture has a disabled main window, usually a modal dialog; resolve it before writing.')
