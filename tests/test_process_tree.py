import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from cadence_mcp.process_tree import run_owned_process


@unittest.skipUnless(os.name == "nt", "Windows Job Object acceptance requires Windows")
class ProcessTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.python = getattr(sys, "_base_executable", sys.executable)

    def run_code(self, code, seconds=10, **kwargs):
        return run_owned_process([self.python, "-c", code], self.root, os.environ.copy(), seconds, **kwargs)

    def test_normal_exit_and_code_are_preserved(self):
        result = self.run_code("from pathlib import Path; Path('done.txt').write_text('done'); raise SystemExit(7)")
        self.assertEqual(result["state"], "exited")
        self.assertEqual(result["returnCode"], 7)
        self.assertEqual(result["remainingOwnedProcesses"], 0)
        self.assertEqual((self.root / "done.txt").read_text(), "done")

    def test_waits_for_descendant_after_wrapper_exits(self):
        child = "from pathlib import Path; import time; time.sleep(0.25); Path('child-done.txt').write_text('done')"
        code = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}])"
        result = self.run_code(code)
        self.assertTrue((self.root / "child-done.txt").exists())
        self.assertGreaterEqual(result["totalOwnedProcesses"], 2)
        self.assertEqual(result["remainingOwnedProcesses"], 0)

    def test_timeout_terminates_owned_descendant(self):
        child = "import time; time.sleep(30)"
        code = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
        result = self.run_code(code, seconds=0.7)
        self.assertEqual(result["state"], "timeout")
        self.assertGreaterEqual(result["totalOwnedProcesses"], 2)
        self.assertEqual(result["remainingOwnedProcesses"], 0)

    def test_cancel_and_precancel(self):
        cancel = threading.Event()
        timer = threading.Timer(0.3, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)
        result = self.run_code("import time; time.sleep(30)", cancel=cancel)
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(result["remainingOwnedProcesses"], 0)
        result = self.run_code("raise SystemExit('should never run')", cancel=cancel)
        self.assertIsNone(result["pid"])

    def test_failure_before_resume_closes_job_and_stops_suspended_process(self):
        pid = None
        def fail(value):
            nonlocal pid
            pid = value
            raise RuntimeError("pre-resume callback failed")
        with self.assertRaises(RuntimeError): self.run_code("from pathlib import Path; Path('unexpected').touch()", on_started=fail)
        self.assertFalse((self.root / "unexpected").exists())
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        api.OpenProcess.restype = w.HANDLE
        api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        api.WaitForSingleObject.restype = w.DWORD
        api.CloseHandle.argtypes = [w.HANDLE]
        handle = api.OpenProcess(0x00100000, False, pid)
        if handle:
            try: self.assertEqual(api.WaitForSingleObject(handle, 0), 0)
            finally: api.CloseHandle(handle)
        else:
            self.assertEqual(ctypes.get_last_error(), 87)

    def test_unrelated_process_is_not_terminated(self):
        unrelated = subprocess.Popen([self.python, "-c", "import time; time.sleep(30)"],
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            result = self.run_code("import time; time.sleep(30)", seconds=0.2)
            self.assertEqual(result["state"], "timeout")
            self.assertIsNone(unrelated.poll())
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=5)

    def test_repeated_runs_do_not_leak_kernel_handles(self):
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.GetCurrentProcess.restype = w.HANDLE
        api.GetProcessHandleCount.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        def count():
            value = w.DWORD()
            self.assertTrue(api.GetProcessHandleCount(api.GetCurrentProcess(), ctypes.byref(value)))
            return value.value
        self.run_code("pass")
        before = count()
        for _ in range(8):
            self.assertEqual(self.run_code("pass")["state"], "exited")
        self.assertLessEqual(count() - before, 2)

