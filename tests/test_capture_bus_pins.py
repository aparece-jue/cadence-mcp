import copy,unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.capture_bus_pins import validate_pin_members

def fixture():
 definitions=dict(schematic=[dict(objectId='s',name='ROOT',generation=1)],page=[dict(objectId='p',schematicId='s',name='MAIN',generation=1)],part=[dict(objectId='o',pageId='p',schematicId='s',reference='R1',generation=1)],pin=[dict(objectId='i',partId='o',pageId='p',schematicId='s',reference='R1',number='1',name='A',connected=True,net='D0',generation=1)])
 data={k:[{n:v for n,v in row.items() if n!='generation'} for row in rows] for k,rows in definitions.items()}
 data['busGroups']=[dict(busGroupId='g',pageId='p',name='D[1..0]',width=2,members=['D1','D0'])]
 data['memberships']=[dict(pinId='i',busGroupId='g',pageId='p',reference='R1',pinNumber='1',busName='D[1..0]',pinNet='D0',hasMember=True,position=1,memberPointerEqualsPinNet=True)]
 return definitions,data

class BusPinValidationTests(unittest.TestCase):
 def test_native_membership_preserves_declared_order(self):
  definitions,data=fixture();validate_pin_members(data,definitions)
 def test_missing_duplicate_foreign_and_cross_page_rows_refused(self):
  for mode in ('missing','duplicate','foreign','cross_page'):
   definitions,data=fixture()
   if mode=='missing':data['memberships']=[]
   elif mode=='duplicate':data['memberships']*=2
   elif mode=='foreign':data['memberships'][0]['pinId']='outside'
   else:data['memberships'][0]['pageId']='outside'
   with self.subTest(mode=mode),self.assertRaises(CadenceError):validate_pin_members(data,definitions)
 def test_wrong_member_position_and_boolean_substitutes_refused(self):
  for change in [dict(position=0),dict(position=True),dict(hasMember=1),dict(memberPointerEqualsPinNet=False),dict(pinNet='OTHER')]:
   definitions,data=fixture();data['memberships'][0].update(change)
   with self.subTest(change=change),self.assertRaises(CadenceError):validate_pin_members(data,definitions)
 def test_nonmembership_cannot_be_promoted_by_matching_name(self):
  definitions,data=fixture();data['memberships'][0].update(hasMember=False,memberPointerEqualsPinNet=False,position=-1)
  validate_pin_members(data,definitions)
  data['memberships'][0]['position']=1
  with self.assertRaises(CadenceError):validate_pin_members(data,definitions)
 def test_unchanged_definitions_required_even_for_nonmembers(self):
  definitions,data=fixture();data['pin'][0]['net']='changed'
  with self.assertRaises(CadenceError):validate_pin_members(data,definitions)
 def test_unknown_groups_and_excessive_names_refused(self):
  for mode in ('group','name','width'):
   definitions,data=fixture()
   if mode=='group':data['busGroups'][0]['busGroupId']='foreign'
   elif mode=='name':data['busGroups'][0]['members'][0]='x'*4097
   else:data['busGroups'][0]['width']=True
   with self.subTest(mode=mode),self.assertRaises(CadenceError):validate_pin_members(data,definitions)

if __name__=='__main__':unittest.main()
