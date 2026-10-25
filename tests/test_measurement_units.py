import copy,unittest
from cadence_mcp.pspice_measurement_units import analysis_axis,annotate_measurements
def annotate(expression='MAX(V(2))',declaration='MAX V(2)',analysis='dc',text='.DC V1 0 5 1',fields=None):
 return annotate_measurements([{'name':'x','expression':expression,'fields':fields or {'value':2.5,'from':0,'to':5},'raw':'literal native evidence','state':'evaluated'}],[{'name':'X','expression':declaration}],analysis,[text])
class MeasurementUnitTests(unittest.TestCase):
 def test_voltage_result_and_dc_voltage_axis(self):
  rows,meta=annotate();self.assertEqual({k:u['unit'] for k,u in rows[0]['fieldUnits'].items()},{'value':'V','from':'V','to':'V'});self.assertFalse(meta['nativeUnitMetadataAvailable'])
 def test_current_sweep_and_value_are_separate_dimensions(self):
  rows,_=annotate(text='.DC IBIAS 0 1 .1');self.assertEqual(rows[0]['fieldUnits']['value']['unit'],'V');self.assertEqual(rows[0]['fieldUnits']['to']['unit'],'A')
 def test_current_statistic_and_frequency_axis(self):
  rows,_=annotate(expression='RMS(I(V1))',declaration='RMS I(V1)',analysis='ac',fields={'value':0.01,'at':100});self.assertEqual(rows[0]['fieldUnits']['value']['unit'],'A');self.assertEqual(rows[0]['fieldUnits']['at']['unit'],'Hz')
 def test_when_value_is_voltage_at_field_is_time_not_name_based(self):
  rows,_=annotate(expression='V(2)',declaration='WHEN V(2)=.632 RISE=1',analysis='transient',fields={'value':.632,'at':.001});self.assertEqual(rows[0]['fieldUnits']['value']['unit'],'V');self.assertEqual(rows[0]['fieldUnits']['at']['unit'],'s')
 def test_trigger_target_difference_uses_independent_axis(self):
  rows,_=annotate(expression=None,declaration='TRIG V(1) VAL=0.2 RISE=1 TARG V(1) VAL=.8 RISE=1',analysis='transient',fields={'value':.002,'from':.001,'to':.003});self.assertEqual({u['unit'] for u in rows[0]['fieldUnits'].values()},{'s'})
 def test_compound_param_and_decibel_expressions_remain_unknown(self):
  for expr in ('MAX(V(2)*I(V1))','DB(V(2))','MIN_AT(V(2))',None):
   rows,meta=annotate(expression=expr,declaration='PARAM {x}',fields={'value':1});self.assertIsNone(rows[0]['fieldUnits']['value']['unit']);self.assertEqual(meta['unknownUnitFieldCount'],1)
 def test_ambiguous_parameter_and_nested_dc_axes_remain_unknown(self):
  for texts in (['.DC PARAM R 1 2 1'],['.DC V1 0 5 1 I1 0 1 .1'],['.DC V1 0 5 1','.DC I1 0 1 .1']):self.assertIsNone(analysis_axis('dc',texts)['unit'])
  self.assertEqual(analysis_axis('dc',['* ignored\n.DC LIN I1\n+ 0 1 .1'])['unit'],'A')
 def test_projection_keeps_original_numeric_and_raw_evidence(self):
  source=[{'name':'x','expression':'V(2)','fields':{'value':2},'raw':'literal'}];before=copy.deepcopy(source);rows,_=annotate_measurements(source,[{'name':'x','expression':'FIND V(2) AT=1'}],'ac',[]);self.assertEqual(source,before);self.assertEqual(rows[0]['fields'],source[0]['fields']);self.assertEqual(rows[0]['raw'],'literal')
