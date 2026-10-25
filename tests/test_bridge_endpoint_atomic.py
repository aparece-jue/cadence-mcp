"""Deterministic native observation at the exact endpoint write boundary."""
import json,os,secrets,subprocess,tempfile,time,unittest,uuid
from pathlib import Path
from cadence_mcp.core import sha256

@unittest.skipUnless(os.environ.get('CADENCE_TEST_TCLSH'),'Explicit native Tcl runtime required')
class AtomicEndpointTests(unittest.TestCase):
    def test_descriptor_is_not_visible_while_its_payload_is_being_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=Path(__file__).resolve().parents[1]
            script=(repo/'tests/bridge_harness.tcl').read_text(encoding='utf-8')
            observer='''
rename ::puts ::fixtureOriginalPuts
proc ::puts {args} {
    if {[string first {"host":"127.0.0.1"} [lindex $args end]]>=0} {
        set directory [file dirname $::configFile]
        set visible [expr {[file exists [file join $directory endpoint.json]] ? "true" : "false"}]
        set f [open [file join $directory publication-observation.json] {WRONLY CREAT EXCL}]
        try {::fixtureOriginalPuts $f [cmcp::obj visibleBeforePayloadWrite $visible]} finally {close $f}
    }
    uplevel 1 [list ::fixtureOriginalPuts {*}$args]
}
'''
            script=script.replace('source $adapter','source $adapter\n'+observer)
            fixture=root/'harness.tcl';fixture.write_text(script,encoding='utf-8')
            executable=Path(os.environ['CADENCE_TEST_TCLSH']);binding=root/'binding.json';design=root/'owned.dsn';design.write_bytes(b'fake owned design')
            process=subprocess.Popen([str(executable),str(fixture),str(binding),str(repo/'src/cadence_mcp/adapters/bridge.tcl')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                config={'protocol':1,'expectedPid':process.pid,'expectedDesign':str(design),'instanceId':uuid.uuid4().hex,'token':secrets.token_hex(32),'sourceFingerprint':sha256(design),'expectedExecutable':str(executable),'executableFingerprint':sha256(executable)}
                temporary=root/'binding.tmp';temporary.write_text(json.dumps(config),encoding='utf-8');temporary.replace(binding)
                end=time.monotonic()+5
                while not (root/'endpoint.json').exists():
                    if process.poll() is not None:self.fail(process.stderr.read().decode(errors='replace'))
                    if time.monotonic()>end:self.fail('Endpoint not published')
                    time.sleep(.01)
                observed=json.loads((root/'publication-observation.json').read_text())
                self.assertFalse(observed['visibleBeforePayloadWrite'])
                endpoint=json.loads((root/'endpoint.json').read_text())
                self.assertEqual(endpoint['pid'],process.pid);self.assertEqual(endpoint['instanceId'],config['instanceId'])
                self.assertFalse(list(root.glob('.endpoint-*.tmp')))
            finally:
                if process.poll() is None:process.terminate()
                process.communicate(timeout=5)
