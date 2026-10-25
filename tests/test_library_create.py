import copy,json,tempfile,unittest
from pydantic import ValidationError
from pathlib import Path
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates,validate_spec,expected_graph
from cadence_mcp.server import Artifact
def spec():return {'packageName':'TEST','referenceTemplate':'U?','footprint':'TEST_FP','expectedHomogeneous':True,'symbols':[{'cellName':'C','partName':'P.Normal','pins':[{'position':0,'name':'A','pinType':4,'start':[0,0],'hotSpot':[-10,0],'visible':True}],'lines':[]}],'devices':[{'designator':'A','position':0,'cellName':'C','mapping':[{'position':0,'number':'1','shared':False,'swapId':0}]}]}
class SpecTests(unittest.TestCase):
    def test_complete_maps_required_and_positions_are_explicit(self):
        s=spec();self.assertEqual(validate_spec(s),s)
        for edit in [lambda s:s['devices'][0]['mapping'].clear(),lambda s:s['symbols'][0]['pins'][0].update(position=True),lambda s:s['symbols'][0]['pins'][0].update(pinType=8)]:
            broken=spec();edit(broken)
            with self.assertRaises(CadenceError):validate_spec(broken)
    def test_shared_physical_numbers_need_explicit_consistent_function(self):
        s=spec();d=copy.deepcopy(s['devices'][0]);d.update(designator='B',position=1);s['devices'].append(d)
        with self.assertRaises(CadenceError):validate_spec(s)
        for dev in s['devices']:dev['mapping'][0]['shared']=True
        self.assertEqual(len(expected_graph(validate_spec(s))['pins']),2)
        s['devices'][1]['mapping'][0]['swapId']=1
        with self.assertRaises(CadenceError):validate_spec(s)
    def test_artifact_contract_distinguishes_declaration_digest_without_weakening_fields(self):
        row={'artifactId':'test','kind':'capture_created_library','workspaceRelativePath':'library.olb','sha256':'a'*64,'size':1,'producedByJob':'job','sourceFingerprint':'b'*64,'createdAt':'2026-10-23T00:00:00+00:00','validationState':'validated'}
        self.assertIsNone(Artifact.model_validate(row).sourceKind)
        self.assertEqual(Artifact.model_validate(row|{'sourceKind':'new_library_spec'}).sourceKind,'new_library_spec')
        for extra in [{'sourceKind':'arbitrary'},{'eval':'unsafe'}]:
            with self.assertRaises(ValidationError):Artifact.model_validate(row|extra)
    def test_duplicate_cells_unused_symbols_and_partial_device_positions_rejected(self):
        for change in [lambda s:s['symbols'].append(copy.deepcopy(s['symbols'][0])),lambda s:s['devices'][0].update(position=1),lambda s:s['devices'][0].update(cellName='outside')]:
            s=spec();change(s)
            with self.assertRaises(CadenceError):validate_spec(s)
    def test_semantic_order_not_source_list_order_defines_expectations(self):
        s=spec();p=copy.deepcopy(s['symbols'][0]['pins'][0]);p.update(position=1,name='B',hotSpot=[10,0]);s['symbols'][0]['pins'].append(p)
        s['devices'][0]['mapping'].append({'position':1,'number':'2','shared':False,'swapId':0});other=copy.deepcopy(s);other['symbols'][0]['pins'].reverse();other['devices'][0]['mapping'].reverse()
        self.assertEqual(expected_graph(s),expected_graph(other))
    def test_cancelled_plan_and_spec_tampering_cannot_start_native(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();config=Config(install,root/'work',(root,));c=LibraryCreates(config,LibraryService(config));p=c.plan(spec());c.cancel(p['planId'],p['planDigest'])
            with patch.object(c,'execute') as native:
                with self.assertRaises(CadenceError):c.apply(p['planId'],p['planDigest'],'cancel')
                native.assert_not_called()
            p=c.plan(spec());_,path,row=c._load(p['planId']);row['plan']['payload']['spec']['footprint']='changed';path.write_text(json.dumps(row))
            with self.assertRaises(CadenceError):c.apply(p['planId'],p['planDigest'],'tamper')

    def test_verified_native_swap_id_boundary(self):
        for value in (-1,0,125,126):
            s=spec();s['devices'][0]['mapping'][0]['swapId']=value
            self.assertEqual(validate_spec(s),s)
        for value in (-2,127,128,202,4095,True):
            s=spec();s['devices'][0]['mapping'][0]['swapId']=value
            with self.assertRaises(CadenceError):validate_spec(s)

    def test_alternate_part_views_keep_device_and_physical_counts(self):
        s=spec();alt=copy.deepcopy(s['symbols'][0]);alt['partName']='P.Convert';alt['pins'][0]['hotSpot']=[10,0];s['symbols'].append(alt)
        self.assertEqual(validate_spec(s),s);graph=expected_graph(s)
        self.assertEqual(graph['package']['size'],1);self.assertEqual(len(graph['devices']),2)
        self.assertEqual(len({p[6] for p in graph['pins']}),1)
    def test_alternate_view_cannot_change_pin_function_or_position(self):
        for change in ({'name':'DIFFERENT'},{'pinType':0},{'position':2}):
            s=spec();alt=copy.deepcopy(s['symbols'][0]);alt['partName']='P.Convert';alt['pins'][0].update(change);s['symbols'].append(alt)
            with self.assertRaises(CadenceError):validate_spec(s)
    def test_alternate_cell_name_case_alias_is_ambiguous(self):
        s=spec();alt=copy.deepcopy(s['symbols'][0]);alt.update(partName='P.Convert',cellName='c');s['symbols'].append(alt)
        with self.assertRaises(CadenceError):validate_spec(s)
