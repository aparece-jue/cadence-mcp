import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.pspice_dat import PSpiceDat,legacy_header
from cadence_mcp.core import Config,CadenceError
class DirectHeaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
        self.source=root/'fresh.dat';self.source.write_bytes(b'owned fresh data');self.reader=PSpiceDat(Config(install,root/'work',(root,)))
        self.raw={'blockCount':1,'headerJSON':'{"filename":{"Analog Traces":{},"Sweep Data":{},"Number Of Analog Rows":1,},}'}
        self.header={'blockCount':1,'headerJSON':json.dumps([{'Number':0,'AnalysisName':'AC Sweep','PrimaryParamName':'Frequency','ComplexFlag':2,'DataType':0,'NumberofAnalogRows':1,'NumberofAnalogColumns':2,'Trace Names':{'Analog Names':['Frequency','V(OUT)']}}])}
    def test_legacy_uses_independent_direct_fields_and_rejects_unknown_trace_before_native(self):
        with patch.object(self.reader,'_worker',side_effect=[self.raw,self.header]) as worker:
            opened=self.reader.open(str(self.source));ident=opened['datId']
            self.assertEqual(worker.call_args.args[1],'headers_direct');self.assertEqual(opened['headerSource'],'native_direct_headers')
            self.assertEqual(opened['aliasGroupingSource'],'not_available_from_direct_names')
            self.assertEqual(self.reader.query(ident,'trace',0)['items'][1]['name'],'V(OUT)')
            with self.assertRaises(CadenceError):self.reader.samples(ident,0,'V(MISSING)')
            self.assertEqual(worker.call_count,2)
    def test_arbitrary_malformed_json_does_not_trigger_native_fallback(self):
        for value in ['{"junk":1,}', '[{"bad":true}]', '{}']:
            with patch.object(self.reader,'_worker',return_value={'blockCount':1,'headerJSON':value}) as worker:
                with self.assertRaises(CadenceError):self.reader.open(str(self.source))
                self.assertEqual(worker.call_count,1)
    def test_direct_metadata_cannot_bypass_common_count_and_alias_validation(self):
        bad=json.loads(self.header['headerJSON']);bad[0]['NumberofAnalogColumns']=3
        with patch.object(self.reader,'_worker',side_effect=[self.raw,{'blockCount':1,'headerJSON':json.dumps(bad)}]):
            with self.assertRaises(CadenceError):self.reader.open(str(self.source))
        self.assertEqual(self.reader.sessions,{})
