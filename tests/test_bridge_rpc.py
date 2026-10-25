import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from cadence_mcp.bridge_rpc import GuiBridgeManager,RpcConnection,unique_object
from cadence_mcp.core import CadenceError,sha256

class ManagerTests(unittest.TestCase):
    def test_loss_invalidates_without_replay(self):
        manager=GuiBridgeManager()
        connection=RpcConnection(Path('unused'))
        manager.sessions['s']={'connection':connection,'generation':1,'instanceId':'i','pid':1}
        with patch.object(connection,'call',side_effect=CadenceError('bridge_unavailable','offline')) as call:
            with self.assertRaises(CadenceError):manager.query('s','status')
            self.assertEqual(call.call_count,1)
        with self.assertRaises(CadenceError):manager.query('s','status')

    def test_detach_disconnected_session_releases_local_cache(self):
        manager=GuiBridgeManager();connection=RpcConnection(Path('unused'))
        manager.sessions['s']={'connection':connection,'generation':1}
        with patch.object(connection,'call',side_effect=CadenceError('bridge_unavailable','offline')):
            result=manager.detach('s')
        self.assertTrue(result['detached']);self.assertFalse(result['remoteReleaseConfirmed'])
        self.assertNotIn('s',manager.sessions)

    def test_duplicate_response_fields_rejected(self):
        with self.assertRaises(ValueError):json.loads('{"pid":1,"pid":2}',object_pairs_hook=unique_object)

    def test_read_only_operation_allowlist(self):
        with self.assertRaises(CadenceError):GuiBridgeManager().query('missing','eval')

@unittest.skipUnless(os.environ.get('CADENCE_TEST_TCLSH'),'Explicit native Tcl test runtime not configured')
class NativeRpcTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.design=self.root/'测试副本.dsn';self.design.write_bytes(b'fake data, no real DSN')
        self.config_path=self.root/'binding.json'
        executable=Path(os.environ['CADENCE_TEST_TCLSH']).resolve()
        repo=Path(__file__).resolve().parents[1]
        self.process=subprocess.Popen([str(executable),str(repo/'tests/bridge_harness.tcl'),str(self.config_path),
            str(repo/'src/cadence_mcp/adapters/bridge.tcl')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(self.stop)
        self.config={'protocol':1,'expectedPid':self.process.pid,'expectedDesign':str(self.design),
                     'instanceId':uuid.uuid4().hex,'token':secrets.token_hex(32),'sourceFingerprint':sha256(self.design),
                     'expectedExecutable':str(executable),'executableFingerprint':sha256(executable)}
        self.config_path.write_text(json.dumps(self.config),encoding='utf-8')
        end=time.monotonic()+5
        while not (self.root/'endpoint.json').exists():
            if self.process.poll() is not None:self.fail(self.process.stderr.read().decode(errors='replace'))
            if time.monotonic()>end:self.fail('Native bridge did not start')
            time.sleep(0.02)
        self.connection=RpcConnection(self.config_path)

    def stop(self):
        if self.process.poll() is None:self.process.terminate()
        self.process.communicate(timeout=5)

    def request(self,**changes):
        endpoint=json.loads((self.root/'endpoint.json').read_text())
        request={'protocol':2,'requestId':uuid.uuid4().hex,'token':self.config['token'],
            'instanceId':self.config['instanceId'],'expectedDesign':str(self.design),'operation':'hello',
            'params':{},'deadlineMs':int(time.time()*1000)+4000,**changes}
        with socket.create_connection(('127.0.0.1',endpoint['port']),timeout=3) as channel:
            channel.settimeout(4)
            channel.sendall(json.dumps(request).encode()+b'\n')
            reply=channel.recv(16385)
        return json.loads(reply) if reply else None

    def change(self,path=None,dirty=0):
        target=self.root/'control.json';temp=self.root/'control.tmp'
        temp.write_text(json.dumps({'path':str(path or self.design),'dirty':dirty}),encoding='utf-8');temp.replace(target)
        time.sleep(0.35)

    def test_auth_deadline_and_instance(self):
        self.assertIsNone(self.request(token='bad'))
        self.assertIsNone(self.request(instanceId='wrong'))
        self.assertEqual(self.request(deadlineMs=int(time.time()*1000)-1)['code'],'deadline_exceeded')
        reply=self.connection.call('hello',{})
        self.assertEqual(reply['data']['dirtyState'],'clean')
        self.assertFalse(reply['data']['bindingLost'])

    def test_replaced_binding_rejected_before_retargeting(self):
        self.connection.call('hello',{})
        self.config['token']='0'*64
        self.config_path.write_text(json.dumps(self.config),encoding='utf-8')
        with self.assertRaises(CadenceError) as error:self.connection.call('hello',{})
        self.assertEqual(error.exception.code,'instance_replaced')

    def test_dirty_transition_invalidates_old_session(self):
        hello=self.connection.call('hello',{});g=hello['generation'];sid=uuid.uuid4().hex
        self.connection.call('session.open',{'sessionId':sid,'generation':g})
        self.change(dirty=1)
        with self.assertRaises(CadenceError) as e:self.connection.call('status',{'sessionId':sid,'generation':g})
        self.assertEqual(e.exception.code,'session_lost')
        self.assertEqual(self.connection.call('hello',{})['data']['dirtyState'],'dirty')

    def test_switch_away_and_back_stays_invalid(self):
        self.change(self.root/'other.dsn')
        self.assertTrue(self.connection.call('hello',{})['data']['bindingLost'])
        self.change()
        hello=self.connection.call('hello',{})
        self.assertTrue(hello['data']['bindingLost'])
        with self.assertRaises(CadenceError) as e:self.connection.call('session.open',{'sessionId':uuid.uuid4().hex,'generation':hello['generation']})
        self.assertEqual(e.exception.code,'target_changed')

    def test_session_release_and_unknown_operation(self):
        generation=self.connection.call('hello',{})['generation'];sid=uuid.uuid4().hex
        params={'sessionId':sid,'generation':generation}
        self.connection.call('session.open',params)
        with self.assertRaises(CadenceError) as e:self.connection.call('eval',params)
        self.assertEqual(e.exception.code,'capability_unavailable')
        self.connection.call('session.close',params)
        with self.assertRaises(CadenceError):self.connection.call('status',params)

    def test_separate_instances_cannot_share_session(self):
        generation=self.connection.call('hello',{})['generation'];sid=uuid.uuid4().hex
        self.connection.call('session.open',{'sessionId':sid,'generation':generation})
        other=NativeRpcTests('test_session_release_and_unknown_operation')
        other.setUp()
        try:
            self.assertNotEqual(other.config['instanceId'],self.config['instanceId'])
            g=other.connection.call('hello',{})['generation']
            with self.assertRaises(CadenceError):other.connection.call('status',{'sessionId':sid,'generation':g})
        finally:other.doCleanups()
