import json,os,subprocess,tempfile,unittest
from pathlib import Path
from cadence_mcp.core import CadenceError
from cadence_mcp.environment import ADAPTERS
from cadence_mcp.capture_pspice_receipt import decode_receipt

class NativeNetlistAdapterTests(unittest.TestCase):
 def harness(self,mode):
  tcl=os.environ.get('CADENCE_TEST_TCLSH')
  if not tcl or not Path(tcl).is_file():self.skipTest('Configured Tcl unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);script=root/'test.tcl';output=root/'receipt.json';summary=root/'summary.json';marker=root/'entered';target=root/'new.net'
   code='''source {%s}
source {%s}
namespace eval ::cmcpBridge {proc activeDesign {} {return [file normalize ACTIVE]}}
set mode {%s};set calls 0
proc OrTclNetlist_sCreatePSpiceNetList {args} {global calls mode;incr calls;if {$mode eq "native0"} {return 0};return 1}
proc DboTclHelper_sMakeStdVector {} {return vector}
foreach name {OrTclNetlist_sGetErrorLog OrTclNetlist_sGetWarningLog OrTclNetlist_sGetSessionLog OrTclNetlist_sGetNetlistLog} {
 proc $name {vector} {global mode;if {$mode eq "getterFailure"} {error unreadable};return {}}
}
proc DboTclHelper_sGetVectorSize {vector} {global mode;if {$mode eq "oversizeLine"} {return 1};if {$mode eq "largeTotal"} {return 33};return 0}
proc DboTclHelper_sGetConstCharPtrFromVector {vector index} {global mode;if {$mode eq "oversizeLine"} {return [string repeat A 4097]};return [string repeat A 4096]}
set expected [pid];if {$mode eq "wrongPid"} {incr expected}
set arguments [list $expected ACTIVE DESIGN {%s} {%s} {%s} aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa DLL]
set caught [catch {::cmcpNativeNetlist::run {*}$arguments} message]
if {$mode eq "repeat"} {set caught [catch {::cmcpNativeNetlist::run {*}$arguments} message]}
set f [open {%s} w];puts $f [cmcp::obj pid [pid] calls $calls caught $caught message [cmcp::q $message]];close $f
'''%((ADAPTERS/'json.tcl').as_posix(),(ADAPTERS/'capture_pspice_netlist_job.tcl').as_posix(),mode,target.as_posix(),output.as_posix(),marker.as_posix(),summary.as_posix())
   script.write_text(code,encoding='utf-8');p=subprocess.run([tcl,str(script)],cwd=root,capture_output=True,timeout=10);self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'));info=json.loads(summary.read_text());raw=json.loads(output.read_text()) if output.exists() else None;return info,raw,marker.exists()
 def test_wrong_process_refuses_before_marker_or_native_call(self):
  info,raw,entered=self.harness('wrongPid');self.assertEqual(info['message'],'wrong_process');self.assertEqual(info['calls'],0);self.assertFalse(entered);self.assertIsNone(raw)
 def test_same_nonce_replay_is_actually_acknowledged_as_refused(self):
  info,raw,entered=self.harness('repeat');self.assertEqual(info['calls'],1);self.assertEqual(info['caught'],1);self.assertEqual(info['message'],'already_dispatched');self.assertTrue(entered);decode_receipt(raw,'a'*32,info['pid'])
 def test_native_zero_does_not_become_successful_receipt(self):
  info,raw,entered=self.harness('native0')
  with self.assertRaises(CadenceError) as c:decode_receipt(raw,'a'*32,info['pid'])
  self.assertEqual(c.exception.code,'native_netlist_failed')
 def test_unreadable_oversize_and_total_log_limit_never_count_as_empty_success(self):
  for mode in ['getterFailure','oversizeLine','largeTotal']:
   info,raw,entered=self.harness(mode)
   with self.subTest(mode=mode),self.assertRaises(CadenceError) as c:decode_receipt(raw,'a'*32,info['pid'])
   self.assertEqual(c.exception.code,'native_log_unavailable')
if __name__=='__main__':unittest.main()
