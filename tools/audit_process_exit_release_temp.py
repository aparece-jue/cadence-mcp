"""Observe signaled process handles and immediate owned-directory release after job drain."""
import argparse,ctypes,json,os,sys,threading,time
from ctypes import wintypes as w
from pathlib import Path
from cadence_mcp.process_tree import run_owned_process
p=argparse.ArgumentParser();p.add_argument('--output-root',type=Path,required=True);p.add_argument('--count',type=int,default=60);a=p.parse_args()
root=a.output_root.resolve();root.mkdir(exist_ok=False);python=getattr(sys,'_base_executable',sys.executable)
api=ctypes.WinDLL('kernel32',use_last_error=True);api.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];api.OpenProcess.restype=w.HANDLE
api.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];api.WaitForSingleObject.restype=w.DWORD
api.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];api.GetExitCodeProcess.restype=w.BOOL
api.CloseHandle.argtypes=[w.HANDLE];api.CloseHandle.restype=w.BOOL
def status(pid):
 if not pid:return {'pid':pid,'state':'not_recorded'}
 handle=api.OpenProcess(0x101000,False,pid)
 if not handle:return {'pid':pid,'openError':ctypes.get_last_error()}
 try:
  wait=api.WaitForSingleObject(handle,0);code=w.DWORD();api.GetExitCodeProcess(handle,ctypes.byref(code))
  return {'pid':pid,'waitResult':wait,'exitCode':code.value}
 finally:api.CloseHandle(handle)
rows=[]
for index in range(a.count):
 directory=root/str(index);directory.mkdir();assert directory.resolve().is_relative_to(root)
 cancel=threading.Event();timer=None;mode='cancel' if index%2 else 'timeout'
 if mode=='cancel':timer=threading.Timer(0.3,cancel.set);timer.start()
 code="import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);Path('child.pid').write_text(str(p.pid));time.sleep(30)"
 process=run_owned_process([python,'-c',code],directory,os.environ.copy(),0.7,cancel=cancel if mode=='cancel' else None)
 if timer:timer.cancel();timer.join()
 child=int((directory/'child.pid').read_text()) if (directory/'child.pid').exists() else None
 row={'index':index,'mode':mode,'process':process,'rootStatus':status(process['pid']),'childStatus':status(child)}
 if (directory/'child.pid').exists():(directory/'child.pid').unlink()
 started=time.monotonic();attempts=[]
 for delay in (0,0.001,0.005,0.02,0.1,0.5):
  if delay:time.sleep(delay)
  try:directory.rmdir();attempts.append({'released':True,'afterSeconds':time.monotonic()-started});break
  except OSError as error:
   attempts.append({'released':False,'winError':error.winerror,'afterSeconds':time.monotonic()-started,
                    'rootStatus':status(process['pid']),'childStatus':status(child)})
 row['directoryRelease']=attempts;rows.append(row)
 (root/'report.json').write_text(json.dumps({'complete':False,'rows':rows},indent=2),encoding='utf-8')
report={'complete':True,'cases':len(rows),'immediateReleaseFailures':sum(not r['directoryRelease'][0]['released'] for r in rows),
 'unsignaledRootAfterReturn':sum(r['rootStatus'].get('waitResult')==258 for r in rows),
 'unsignaledChildAfterReturn':sum(r['childStatus'].get('waitResult')==258 for r in rows),'rows':rows}
(root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='rows'}))

