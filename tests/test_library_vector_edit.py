import copy,json,tempfile,unittest
from pathlib import Path
from cadence_mcp.core import CadenceError,Config,sha256
from cadence_mcp.library import LibraryService
from cadence_mcp.library_vector_edit import vector_graph,expected_vector_edit,normalize_target_font,LibraryVectorEdits
from cadence_mcp.isolated_jobs import digest
from cadence_mcp.gui_jobs import durable_json

def inspection():
    font=['Arial',-11,0,0,0,400,0,0,0,0,7,0,1,16]
    data={'package':[{'objectId':'pkg','name':'TEST','size':2,'homogeneous':True,'footprint':'FP'}],
          'device':[],'cell':[],'part':[],'pin':[],'meta':{'packages':[{'packageName':'TEST','referenceTemplate':'U?'}],'symbols':[]}}
    for index,name in enumerate(('A','B')):
        device='d'+name;cell='c'+name
        data['device'].append({'objectId':device,'packageId':'pkg','designator':name,'position':index,'cellId':cell})
        data['cell'].append({'objectId':cell,'deviceId':device,'packageId':'pkg','name':'C'})
        for variant in ('Normal','Convert'):
            part=device+variant
            data['part'].append({'objectId':part,'packageId':'pkg','deviceId':device,'cellId':cell,'name':'P.'+variant})
            data['pin'].append({'objectId':part+'pin','packageId':'pkg','deviceId':device,'partId':part,'name':'A','position':0,'number':'1','pinType':4,'visible':True,'shared':True,'swapId':0,'hotSpot':[0,0]})
            data['meta']['symbols'].append({'scope':['TEST',name,index,'C','P.'+variant],
             'pinStarts':[{'position':0,'start':[1,0]}],'lines':[{'start':[0,0],'end':[5,0],'style':0,'width':0}],
             'otherVectorTypes':[],'orderedVectors':[['line',[0,0],[5,0],0,0],['text','T',[0,0],[0,0,10,10],copy.deepcopy(font),0]]})
    return data

