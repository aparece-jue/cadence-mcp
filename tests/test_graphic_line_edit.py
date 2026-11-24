import copy
from pathlib import Path
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from cadence_mcp.capture_graphic_line_edit import CaptureGraphicLineEdits,declaration, line_records_state
from cadence_mcp.core import CadenceError
from cadence_mcp.isolated_jobs import digest


def change():
    return dict(localStart=[-15,-10],localEnd=[45,35],location=[900,700],rotation=0,mirror=0,
                lineStyle=2,lineWidth=1,lineColor=47)


class GraphicLineEditTests(unittest.TestCase):
    def test_all_pose_endpoints_match_independent_integer_table(self):
        table=[[[885,690],[945,735]],[[915,690],[855,735]],
               [[890,715],[935,655]],[[890,685],[935,745]],
               [[915,710],[855,665]],[[885,710],[945,665]],
               [[910,685],[865,745]],[[910,715],[865,655]]]
        for r in range(4):
            for m in range(2):
                value=change();value.update(rotation=r,mirror=m)
                self.assertEqual(declaration(value)[1]['pageControlPoints'],table[r*2+m])

    def test_schema_rejects_boolean_coercion_unknown_and_incomplete_changes(self):
        for key,value in [('rotation',True),('mirror',2),('lineStyle',1.0),('lineColor',49),
                          ('localStart',[False,0]),('localEnd',[0]),('eval','unsafe')]:
            row=change();row[key]=value
            with self.subTest(key=key),self.assertRaises(CadenceError):declaration(row)
        row=change();del row['lineColor']
        with self.assertRaises(CadenceError):declaration(row)

    def test_degenerate_and_transformed_overflow_rejected(self):
        for row in [dict(change(),localEnd=[-15,-10]),dict(change(),location=[1000000,0])]:
            with self.assertRaises(CadenceError):declaration(row)

    def capture(self):
        row=dict(design=Path('private/design.dsn'),data=dict(page=[dict(objectId='p',schematicId='s',name='PAGE')],
            schematic=[dict(objectId='s',name='ROOT')]))
        return SimpleNamespace(config=object(),_session=lambda sid:row)

    def test_exact_native_id_keeps_other_duplicate_geometry_color_and_order(self):
        old=[dict(nativeId=101,geometry='same',lineColor=8),dict(nativeId=102,geometry='same',lineColor=47)]
        replacement=dict(nativeId=102,geometry='new',lineColor=1)
        before=copy.deepcopy(old)
        with patch('cadence_mcp.capture_graphic_line_edit.read_lines',return_value=old):
            got=line_records_state(self.capture(),'sid','p',102,replacement)
            self.assertEqual(got,[dict(scope=['ROOT','PAGE'],digest=digest([old[0],replacement]))])
            self.assertEqual(line_records_state(self.capture(),'sid','p',102),
                             [dict(scope=['ROOT','PAGE'],digest=digest([old[0]]))])
        self.assertEqual(old,before)

    def test_missing_and_duplicate_native_ids_refused(self):
        for old,target in [([dict(nativeId=101),dict(nativeId=101)],101),([dict(nativeId=101)],102)]:
            with patch('cadence_mcp.capture_graphic_line_edit.read_lines',return_value=old),self.assertRaises(CadenceError):
                line_records_state(self.capture(),'sid','p',target)

    def test_invalid_and_ambiguous_locators_rejected_before_native_read(self):
        cap=self.capture();cap.lock=threading.RLock();writer=CaptureGraphicLineEdits.__new__(CaptureGraphicLineEdits);writer.capture=cap
        with patch('cadence_mcp.capture_graphic_line_edit.page_rows') as native:
            for ident in [True,'x'*257,'p/graphic-'+'1'*5000,'p/graphic-4097','foreign/graphic-1']:
                with self.subTest(ident=str(ident)[:40]),self.assertRaises(CadenceError):writer.plan_edit('sid',ident,'delete')
            original=cap._session('sid');original['data']['schematic'].append(dict(objectId='s2',name='ROOT'))
            cap._session=lambda sid:original
            with self.assertRaises(CadenceError) as error:writer.plan_edit('sid','p/graphic-1','delete')
            self.assertEqual(error.exception.code,'ambiguous_target');native.assert_not_called()
