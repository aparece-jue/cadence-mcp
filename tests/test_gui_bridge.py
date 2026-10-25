from pathlib import Path
import json
import socket
import tempfile
import threading
import unittest

from cadence_mcp.gui_bridge import GuiBridgeClient
from cadence_mcp.core import CadenceError,sha256

class BridgeClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.design=self.root/'copy.dsn'
        self.design.write_bytes(b'fixture')
        self.config={'expectedDesign':str(self.design),'sourceFingerprint':sha256(self.design),
                     'expectedPid':123,'instanceId':'test-instance','token':'test-token'}
        self.path=self.root/'binding.json'
        self.path.write_text(json.dumps(self.config),encoding='utf-8')

    def server(self,kind='ok'):
        listener=socket.socket()
        listener.bind(('127.0.0.1',0)); listener.listen(1); listener.settimeout(5)
        endpoint={'host':'127.0.0.1','port':listener.getsockname()[1],'protocol':1,'pid':123,'instanceId':'test-instance'}
        (self.root/'endpoint.json').write_text(json.dumps(endpoint),encoding='utf-8')
        self.errors=[]
        def serve():
            try:
                with listener,listener.accept()[0] as connection:
                    connection.settimeout(3)
                    request=json.loads(connection.makefile('rb').readline(16385))
                    if kind=='close':return
                    row={'protocol':1,'requestId':request['requestId'],'instanceId':'test-instance','pid':123,
                         'status':'succeeded','activeDesign':str(self.design),'tclVersion':'8.6.5',
                         'readOnly':True,'dirtyState':'unknown','capabilities':['gui.status']}
                    if kind=='target':row.update(status='target_changed',activeDesign=str(self.root/'other.dsn'))
                    if kind=='nonce':row['instanceId']='wrong'
                    if kind=='request':row['requestId']='wrong'
                    connection.sendall(json.dumps(row).encode()+b'\n')
            except Exception as e:self.errors.append(e)
        thread=threading.Thread(target=serve,daemon=True);thread.start()
        self.addCleanup(thread.join,6)

    def test_bound_status_does_not_leak_token(self):
        self.server()
        row=GuiBridgeClient(self.path).status()
        self.assertTrue(row['bindingVerified'])
        self.assertNotIn('test-token',json.dumps(row))
        self.assertEqual(row['dirtyState'],'unknown')

    def test_switched_design_not_retargeted(self):
        self.server('target')
        with self.assertRaises(CadenceError) as e:GuiBridgeClient(self.path).status()
        self.assertEqual(e.exception.code,'target_changed')

    def test_wrong_response_identity_rejected(self):
        for kind in ['nonce','request','close']:
            self.server(kind)
            with self.assertRaises(CadenceError):GuiBridgeClient(self.path).status()

    def test_changed_file_rejected_before_connect(self):
        (self.root/'endpoint.json').write_text(json.dumps({'host':'127.0.0.1','port':123,'protocol':1,'pid':123,'instanceId':'test-instance'}))
        self.design.write_bytes(b'changed')
        with self.assertRaises(CadenceError) as e:GuiBridgeClient(self.path).status()
        self.assertEqual(e.exception.code,'target_changed')

    def test_remote_or_wrong_endpoint_rejected(self):
        for field,value in [('host','0.0.0.0'),('pid',456),('port',True)]:
            ep={'host':'127.0.0.1','port':123,'protocol':1,'pid':123,'instanceId':'test-instance'}
            ep[field]=value
            (self.root/'endpoint.json').write_text(json.dumps(ep))
            with self.assertRaises(CadenceError):GuiBridgeClient(self.path).status()