class VectorEditTests(unittest.TestCase):
    scope=['TEST','A',0,'C','P.Normal']
    def test_shared_symbol_update_changes_all_named_references_and_preserves_other_view(self):
        graph=vector_graph(inspection());before=copy.deepcopy(graph)
        expected,declared,old,affected=expected_vector_edit(graph,self.scope,0,'update',{'kind':'line','start':[1,2],'end':[6,2],'style':1})
        self.assertEqual(graph,before);self.assertEqual(len(affected),2);self.assertEqual(expected['definitions'],graph['definitions'])
        for a,b in zip(expected['metadata']['symbols'],graph['metadata']['symbols']):
            if a['scope'][-1]=='P.Convert':self.assertEqual(a,b)
            else:
                self.assertEqual(a['orderedVectors'][0],['line',[1,2],[6,2],1,0])
                self.assertEqual(a['orderedVectors'][1:],b['orderedVectors'][1:])
                self.assertEqual(a['pinStarts'],b['pinStarts'])
    def test_delete_removes_exact_order_position_without_altering_remaining_fields(self):
        graph=vector_graph(inspection());expected,_,_,affected=expected_vector_edit(graph,self.scope,0,'delete',None)
        self.assertEqual(len(affected),2)
        for a,b in zip(expected['metadata']['symbols'],graph['metadata']['symbols']):
            self.assertEqual(a['orderedVectors'],b['orderedVectors'][1:] if a['scope'][-1]=='P.Normal' else b['orderedVectors'])
    def test_target_text_classification_is_derived_but_untouched_classification_is_preserved(self):
        graph=vector_graph(inspection())
        expected,new,_,_=expected_vector_edit(graph,self.scope,1,'update',{'kind':'text','text':'New','bounds':[1,1,20,20]})
        changed=copy.deepcopy(expected)
        for row in changed['metadata']['symbols']:
            if row['scope'][-1]=='P.Normal':row['orderedVectors'][1][-1]=1
        normalized=normalize_target_font(expected,'P.Normal',1,'update','text')
        self.assertEqual(normalize_target_font(changed,'P.Normal',1,'update','text'),normalized)
        row=next(r for r in changed['metadata']['symbols'] if r['scope'][-1]=='P.Convert');row['orderedVectors'][1][-1]=1
        self.assertNotEqual(normalize_target_font(changed,'P.Normal',1,'update','text'),normalized)
    def test_kind_change_noop_delete_replacement_and_bad_target_are_rejected(self):
        graph=vector_graph(inspection())
        for index,op,new in [(0,'update',{'kind':'fill','start':[0,0]}),(0,'update',{'kind':'line','start':[0,0],'end':[5,0]}),
                             (0,'delete',{'kind':'line','start':[0,0],'end':[5,0]}),(5,'delete',None),(True,'delete',None),(0,'eval',None)]:
            with self.subTest(index=index,op=op,new=new),self.assertRaises(CadenceError):expected_vector_edit(graph,self.scope,index,op,new)
    def test_inconsistent_repeated_symbol_view_requires_more_specific_native_identity(self):
        graph=vector_graph(inspection())
        row=next(r for r in graph['metadata']['symbols'] if r['scope'][1]=='B' and r['scope'][-1]=='P.Normal')
        row['orderedVectors'][0][1]=[99,0]
        with self.assertRaises(CadenceError) as caught:expected_vector_edit(graph,self.scope,0,'delete',None)
        self.assertEqual(caught.exception.code,'ambiguous_library_graph')
    def test_missing_metadata_unknown_vectors_bad_font_and_pin_starts_refused(self):
        changes=[lambda d:d['meta']['symbols'].pop(),lambda d:d['meta']['symbols'][0]['otherVectorTypes'].append(999),
                 lambda d:d['meta']['symbols'][0]['orderedVectors'][1].pop(),
                 lambda d:d['meta']['symbols'][0]['pinStarts'].clear()]
        for change in changes:
            d=inspection();change(d)
            with self.assertRaises(CadenceError):vector_graph(d)
    def test_order_and_template_changes_affect_preservation_graph(self):
        original=vector_graph(inspection())
        for field in ('order','template','pin_start'):
            d=inspection()
            if field=='order':d['meta']['symbols'][0]['orderedVectors'].reverse()
            elif field=='template':d['meta']['packages'][0]['referenceTemplate']='X?'
            else:d['meta']['symbols'][0]['pinStarts'][0]['start']=[2,0]
            self.assertNotEqual(vector_graph(d),original)
    def test_frozen_expected_evidence_and_source_hash_cannot_change_after_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
            work=root/'work';work.mkdir();source=work/'library.olb';source.write_bytes(b'owned source')
            before=work/'before.json';before.write_text('{}');expected=work/'expected.json';expected.write_text('{}')
            cfg=Config(install,work,(root,));edit=LibraryVectorEdits(cfg,LibraryService(cfg))
            payload={'sourceLibrary':str(source),'sourceFingerprint':sha256(source),
              'beforeEvidence':str(before),'beforeEvidenceHash':sha256(before),
              'expectedEvidence':str(expected),'expectedEvidenceHash':sha256(expected)}
            edit.preflight(payload)
            expected.write_text('{"changed":true}')
            with self.assertRaises(CadenceError):edit.preflight(payload)
            expected.write_text('{}');source.write_bytes(b'changed source')
            with self.assertRaises(CadenceError):edit.preflight(payload)
    def test_large_shared_reference_result_remains_readable_after_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
            cfg=Config(install,root/'work',(root,));edit=LibraryVectorEdits(cfg,LibraryService(cfg))
            affected=[[str(i).zfill(3)+'P'*61,'A',0,'C'*64,'N'*64] for i in range(150)]
            payload={'partId':'part','vectorId':'part/vector-1','scope':affected[0],'index':0,
              'old':['text','x'*9000,[0,0],[0,0,10,10],['Arial',-11,0,0,0,400,0,0,0,0,7,0,1,16],0],
              'operation':'delete','replacement':None,'affectedScopes':affected,'sourceFingerprint':'a'*64}
            self.assertLess(len(json.dumps(payload).encode()),48000)
            plan=edit.create_plan(payload);directory,path,row=edit._load(plan['planId'])
            row.update(state='verified',result={'affectedScopes':affected,'independentReopenVerified':True})
            durable_json(path,row)
            self.assertGreater(path.stat().st_size,65536)
            self.assertEqual(edit._load(plan['planId'])[2]['state'],'verified')
