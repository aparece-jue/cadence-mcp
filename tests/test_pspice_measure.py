import math,unittest
from cadence_mcp.core import CadenceError
from cadence_mcp.pspice_measure import measure_samples
def rows(values,imaginary=None):return [{'index':i,'real':x,'imaginary':imaginary[i] if imaginary is not None else None} for i,x in enumerate(values)]
class MeasureTests(unittest.TestCase):
    def test_summary_names_distinguish_sample_rms_and_signed_area(self):
        value=measure_samples(rows([0,1,2]),rows([0,1,2]))
        self.assertEqual(value['sampleMean'],1);self.assertAlmostEqual(value['sampleRms'],math.sqrt(5/3));self.assertEqual(value['areaTrapezoidal'],2)
        self.assertAlmostEqual(value['intervalRms'],math.sqrt(4/3));self.assertEqual(value['intervalMean'],1)
        reverse=measure_samples(rows([2,1,0]),rows([2,1,0]));self.assertEqual(reverse['areaTrapezoidal'],-2)
    def test_interpolation_in_both_axis_orders_and_no_extrapolation(self):
        for axis,value in [([0,2],[0,4]),([2,0],[4,0])]:
            self.assertEqual(measure_samples(rows(axis),rows(value),'value_at',at_axis=0.5)['value'],1)
            with self.assertRaises(CadenceError):measure_samples(rows(axis),rows(value),'value_at',at_axis=3)
    def test_crossing_direction_plateau_and_missing_are_explicit(self):
        self.assertEqual(measure_samples(rows([0,1,2]),rows([0,1,0]),'first_crossing',threshold=0.5,direction='falling')['axisValue'],1.5)
        self.assertFalse(measure_samples(rows([0,1]),rows([0,1]),'first_crossing',threshold=2)['found'])
        self.assertEqual(measure_samples(rows([0,1]),rows([1,1]),'first_crossing',threshold=1)['direction'],'plateau')
        self.assertFalse(measure_samples(rows([0,1]),rows([1,1]),'first_crossing',threshold=1,direction='rising')['found'])
    def test_crossing_first_uses_increasing_axis_when_stored_backwards(self):
        value=measure_samples(rows([2,1,0]),rows([0,1,0]),'first_crossing',threshold=0.5,direction='rising')
        self.assertEqual(value['axisValue'],0.5);self.assertEqual(value['bracketIndices'],[2,1])
    def test_complex_components_and_real_axis_validation(self):
        data=rows([3,0],[4,-1]);axis=rows([0,1],[0,0])
        self.assertEqual(measure_samples(axis,data,'value_at','magnitude',at_axis=0)['value'],5)
        self.assertEqual(measure_samples(axis,data,'value_at','imaginary',at_axis=1)['value'],-1)
        with self.assertRaises(CadenceError):measure_samples(rows([0,1],[0,1]),data)
        with self.assertRaises(CadenceError):measure_samples(rows([0,1]),rows([0,1]),component='imaginary')
    def test_bad_axes_parameters_and_overflow_do_not_produce_success(self):
        for axis in ([0,0],[0,2,1]):
            with self.assertRaises(CadenceError):measure_samples(rows(axis),rows(axis))
        for options in [{'measurement':'value_at','at_axis':True},{'measurement':'summary','threshold':1},{'measurement':'first_crossing','threshold':float('nan')}]:
            with self.assertRaises(CadenceError):measure_samples(rows([0,1]),rows([0,1]),**options)
        with self.assertRaises(CadenceError):measure_samples(rows([0,1e308]),rows([1e308,1e308]))
        self.assertAlmostEqual(measure_samples(rows([0,1]),rows([1e308,-1e308]))['sampleRms']/1e308,1)
