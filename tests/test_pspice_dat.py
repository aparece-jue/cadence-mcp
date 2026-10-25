import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mcp import Client
from cadence_mcp.core import CadenceError, Config, sha256
from cadence_mcp.pspice_dat import PSpiceDat,decode_headers,decode_samples
from cadence_mcp.server import create_server

def header():
    return {'Number':0,'AnalysisName':'AC Sweep','PrimaryParamName':'Frequency','ComplexFlag':2,'DataType':0,
            'NumberofAnalogRows':3,'NumberofAnalogColumns':2,
            'Trace Names':{'Analog Names':['Frequency',{'Gain':['V(out)','Gain']}]}}
def document(row=None):return {'blockCount':1,'headerJSON':json.dumps([row or header()])}

class DatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); install=self.root/'install'
        (install/'tcltk/bin').mkdir(parents=True); (install/'tcltk/bin/tclsh.exe').touch()
        self.source=self.root/'input.dat';self.source.write_bytes(b'mock native DAT')
        self.config=Config(install,self.root/'work',(self.root,));self.service=PSpiceDat(self.config)

    def worker(self,directory,mode,block=0,trace=''):
        if mode=='headers':return document()
        return {'block':block,'trace':trace,'rows':3,'valuesCSV':'1,-2,3,4,-5,6'}

    def test_exact_alias_complex_paging_and_source_preservation(self):
        before=sha256(self.source)
        with patch.object(self.service,'_worker',side_effect=self.worker) as worker:
            ident=self.service.open(str(self.source))['datId']
            rows=self.service.query(ident,'trace',0,1,1)
            self.assertEqual(rows['items'][0]['aliases'],['V(out)'])
            values=self.service.samples(ident,0,'V(out)',1,1)
            self.assertEqual(values['items'],[{'index':1,'real':3,'imaginary':4}])
            self.assertEqual(values['nextOffset'],2)
            self.assertEqual(worker.call_args.args[3],'Gain')
            self.assertIsNone(values['unit']);self.assertFalse(values['jobAssociationVerified'])
        self.assertEqual(sha256(self.source),before)

    def test_missing_trace_invalid_block_and_empty_final_page(self):
        with patch.object(self.service,'_worker',side_effect=self.worker) as worker:
            ident=self.service.open(str(self.source))['datId']
            for args in [(0,'gain'),(-1,'Gain'),(True,'Gain')]:
                with self.assertRaises(CadenceError):self.service.samples(ident,*args)
            self.assertEqual(worker.call_count,1)
            self.assertEqual(self.service.samples(ident,0,'Gain',3,2)['items'],[])
            with self.assertRaises(CadenceError):self.service.query(ident,'block',0)
            with self.assertRaises(CadenceError):self.service.query(ident,'trace',0,0,1001)

    def test_stale_copy_refused_but_close_can_release(self):
        with patch.object(self.service,'_worker',side_effect=self.worker):ident=self.service.open(str(self.source))['datId']
        (self.service.sessions[ident]['directory']/'imported.dat').write_bytes(b'changed')
        with self.assertRaises(CadenceError):self.service.query(ident,'block')
        self.assertTrue(self.service.close(ident)['closed'])
        with self.assertRaises(CadenceError):self.service.query(ident,'block')

    def test_metadata_rejects_ambiguous_aliases_and_inconsistent_headers(self):
        for key,value in [('ComplexFlag',0),('NumberofAnalogRows',100001),('Number',True),('NumberofAnalogColumns',3)]:
            row=header();row[key]=value
            with self.assertRaises(CadenceError):decode_headers(document(row))
        row=header();row['Trace Names']['Analog Names'][1]['Gain'].append('Frequency')
        with self.assertRaises(CadenceError):decode_headers(document(row))
        with self.assertRaises(CadenceError):decode_headers({'blockCount':2,'headerJSON':document()['headerJSON']})

    def test_bad_numeric_data_cannot_be_silently_truncated(self):
        block=decode_headers(document())[0][0]
        for text in ['1,2,3','nan,0,1,2,3,4','1e999,0,1,2,3,4','1,2,3,4,5,6,','1;puts bad,0,1,2,3,4']:
            with self.assertRaises(CadenceError):decode_samples({'block':0,'trace':'Gain','rows':3,'valuesCSV':text},block,'Gain')
        with self.assertRaises(CadenceError):decode_samples({'block':False,'trace':'Gain','rows':3,'valuesCSV':'1,2,3,4,5,6'},block,'Gain')

    def test_real_and_unknown_units_and_unsupported_mixed_samples(self):
        row=header();row['ComplexFlag']=1;row['DataType']=2
        block=decode_headers(document(row))[0][0]
        values=decode_samples({'block':0,'trace':'Gain','rows':3,'valuesCSV':'1,2,3'},block,'Gain')
        self.assertEqual([v['imaginary'] for v in values],[None]*3)
        with patch.object(self.service,'_worker',return_value=document(row)):
            ident=self.service.open(str(self.source))['datId']
        with self.assertRaises(CadenceError):self.service.samples(ident,0,'Gain')

    def test_mcp_contract_and_session_lifecycle(self):
        async def check():
            with patch('cadence_mcp.pspice_dat.PSpiceDat._worker',side_effect=self.worker):
                async with Client(create_server(self.config)) as client:
                    opened=await client.call_tool('pspice_dat_open',{'sourceDat':str(self.source)})
                    self.assertFalse(opened.is_error)
                    ident=opened.structured_content['data']['datId']
                    self.assertFalse((await client.call_tool('pspice_dat_samples',{'datId':ident,'block':0,'traceName':'Gain'})).is_error)
                    self.assertTrue((await client.call_tool('pspice_dat_samples',{'datId':ident,'block':0,'traceName':'Gain','eval':'puts bad'})).is_error)
                    self.assertFalse((await client.call_tool('pspice_dat_close',{'datId':ident})).is_error)
                    self.assertTrue((await client.call_tool('pspice_dat_query',{'datId':ident,'entity':'block'})).is_error)
        asyncio.run(check())
