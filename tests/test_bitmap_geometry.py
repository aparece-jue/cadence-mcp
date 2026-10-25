import copy,unittest
from pydantic import ValidationError
from cadence_mcp.core import CadenceError
from cadence_mcp.library_vectors import BitmapGeometry,VECTOR_ADAPTER
from cadence_mcp.library_vector_edit import expected_vector_edit,vector_graph
from test_library_vector_edit import inspection

class BitmapGeometryTests(unittest.TestCase):
    scope=['TEST','A',0,'C','P.Normal']
    geometry={'bounds':[3,4,43,34],'location':[3,4],'expectedDibSha256':'a'*64}
    def graph(self):
        data=inspection()
        for row in data['meta']['symbols']:
            row['orderedVectors'].append(['bitmap',[0,0,20,20],[0,0],[2,2],56,'a'*64])
        return vector_graph(data)
    def test_geometry_update_all_references_without_pixel_or_dimension_change(self):
        graph=self.graph();before=copy.deepcopy(graph)
        expected,new,old,affected=expected_vector_edit(graph,self.scope,2,'update',None,self.geometry)
        self.assertEqual(graph,before);self.assertEqual(len(affected),2)
        self.assertEqual(new,{'kind':'bitmap','bounds':[3,4,43,34],'location':[3,4]})
        for row in expected['metadata']['symbols']:
            original=next(r for r in before['metadata']['symbols'] if r['scope']==row['scope'])
            if row['scope'][-1]=='P.Normal':
                self.assertEqual(row['orderedVectors'][2],['bitmap',[3,4,43,34],[3,4],[2,2],56,'a'*64])
                self.assertEqual(row['orderedVectors'][:2],original['orderedVectors'][:2])
            else:self.assertEqual(row,original)
        self.assertEqual(expected['definitions'],before['definitions'])
    def test_wrong_pixel_expectation_rejected(self):
        with self.assertRaises(CadenceError) as caught:
            expected_vector_edit(self.graph(),self.scope,2,'update',None,{**self.geometry,'expectedDibSha256':'b'*64})
        self.assertEqual(caught.exception.code,'bitmap_content_mismatch')
    def test_ambiguous_arguments_and_wrong_kind_rejected(self):
        for index,operation,replacement,geometry in [(2,'delete',None,self.geometry),(0,'update',None,self.geometry),(2,'update',None,None),(2,'update',{'kind':'fill','start':[0,0]},self.geometry)]:
            with self.subTest(index=index,operation=operation),self.assertRaises(CadenceError):
                expected_vector_edit(self.graph(),self.scope,index,operation,replacement,geometry)
    def test_noop_rejected(self):
        geometry={**self.geometry,'bounds':[0,0,20,20],'location':[0,0]}
        with self.assertRaises(CadenceError) as caught:expected_vector_edit(self.graph(),self.scope,2,'update',None,geometry)
        self.assertEqual(caught.exception.code,'no_change')
    def test_strict_geometry_and_no_pixel_creation_union(self):
        for change in [{'bounds':[0,0,0,20]},{'location':[True,0]},{'bounds':[0,0,1000001,20]},{'expectedDibSha256':'x'*64},{'dimensions':[9,9]}]:
            with self.subTest(change=change),self.assertRaises(ValidationError):BitmapGeometry.model_validate({**self.geometry,**change})
        with self.assertRaises(ValidationError):VECTOR_ADAPTER.validate_python({'kind':'bitmap',**self.geometry})

if __name__=='__main__':unittest.main()
