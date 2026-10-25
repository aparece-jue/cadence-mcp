import ctypes,os,sys,tempfile,threading,unittest
from ctypes import wintypes as w
from pathlib import Path
from cadence_mcp.process_tree import run_owned_process

@unittest.skipUnless(os.name=='nt','Windows process exit signals')
class ExitSignalTests(unittest.TestCase):
    def assert_stopped(self,pid):
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];api.OpenProcess.restype=w.HANDLE
        api.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];api.WaitForSingleObject.restype=w.DWORD
        api.CloseHandle.argtypes=[w.HANDLE]
        handle=api.OpenProcess(0x00100000,False,pid)
        if not handle:self.assertEqual(ctypes.get_last_error(),87)
        else:
            try:self.assertEqual(api.WaitForSingleObject(handle,0),0)
            finally:api.CloseHandle(handle)
    def test_cancel_and_timeout_release_owned_directory_before_return(self):
        python=getattr(sys,'_base_executable',sys.executable)
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ('cancel','timeout'):
                directory=Path(tmp)/mode;directory.mkdir();cancel=threading.Event();timer=None
                if mode=='cancel':timer=threading.Timer(0.3,cancel.set);timer.start()
                code="import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);Path('child.pid').write_text(str(p.pid));time.sleep(30)"
                try:result=run_owned_process([python,'-c',code],directory,os.environ.copy(),0.7,cancel=cancel if mode=='cancel' else None)
                finally:
                    if timer:timer.cancel();timer.join()
                self.assertEqual(result['state'],'cancelled' if mode=='cancel' else 'timeout')
                self.assertTrue(result['rootExitSignalConfirmed']);self.assertTrue(result['observedProcessExitSignalsConfirmed'])
                self.assertGreaterEqual(result['observedOwnedProcessCount'],2)
                child=int((directory/'child.pid').read_text());self.assert_stopped(result['pid']);self.assert_stopped(child)
                (directory/'child.pid').unlink();directory.rmdir() # No delay/retry or ignored cleanup error.
    def test_nested_early_exiting_wrappers_preserve_last_descendant_and_release_directory(self):
        python=getattr(sys,'_base_executable',sys.executable)
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'nested';directory.mkdir()
            grandchild="from pathlib import Path;import time;time.sleep(0.25);Path('done').write_text('done')"
            child=f"import subprocess,sys;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c',{grandchild!r}]);Path('last.pid').write_text(str(p.pid))"
            root=f"import subprocess,sys;subprocess.Popen([sys.executable,'-c',{child!r}])"
            result=run_owned_process([python,'-c',root],directory,os.environ.copy(),5)
            self.assertEqual(result['state'],'exited');self.assertGreaterEqual(result['totalOwnedProcesses'],3)
            self.assertTrue(result['observedProcessExitSignalsConfirmed']);self.assert_stopped(result['pid'])
            self.assert_stopped(int((directory/'last.pid').read_text()));self.assertEqual((directory/'done').read_text(),'done')
            (directory/'last.pid').unlink();(directory/'done').unlink();directory.rmdir()
