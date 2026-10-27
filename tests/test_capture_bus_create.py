import copy, unittest
from pathlib import Path
from cadence_mcp.core import CadenceError
from cadence_mcp.capture_bus_create import validate_spec, wire_groups, entry_rows, CaptureBusCreates, EditorBusHost
from cadence_mcp.editor_wire_host import EditorWireHost, ADAPTER_NAMES

class BusCreateTests(unittest.TestCase):
 def branch(self):
  return dict(index=0,entryPoint=[100,120],endPoint=[120,140],wireEnd=[200,140],expectedBusAttached=True)
 def spec(self,**changes):
  args=dict(prefix='DATA',first=7,last=0,start=[100,100],end=[100,500],branches=[self.branch()]);args.update(changes);return validate_spec(**args)
 def test_partial_and_detached_are_explicit_not_silently_completed(self):
  self.assertEqual(len(self.spec()['branches']),1)
  b=self.branch();b.update(entryPoint=[90,120],expectedBusAttached=False)
  self.assertFalse(self.spec(branches=[b])['branches'][0]['expectedBusAttached'])
  self.assertEqual(self.spec(first=0,last=7)['members'],['DATA'+str(i) for i in range(8)])
 def test_invalid_ranges_names_and_noninteger_coordinates_refused(self):
  for args in [dict(prefix='DATA;exec'),dict(first=True),dict(last=7),dict(first=128,last=0),dict(start=[True,100]),dict(end=[200,500])]:
   with self.subTest(args=args),self.assertRaises(CadenceError):self.spec(**args)
 def test_wrong_declared_attachment_refused_before_native_work(self):
  for attached,x in [(False,100),(True,90)]:
   b=self.branch();b.update(entryPoint=[x,120],expectedBusAttached=attached)
   with self.assertRaises(CadenceError) as e:self.spec(branches=[b])
   self.assertEqual(e.exception.code,'inconsistent_bus_expectation')
 def test_duplicate_unknown_and_untyped_branches_refused(self):
  for bs in [[self.branch(),self.branch()],[{**self.branch(),'index':8}],[{**self.branch(),'expectedBusAttached':1}],[{**self.branch(),'command':'eval'}]]:
   with self.subTest(bs=bs),self.assertRaises(CadenceError):self.spec(branches=bs)
 def data(self):return dict(schematic=[dict(objectId='s',name='ROOT')],page=[dict(objectId='p',schematicId='s',name='PAGE')])
 def wire(self,points,ident='w'):
  return dict(wireId=ident,pageId='p',isBus=True,isBundle=False,name='DATA[1..0]',width=2,members=[dict(name='DATA1'),dict(name='DATA0')],points=points)
 def test_native_splitting_preserves_geometry_but_name_and_order_matter(self):
  original=self.wire([[100,100],[100,500]])
  split=[self.wire([[100,100],[100,200]],'a'),self.wire([[100,200],[100,500]],'b')]
  self.assertEqual(wire_groups(self.data(),[original]),wire_groups(self.data(),split))
  for key,value in [('name','OTHER[1..0]'),('members',[dict(name='DATA0'),dict(name='DATA1')])]:
   changed=copy.deepcopy(original);changed[key]=value
   self.assertNotEqual(wire_groups(self.data(),[original]),wire_groups(self.data(),[changed]))
 def test_entry_semantics_ignore_pointer_changes_but_preserve_null(self):
  w=self.wire([[100,100],[100,500]])
  e=dict(pageId='p',entryPoint=[100,120],endPoint=[120,140],entryWireId='w',endWireId=None)
  before=entry_rows(self.data(),dict(wires=[w],entries=[e]))
  w['wireId']='new';e['entryWireId']='new'
  self.assertEqual(before,entry_rows(self.data(),dict(wires=[w],entries=[e])))
  self.assertIsNone(before[0][-1]);e['entryWireId']=None
  self.assertNotEqual(before,entry_rows(self.data(),dict(wires=[w],entries=[e])))
 def test_started_cancel_cannot_reach_host(self):
  job=object.__new__(CaptureBusCreates);job._load=lambda _: (Path('.'),None,dict(digest='d',state='started'))
  with self.assertRaises(CadenceError) as e:job.cancel('p','d')
  self.assertEqual(e.exception.code,'too_late')
 def test_bus_adapter_does_not_change_existing_wire_proofs(self):
  self.assertEqual(EditorWireHost.adapter_names,ADAPTER_NAMES)
  self.assertEqual(EditorBusHost.adapter_names,ADAPTER_NAMES+('editor_bus_create_job.tcl',))

if __name__=='__main__':unittest.main()
