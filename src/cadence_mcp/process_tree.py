"""Windows-only owned process tree with suspended creation and kill-on-close.

No shell. A child cannot run before being assigned to our private Job Object.
"""
import ctypes
from ctypes import wintypes as w
import os
import subprocess
import time

from .core import CadenceError


class STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR),
                ("lpTitle", w.LPWSTR), ("dwX", w.DWORD), ("dwY", w.DWORD),
                ("dwXSize", w.DWORD), ("dwYSize", w.DWORD), ("dwXCountChars", w.DWORD),
                ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD), ("dwFlags", w.DWORD),
                ("wShowWindow", w.WORD), ("cbReserved2", w.WORD), ("lpReserved2", ctypes.POINTER(w.BYTE)),
                ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


class BASIC_LIMIT(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount",
                "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


class ACCOUNTING(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in ("TotalUserTime", "TotalKernelTime",
                "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")] + [
                (name, w.DWORD) for name in ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]


def run_owned_process(argv, cwd, env, timeout_seconds, cancel=None, on_started=None):
    if os.name != "nt":
        raise CadenceError("capability_unavailable", "Owned process trees currently require Windows.")
    if not argv or not 0 < timeout_seconds <= 600:
        raise CadenceError("invalid_process_request", "Invalid bounded process request.")
    if cancel is not None and cancel.is_set():
        return {"state": "cancelled", "pid": None, "returnCode": None, "durationSeconds": 0,
                "remainingOwnedProcesses": 0, "totalOwnedProcesses": 0}
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    api.CreateJobObjectW.restype = w.HANDLE
    api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    api.SetInformationJobObject.restype = w.BOOL
    api.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
    api.QueryInformationJobObject.restype = w.BOOL
    api.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL,
                                  w.DWORD, ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION)]
    api.CreateProcessW.restype = w.BOOL
    api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    api.AssignProcessToJobObject.restype = w.BOOL
    api.ResumeThread.argtypes = [w.HANDLE]
    api.ResumeThread.restype = w.DWORD
    api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    api.WaitForSingleObject.restype = w.DWORD
    api.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    api.GetExitCodeProcess.restype = w.BOOL
    api.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    api.TerminateJobObject.restype = w.BOOL
    api.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    api.TerminateProcess.restype = w.BOOL
    api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    api.OpenProcess.restype = w.HANDLE
    api.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)]
    api.IsProcessInJob.restype = w.BOOL
    api.CloseHandle.argtypes = [w.HANDLE]
    api.CloseHandle.restype = w.BOOL

    def require(ok, phase):
        if not ok:
            raise CadenceError("process_control_failed", f"Windows process control failed during {phase} (error {ctypes.get_last_error()}).", "worker")

    job = api.CreateJobObjectW(None, None)
    require(job, "job creation")
    process = PROCESS_INFORMATION()
    assigned = False
    exit_signals_confirmed = False
    owned_handles = {}
    started = time.monotonic()

    def collect_owned_handles():
        # Membership can end before the process kernel object becomes signaled.
        # Retain observed descendant handles while they are still in our job.
        capacity = 64
        while True:
            storage = ctypes.create_string_buffer(8 + ctypes.sizeof(ctypes.c_size_t) * capacity)
            ok = api.QueryInformationJobObject(job, 3, storage, ctypes.sizeof(storage), None)
            if ok:
                count = w.DWORD.from_buffer(storage, 4).value
                if count > capacity:
                    raise CadenceError("process_control_failed", "Invalid owned process list.", "worker")
                break
            require(ctypes.get_last_error() == 234, "owned process list")
            capacity = max(capacity * 2, w.DWORD.from_buffer(storage).value)
            if capacity > 16384:
                raise CadenceError("process_tree_limit", "Owned process handle tracking exceeds its bound.", "worker")
        for index in range(count):
            pid = ctypes.c_size_t.from_buffer(storage, 8 + ctypes.sizeof(ctypes.c_size_t) * index).value
            if pid == process.dwProcessId or pid in owned_handles:
                continue
            if len(owned_handles) >= 16384:
                raise CadenceError("process_tree_limit", "Owned process handle tracking exceeds its bound.", "worker")
            handle = api.OpenProcess(0x00101000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
            if not handle:
                if ctypes.get_last_error() == 87:  # PID already gone.
                    continue
                require(False, "owned process handle")
            keep = False
            try:
                member = w.BOOL()
                require(api.IsProcessInJob(handle, job, ctypes.byref(member)), "owned process membership")
                if member.value:  # Exclude a recycled PID belonging to another job.
                    owned_handles[pid] = handle
                    keep = True
            finally:
                if not keep:
                    api.CloseHandle(handle)

    def wait_known_exit_signals(strict=True):
        deadline = time.monotonic() + 5
        for handle in [process.hProcess, *owned_handles.values()]:
            if not handle:
                continue
            milliseconds = max(0, int((deadline - time.monotonic()) * 1000))
            result = api.WaitForSingleObject(handle, milliseconds)
            if strict and result != 0:
                if result == 0xFFFFFFFF:
                    require(False, "process exit signal")
                raise CadenceError("process_termination_indeterminate", "An observed owned process has not signaled exit.", "worker")
    try:
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        require(api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)), "job limits")
        startup = STARTUPINFO()
        startup.cb = ctypes.sizeof(startup)
        startup.dwFlags = 0x00000001  # STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(value) for value in argv]))
        environment = ctypes.create_unicode_buffer("\x00".join(f"{key}={value}" for key, value in sorted(env.items(), key=lambda row: row[0].upper())) + "\x00\x00")
        # CREATE_SUSPENDED | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT
        require(api.CreateProcessW(str(argv[0]), command, None, None, False, 0x08000404,
                                  environment, str(cwd), ctypes.byref(startup), ctypes.byref(process)), "suspended process creation")
        require(api.AssignProcessToJobObject(job, process.hProcess), "job assignment")
        assigned = True
        if on_started is not None:
            on_started(process.dwProcessId)
        require(api.ResumeThread(process.hThread) != 0xFFFFFFFF, "process resume")
        state = "exited"
        while True:
            collect_owned_handles()
            accounting = ACCOUNTING()
            require(api.QueryInformationJobObject(job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None), "job accounting")
            if accounting.ActiveProcesses == 0:
                break
            if cancel is not None and cancel.is_set():
                state = "cancelled"
                break
            if time.monotonic() - started >= timeout_seconds:
                state = "timeout"
                break
            # If the wrapper exits early, still wait for its owned descendants.
            if api.WaitForSingleObject(process.hProcess, 50) == 0:
                time.sleep(0.05)
        if state != "exited":
            collect_owned_handles()
            require(api.TerminateJobObject(job, 0xE0000001), "owned tree termination")
            deadline = time.monotonic() + 5
            while True:
                collect_owned_handles()
                require(api.QueryInformationJobObject(job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None), "termination accounting")
                if accounting.ActiveProcesses == 0:
                    break
                if time.monotonic() > deadline:
                    raise CadenceError("process_termination_indeterminate", "Owned process termination has not been confirmed.", "worker")
                time.sleep(0.02)
        wait_known_exit_signals()
        exit_signals_confirmed = True
        exit_code = w.DWORD()
        require(api.GetExitCodeProcess(process.hProcess, ctypes.byref(exit_code)), "exit code")
        return {"state": state, "pid": process.dwProcessId, "returnCode": exit_code.value,
                "durationSeconds": round(time.monotonic() - started, 3),
                "remainingOwnedProcesses": accounting.ActiveProcesses,
                "totalOwnedProcesses": accounting.TotalProcesses,
                "rootExitSignalConfirmed": True,
                "observedProcessExitSignalsConfirmed": True,
                "observedOwnedProcessCount": 1 + len(owned_handles)}
    finally:
        # Callback/control failures also terminate before releasing retained handles.
        if not exit_signals_confirmed and process.hProcess:
            if assigned:
                api.TerminateJobObject(job, 0xE0000002)
                # KILL_ON_JOB_CLOSE remains the fallback if explicit termination failed.
                api.CloseHandle(job)
                job = None
            else:
                api.TerminateProcess(process.hProcess, 0xE0000002)
            wait_known_exit_signals(strict=False)
        if job:
            api.CloseHandle(job)
        for handle in owned_handles.values():
            api.CloseHandle(handle)
        if process.hThread:
            api.CloseHandle(process.hThread)
        if process.hProcess:
            api.CloseHandle(process.hProcess)
