import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import CadenceError,Config,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import validate_spec,expected_graph,canonical_meta
from cadence_mcp.library_vectors import validate_vectors,vector_descriptor,declared_descriptor
from cadence_mcp.library_vector_query import query_library_vectors,validate_descriptor
from test_library_create import spec

class VectorSpecTests(unittest.TestCase):
 def test_old_spec_digest_shape_unchanged_and_no_defaults_inserted(self):
  s=spec();graph=expected_graph(s)
  self.assertEqual(validate_spec(s),s)
  self.assertEqual(graph['meta']['symbols'],[{'scope':['TEST','A',0,'C','P.Normal'],'pinStarts':[{'position':0,'start':[0,0]}],'lines':[]}])
  new=copy.deepcopy(s);new['symbols'][0]['vectors']=[]
  self.assertEqual(expected_graph(validate_spec(new)),graph)
 def test_typed_line_is_in_both_legacy_line_subset_and_ordered_sequence(self):
  s=spec();s['symbols'][0]['vectors']=[{'kind':'line','start':[0,0],'end':[5,5]}]
  s=validate_spec(s);meta=expected_graph(s)['meta']['symbols'][0]
  self.assertEqual(meta['lines'],[{'ends':[[0,0],[5,5]],'style':0,'width':0}])
  self.assertEqual(meta['orderedVectors'],[['line',[0,0],[5,5],0,0]])
 def test_order_font_and_path_changes_are_not_canonicalized_away(self):
  s=spec();s['symbols'][0]['vectors']=[{'kind':'polyline','points':[[0,0],[1,2],[5,3]]},{'kind':'text','text':'A','bounds':[0,0,10,10]}]
  normalized=validate_spec(s);self.assertNotIn('font',s['symbols'][0]['vectors'][1])
  original=expected_graph(normalized)
  for field in ('order','points','font'):
   other=copy.deepcopy(normalized);v=other['symbols'][0]['vectors']
   if field=='order':v.reverse()
   elif field=='points':v[0]['points'].reverse()
   else:v[1]['font']['weight']=700
   self.assertNotEqual(expected_graph(other),original)
 def test_all_views_receive_order_metadata_even_empty_view(self):
  s=spec();alt=copy.deepcopy(s['symbols'][0]);alt['partName']='P.Convert';s['symbols'].append(alt)
  s['symbols'][0]['vectors']=[{'kind':'ellipse','bounds':[0,0,4,4]}]
  metas=expected_graph(validate_spec(s))['meta']['symbols']
  self.assertEqual(sorted(len(m['orderedVectors']) for m in metas),[0,1])
 def test_native_text_compares_all_font_fields_but_classification_is_derived(self):
  v=validate_vectors([{'kind':'text','text':'Hello','bounds':[1,2,10,12]}])[0]
  wanted=vector_descriptor(v)
  self.assertEqual(wanted[2],[1,2]);self.assertEqual(len(wanted[4]),14)
  for flag in (0,1):self.assertEqual(declared_descriptor(wanted+[flag]),wanted)
  for flag in (True,2,'0'):
   with self.assertRaises(CadenceError):declared_descriptor(wanted+[flag])
 def test_invalid_geometry_native_code_bool_extra_method_and_budget_rejected(self):
  bad=[{'kind':'bitmap','path':'x'},{'kind':'line','start':[0,0],'end':[0,0]},
   {'kind':'ellipse','bounds':[4,0,0,4]},{'kind':'box','bounds':[0,0,4,4],'fill':3},
   {'kind':'box','bounds':[0,0,4,4],'style':6},{'kind':'box','bounds':[0,0,4,4],'width':True},
   {'kind':'fill','start':[0,0],'hatch':6},{'kind':'polygon','points':[[0,0]]*3},
   {'kind':'text','text':'A\0B','bounds':[0,0,4,4]},
   {'kind':'text','text':'A','bounds':[0,0,4,4],'font':{'height':0}},
   {'kind':'line','start':[True,0],'end':[1,2]},
   {'kind':'line','start':[0,0],'end':[1,2],'eval':'unsafe'}]
  for v in bad:
   with self.subTest(v=v),self.assertRaises(CadenceError):validate_vectors([v])
  with self.assertRaises(CadenceError):validate_vectors([{'kind':'text','text':'x'*4096,'bounds':[0,0,4,4]}]*5)

class VectorQueryTests(unittest.TestCase):
 def test_cursor_bound_to_part_limit_session_and_copy_hash_including_cache(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);work=root/'work';directory=work/'lib';directory.mkdir(parents=True);copied=directory/'library.olb';copied.write_bytes(b'owned')
   install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();library=LibraryService(Config(install,work,(root,)))
   data={'package':[{'objectId':'pkg','name':'PKG'}],'device':[{'objectId':'dev','designator':'A'}],
         'part':[{'objectId':'p','packageId':'pkg','deviceId':'dev','name':'P.Normal'},
                 {'objectId':'q','packageId':'pkg','deviceId':'dev','name':'P.Convert'}]}
   library.sessions['lib']={'directory':directory,'revision':sha256(copied),'data':data,'cursors':{},
        'basicVectors':{'p':[{'index':i} for i in range(4)]}}
   page=query_library_vectors(library,'lib','p',None,2);self.assertEqual(page['total'],4)
   token=page['nextCursor'];self.assertIsNotNone(token)
   self.assertEqual(query_library_vectors(library,'lib','p',token,2)['items'],[{'index':2},{'index':3}])
   for part,limit in [('q',2),('p',3)]:
    with self.assertRaises(CadenceError) as caught:query_library_vectors(library,'lib',part,token,limit)
    self.assertEqual(caught.exception.code,'stale_cursor')
   with self.assertRaises(CadenceError):query_library_vectors(library,'lib','foreign',None,2)
   copied.write_bytes(b'tampered')
   with self.assertRaises(CadenceError) as caught:query_library_vectors(library,'lib','p',token,2)
   self.assertEqual(caught.exception.code,'target_changed')
   library.close('lib')
   with self.assertRaises(CadenceError):query_library_vectors(library,'lib','p',None,2)
 def test_bad_native_shape_or_scope_never_cached(self):
  for v in [['line',[0,0],[1,2],0],['text','T',[0,0],[0,0,2,2],['Arial'],0],['bitmap','x'],['fill',[True,0],0,0]]:
   with self.subTest(v=v),self.assertRaises(ValueError):validate_descriptor(v)

