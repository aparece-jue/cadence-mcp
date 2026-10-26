import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.pspice_library_metadata import inspect_library_metadata,normalize_library_metadata

def payload():return {'Data_Subckt':[json.dumps({'Title':'RC_META','Nodes':['IN','OUT'],'OptNodes':[]})],'Data_Models':[json.dumps({'Title':'D_META','Type':'D','AKO':'','Nodes':'A, C'})],'matchingSubckts':'RC_META '}
class LibraryMetadataTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);r=Path(self.tmp.name);self.input=r/'inputs';self.input.mkdir();install=r/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();self.config=Config(install,r/'work',(self.input,));self.source=self.input/'example.lib';self.source.write_text('.MODEL D_META D\n.SUBCKT RC_META IN OUT\nR1 IN OUT 1k\n.ENDS RC_META\n',encoding='utf-8')
 def worker(self,args,cwd,env,timeout):
  Path(args[-1]).write_text(json.dumps({'returned':True,'value':json.dumps(payload())}),encoding='utf-8');return {'returnCode':0,'remainingOwnedProcesses':0}
 def test_native_nested_json_metadata_and_formal_port_order(self):
  rows=normalize_library_metadata(payload(),[('MODEL','D_META'),('SUBCKT','RC_META')],2);self.assertEqual(rows[0]['formalNodes'],['IN','OUT']);self.assertTrue(rows[0]['matchesPinCount']);self.assertNotIn('Definition',str(rows));self.assertEqual(rows[1]['akoReference'],'')
 def test_missing_duplicate_or_wrong_native_filter_rejected(self):
  for kind in ('missing','duplicate','filter','malformed'):
   data=payload()
   if kind=='missing':data['Data_Models']=[]
   if kind=='duplicate':data['Data_Models']*=2
   if kind=='filter':data['matchingSubckts']='OTHER'
   if kind=='malformed':data['Data_Subckt']=['not json']
   with self.subTest(kind=kind),self.assertRaises(CadenceError):normalize_library_metadata(data,[('MODEL','D_META'),('SUBCKT','RC_META')],2)
 def test_snapshot_paging_and_native_completion_with_source_unchanged(self):
  before=sha256(self.source)
  with patch('cadence_mcp.pspice_library_metadata.run_owned_process',self.worker):value=inspect_library_metadata(self.config,str(self.source),2,1,1)
  self.assertEqual(value['total'],2);self.assertEqual(value['items'][0]['name'],'D_META');self.assertFalse(value['hasMore']);self.assertTrue(value['sourceUnchanged']);self.assertFalse(value['dependencyClosureVerified']);self.assertEqual(sha256(self.source),before)
 def test_reference_binary_and_query_boundaries_refuse_before_native(self):
  for raw in (b'.LIB other.lib\n',b'.include other.lib\n',b'* binary\x00'):
   self.source.write_bytes(raw)
   with patch('cadence_mcp.pspice_library_metadata.run_owned_process') as native:
    with self.assertRaises(CadenceError):inspect_library_metadata(self.config,str(self.source))
    native.assert_not_called()
  for pins,offset,limit in ((True,0,1),(0,-1,1),(0,0,0),(4097,0,1)):
   with self.assertRaises(CadenceError):inspect_library_metadata(self.config,str(self.source),pins,offset,limit)
 def test_local_definitions_are_counted_without_false_top_level_completeness(self):
  self.source.write_text('.MODEL D_META D\n.SUBCKT RC_META IN OUT\n.MODEL LOCAL_D D\nD1 IN OUT LOCAL_D\n.ENDS RC_META\n',encoding='utf-8')
  with patch('cadence_mcp.pspice_library_metadata.run_owned_process',self.worker):value=inspect_library_metadata(self.config,str(self.source),2)
  self.assertEqual(value['definitionScope'],'top_level');self.assertEqual(value['localDefinitionsNotReturned'],1);self.assertEqual(value['total'],2)
  self.source.write_text('.SUBCKT INCOMPLETE IN OUT\n',encoding='utf-8')
  with patch('cadence_mcp.pspice_library_metadata.run_owned_process') as native:
   with self.assertRaises(CadenceError):inspect_library_metadata(self.config,str(self.source))
   native.assert_not_called()
 def test_failed_native_process_never_publishes_metadata(self):
  with patch('cadence_mcp.pspice_library_metadata.run_owned_process',return_value={'returnCode':3221225477,'remainingOwnedProcesses':0}):
   with self.assertRaises(CadenceError) as e:inspect_library_metadata(self.config,str(self.source))
  self.assertEqual(e.exception.code,'library_parser_failed')
