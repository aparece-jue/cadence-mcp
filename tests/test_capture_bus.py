import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_bus import query_bus,validate_bus_inventory

def inventory():
 def bus(page):return {'wireId':page+'/bus','pageId':page,'isBus':True,'isBundle':False,'name':'D[1..0]','points':[[0,0],[0,100]],'width':2,'members':[{'position':0,'name':'D1'},{'position':1,'name':'D0'}]}
 return {'wires':[bus('p1'),bus('p2'),{'wireId':'p1/scalar','pageId':'p1','isBus':False,'isBundle':False,'name':'D0','points':[[10,20],[100,20]],'width':0,'members':[]}],'entries':[{'entryId':'p1/entry','pageId':'p1','entryPoint':[0,10],'endPoint':[10,20],'entryWireId':'p1/bus','endWireId':'p1/scalar'}]}

class BusInventoryTests(unittest.TestCase):
 def test_native_order_duplicate_names_across_pages_and_unbound_entry(self):
  data=inventory();validate_bus_inventory(data,{'p1','p2'});data['entries'][0]['endWireId']=None;validate_bus_inventory(data,{'p1','p2'})
 def test_wrong_width_order_types_or_foreign_links_refused(self):
  for change in ('width','order','bool','point','foreign','cross_page'):
   data=inventory()
   if change=='width':data['wires'][0]['width']=3
   elif change=='order':data['wires'][0]['members'][0]['position']=1
   elif change=='bool':data['wires'][0]['isBus']=1
   elif change=='point':data['wires'][0]['points'][0]=[True,0]
   elif change=='foreign':data['entries'][0]['endWireId']='outside'
   else:data['entries'][0]['endWireId']='p2/bus'
   with self.subTest(change=change),self.assertRaises(CadenceError):validate_bus_inventory(data,{'p1','p2'})
 def test_total_member_and_point_budget_is_bounded(self):
  data=inventory();wire=data['wires'][0];wire['width']=10000;wire['members']=[{'position':i,'name':str(i)} for i in range(10000)];wire['points']=[[0,i] for i in range(10000)]
  data={'wires':[{**copy.deepcopy(wire),'wireId':'w'+str(i)} for i in range(6)],'entries':[]}
  with self.assertRaises(CadenceError):validate_bus_inventory(data,{'p1','p2'})

class BusQueryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();source=root/'source.dsn';source.write_bytes(b'owned fixture');self.capture=CaptureService(Config(install,root/'work',(root,)));ws=self.capture.create_workspace(str(source));self.calls=[]
  def worker(config,script,args,cwd):
   self.calls.append(script)
   data={'schematic':[{'objectId':'s','name':'ROOT'}],'page':[{'objectId':'p1','schematicId':'s','name':'A'},{'objectId':'p2','schematicId':'s','name':'B'}],'part':[],'pin':[]} if script=='inspect.tcl' else inventory()
   Path(args[1]).write_text(json.dumps(data),encoding='utf-8')
  self.worker=worker
  with patch('cadence_mcp.capture.run_tcl',side_effect=worker):self.sid=self.capture.open(ws['workspaceId'])['sessionId']
 def query(self,*args,**kwargs):
  with patch('cadence_mcp.capture_bus.run_tcl',side_effect=self.worker):return query_bus(self.capture,self.sid,*args,**kwargs)
 def test_page_isolation_paging_and_cursor_query_binding(self):
  first=self.query('bus',limit=1);self.assertEqual(first['total'],2);self.assertEqual(first['items'][0]['pageId'],'p1');cursor=first['nextCursor'];self.assertIsNotNone(cursor)
  second=self.query('bus',cursor=cursor,limit=1);self.assertEqual(second['items'][0]['pageId'],'p2');self.assertTrue(second['complete'])
  for args in ({'entity':'entry','cursor':cursor,'limit':1},{'entity':'bus','cursor':cursor,'limit':2},{'entity':'bus','page_id':'p1','cursor':cursor,'limit':1}):
   with self.assertRaises(CadenceError) as error:self.query(**args)
   self.assertEqual(error.exception.code,'stale_cursor')
  self.assertEqual(self.query('bus',page_id='p2')['total'],1);self.assertEqual(self.calls.count('inspect_bus.tcl'),1)
 def test_cached_query_rechecks_snapshot_and_closed_session(self):
  self.query('entry');self.capture.sessions[self.sid]['design'].write_bytes(b'tampered')
  with self.assertRaises(CadenceError) as error:self.query('entry')
  self.assertEqual(error.exception.code,'target_changed');self.capture.close(self.sid)
  with self.assertRaises(CadenceError):self.query('entry')
 def test_invalid_entity_page_and_limit_fail_before_native_read(self):
  for args in ({'entity':'shell'},{'entity':'bus','page_id':'outside'},{'entity':'bus','limit':True}):
   with self.assertRaises(CadenceError):self.query(**args)
  self.assertEqual(self.calls.count('inspect_bus.tcl'),0)
 def test_foreign_session_cannot_reuse_bus_cursor(self):
  first=self.query('bus',limit=1);ws=self.capture.create_workspace(str(self.capture.sessions[self.sid]['design']))
  with patch('cadence_mcp.capture.run_tcl',side_effect=self.worker):other=self.capture.open(ws['workspaceId'])['sessionId']
  with patch('cadence_mcp.capture_bus.run_tcl',side_effect=self.worker),self.assertRaises(CadenceError) as error:query_bus(self.capture,other,'bus',cursor=first['nextCursor'],limit=1)
  self.assertEqual(error.exception.code,'stale_cursor')

if __name__=='__main__':unittest.main()
