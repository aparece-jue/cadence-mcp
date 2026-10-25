import copy,csv,io,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.pspice_dat import PSpiceDat
from cadence_mcp.pspice_exports import PSpiceExports
from cadence_mcp.pspice_export_format import render_data,validate_table,COLUMNS

def table():
 return {'metadata':{'offset':2,'rowCount':1,'canonicalTrace':'=UNTRUSTED_LABEL'},'samples':[{'index':2,'axisReal':20.0,'axisImaginary':0.0,'real':1e-200,'imaginary':-1.2345678901234567}]}

class ExportTests(unittest.TestCase):
 def setup_service(self,digital=False):
  temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
  install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
  source=root/'input.dat';source.write_bytes(b'owned mock DAT');cfg=Config(install,root/'work',(root,));data=PSpiceDat(cfg)
  header={'Number':0,'AnalysisName':'AC Sweep','PrimaryParamName':'Frequency','ComplexFlag':2,'DataType':0,'NumberofAnalogRows':3,'NumberofAnalogColumns':2,'Trace Names':{'Analog Names':['Frequency',{'Gain':['V(out)']}]}}
  if digital:header.update(DataType=1,ComplexFlag=1,PrimaryParamName='Time',NumberofAnalogRows=0,NumberofAnalogColumns=0,NumberofDigitalRows=3,NumberofDigitalColumns=1,**{'Trace Names':{'Analog Names':[],'Digital Names':['DIN']}})
  def worker(directory,mode,block=0,trace=''):
   if mode=='headers':return {'blockCount':1,'headerJSON':json.dumps([header])}
   self.assertFalse(digital)
   return {'block':0,'trace':trace,'rows':3,'valuesCSV':'10,0,20,0,30,0' if trace=='Frequency' else '10,-1,20,-2,30,-3'}
  mocked=patch.object(data,'_worker',side_effect=worker);native=mocked.start();self.addCleanup(mocked.stop)
  ident=data.open(str(source))['datId'];return root,cfg,data,ident,PSpiceExports(cfg,data),native
 def test_csv_float_roundtrip_and_fixed_headers_keep_labels_out(self):
  original=table();raw=render_data(original,'csv');rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
  self.assertEqual(list(rows[0]),list(COLUMNS));self.assertNotIn('UNTRUSTED_LABEL',raw.decode())
  self.assertEqual(float(rows[0]['real']),1e-200);self.assertEqual(float(rows[0]['imaginary']),-1.2345678901234567)
 def test_json_preserves_unicode_metadata_and_nullable_imaginary(self):
  original=table();original['metadata']['canonicalTrace']='电压';original['samples'][0]['imaginary']=None
  self.assertEqual(json.loads(render_data(original,'json')),original)
  csvrow=list(csv.DictReader(io.StringIO(render_data(original,'csv').decode())))[0];self.assertEqual(csvrow['imaginary'],'')
 def test_nonfinite_bool_index_count_and_unsupported_format_refused(self):
  for key,value in [('real',math.nan),('real',math.inf),('axisReal',True),('index',True),('index',3)]:
   item=table();item['samples'][0][key]=value
   with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate_table(item)
  for value in (True,0,2):
   item=table();item['metadata']['rowCount']=value
   with self.assertRaises(ValueError):validate_table(item)
  with self.assertRaises(ValueError):render_data(table(),'tcl')
 def test_plan_binds_alias_units_offset_and_unassociated_import(self):
  root,cfg,data,ident,exports,_=self.setup_service();plan=exports.plan(ident,0,'V(out)','json',1,2)
  preview=plan['preview'];self.assertEqual(preview['canonicalTrace'],'Gain');self.assertEqual(preview['requestedTrace'],'V(out)')
  self.assertEqual((preview['offset'],preview['rowCount']),(1,2));self.assertIsNone(preview['valueUnits']['unit'])
  self.assertFalse(preview['sourceProvenance']['jobAssociationVerified']);self.assertFalse(preview['exportedRowsNumericalOracleVerified'])
  _,_,row=exports._load(plan['planId']);frozen=json.loads(Path(row['plan']['payload']['tablePath']).read_text())
  self.assertEqual(frozen['samples'],[{'index':1,'axisReal':20,'axisImaginary':0,'real':20,'imaginary':-2},{'index':2,'axisReal':30,'axisImaginary':0,'real':30,'imaginary':-3}])
  data.close(ident);exports.preflight(row['plan']['payload'])
 def test_range_block_and_digital_targets_refused(self):
  _,_,_,ident,exports,_=self.setup_service()
  for args in [(0,'Gain','csv',3,None),(0,'Gain','csv',0,4),(0,'Gain','csv',0,True),(0,'Gain','csv',-1,1),(0,'MISSING','csv',0,1),(1,'Gain','csv',0,1)]:
   with self.subTest(args=args),self.assertRaises(CadenceError):exports.plan(ident,*args)
  _,_,_,ident,exports,native=self.setup_service(True)
  with self.assertRaises(CadenceError) as caught:exports.plan(ident,0,'DIN')
  self.assertEqual(caught.exception.code,'capability_unavailable');self.assertEqual(native.call_count,1)
 def test_frozen_source_manifest_and_table_tamper_refused(self):
  for key in ('sourceDat','sourceManifest','tablePath'):
   _,_,_,ident,exports,_=self.setup_service();plan=exports.plan(ident,0,'Gain');_,_,row=exports._load(plan['planId']);payload=row['plan']['payload'];path=Path(payload[key]);path.write_bytes(path.read_bytes()+b'CONTROLLED_TAMPER')
   with self.subTest(key=key),self.assertRaises(CadenceError) as caught:exports.preflight(payload)
   self.assertEqual(caught.exception.code,'target_changed')
 def test_worker_serializes_owned_copy_and_refuses_overwrite(self):
  root,_,_,ident,exports,_=self.setup_service();plan=exports.plan(ident,0,'Gain','csv',1,2);_,_,row=exports._load(plan['planId']);payload=row['plan']['payload']
  directory=root/'worker';directory.mkdir();process=exports.execute(directory,payload,None,lambda pid:None)
  self.assertEqual(process['returnCode'],0);self.assertEqual(process['remainingOwnedProcesses'],0)
  self.assertEqual(sha256(directory/'source.dat'),payload['sourceFingerprint'])
  with (directory/'samples.csv').open(newline='',encoding='utf-8') as stream:data=list(csv.DictReader(stream))
  self.assertEqual([float(r['imaginary']) for r in data],[-2,-3]);before=sha256(directory/'samples.csv')
  process=exports.execute(directory,payload,None,lambda pid:None);self.assertNotEqual(process['returnCode'],0);self.assertEqual(sha256(directory/'samples.csv'),before)
 def test_pending_cancel_never_starts_serializer(self):
  _,_,_,ident,exports,_=self.setup_service();plan=exports.plan(ident,0,'Gain');key=(plan['planId'],plan['planDigest']);exports.cancel(*key)
  with self.assertRaises(CadenceError) as caught:exports.apply(*key,'cancelled')
  self.assertEqual(caught.exception.code,'write_not_replayed')

if __name__=='__main__':unittest.main()
