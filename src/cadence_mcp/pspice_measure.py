"""Finite sampled-waveform mathematics; no circuit/solver success inference."""
from bisect import bisect_left
import math
from .core import CadenceError

def finite(value):return type(value) in (int,float) and math.isfinite(value)
def validate_measurement(measurement,component,at_axis,threshold,direction):
    if measurement not in ('summary','value_at','first_crossing') or component not in ('real','imaginary','magnitude') or direction not in ('either','rising','falling'):raise CadenceError('invalid_measurement','Unknown bounded waveform measurement.')
    if measurement=='summary' and (at_axis is not None or threshold is not None or direction!='either'):raise CadenceError('invalid_measurement','Summary does not take axis/crossing parameters.')
    if measurement=='value_at' and (not finite(at_axis) or threshold is not None or direction!='either'):raise CadenceError('invalid_measurement','value_at requires one finite axis value.')
    if measurement=='first_crossing' and (not finite(threshold) or at_axis is not None):raise CadenceError('invalid_measurement','first_crossing requires one finite threshold.')

def measure_samples(axis,trace,measurement='summary',component='real',at_axis=None,threshold=None,direction='either'):
    validate_measurement(measurement,component,at_axis,threshold,direction)
    if not isinstance(axis,list) or not isinstance(trace,list) or not 1<=len(axis)==len(trace)<=100000:raise CadenceError('invalid_measurement_data','Nonempty matching bounded sample arrays are required.')
    xs=[];ys=[]
    for i,(a,v) in enumerate(zip(axis,trace)):
        if any(not isinstance(row,dict) or type(row.get('index')) is not int or row['index']!=i or not finite(row.get('real')) or (row.get('imaginary') is not None and not finite(row['imaginary'])) for row in (a,v)):raise CadenceError('invalid_measurement_data','Samples must have matching finite sequential indices.')
        if a.get('imaginary') not in (None,0):raise CadenceError('unsupported_axis','Measurements require a real sweep axis.')
        if component=='imaginary' and v.get('imaginary') is None:raise CadenceError('unsupported_component','A real trace has no imaginary component.')
        value=v['real'] if component=='real' else v['imaginary'] if component=='imaginary' else math.hypot(v['real'],v.get('imaginary') or 0)
        if not finite(value):raise CadenceError('measurement_numeric_range','Selected magnitude exceeds finite range.')
        xs.append(a['real']);ys.append(value)
    differences=[b-a for a,b in zip(xs,xs[1:])]
    if not finite(xs[-1]-xs[0]) or any(not finite(d) for d in differences):raise CadenceError('measurement_numeric_range','Axis span exceeds finite range.')
    if differences and not (all(d>0 for d in differences) or all(d<0 for d in differences)):raise CadenceError('unsupported_axis','Duplicate or nonmonotonic axis needs a dedicated discontinuity contract.')
    order='single' if not differences else 'increasing' if differences[0]>0 else 'decreasing'
    common={'measurement':measurement,'component':component,'sampleCount':len(xs),'axisDirection':order,'designPassed':None}
    if measurement=='summary':
        scale=max(map(abs,ys));normalized=[v/scale for v in ys] if scale else [0.0]*len(ys)
        mean=math.fsum(normalized)/len(ys)*scale;rms=math.sqrt(math.fsum(v*v for v in normalized)/len(ys))*scale
        area=math.fsum((a/2+b/2)*dx for a,b,dx in zip(normalized,normalized[1:],differences))*scale
        interval_mean=None;interval_rms=None
        if differences:
            span=xs[-1]-xs[0]
            interval_mean=math.fsum((a/2+b/2)*(dx/span) for a,b,dx in zip(normalized,normalized[1:],differences))*scale
            interval_rms=math.sqrt(math.fsum(((a*a+a*b+b*b)/3)*(dx/span) for a,b,dx in zip(normalized,normalized[1:],differences)))*scale
        if not all(finite(v) for v in (mean,rms,area) if v is not None) or any(v is not None and not finite(v) for v in (interval_mean,interval_rms)):raise CadenceError('measurement_numeric_range','Derived measurement exceeds finite range.')
        return {**common,'method':'sample_statistics_and_piecewise_linear_interval','minimum':min(ys),'maximum':max(ys),'sampleMean':mean,'sampleRms':rms,'intervalMean':interval_mean,'intervalRms':interval_rms,'areaTrapezoidal':area,'axisStart':xs[0],'axisEnd':xs[-1]}
    indices=list(range(len(xs)))
    if order=='decreasing':xs.reverse();ys.reverse();indices.reverse()
    if measurement=='value_at':
        if not xs[0]<=at_axis<=xs[-1]:raise CadenceError('axis_out_of_range','Requested interpolation lies outside the sampled sweep; no extrapolation.')
        index=bisect_left(xs,at_axis)
        if xs[index]==at_axis:return {**common,'method':'exact_sample','axisValue':at_axis,'value':ys[index],'bracketIndices':[indices[index],indices[index]]}
        a=index-1;b=index;fraction=(at_axis-xs[a])/(xs[b]-xs[a]);value=(1-fraction)*ys[a]+fraction*ys[b]
        if not finite(value):raise CadenceError('measurement_numeric_range','Interpolated value exceeds finite range.')
        return {**common,'method':'piecewise_linear_selected_component','axisValue':at_axis,'value':value,'bracketIndices':[indices[a],indices[b]]}
    # "First" means increasing axis, independently of storage/sweep direction.
    if len(xs)==1:
        found=ys[0]==threshold and direction=='either'
        return {**common,'found':found,'method':'single_sample_threshold','axisValue':xs[0] if found else None,'threshold':threshold,'direction':None,'bracketIndices':[indices[0],indices[0]] if found else None}
    for i,(a,b) in enumerate(zip(ys,ys[1:])):
        if a==b:
            if a==threshold and direction=='either':return {**common,'found':True,'method':'threshold_plateau_start','axisValue':xs[i],'threshold':threshold,'direction':'plateau','bracketIndices':[indices[i],indices[i+1]]}
            continue
        rising=b>a;kind='rising' if rising else 'falling'
        if direction not in ('either',kind) or not min(a,b)<=threshold<=max(a,b):continue
        scale=max(abs(a),abs(b),abs(threshold));fraction=(threshold/scale-a/scale)/(b/scale-a/scale)
        value=xs[i]*(1-fraction)+xs[i+1]*fraction
        if not finite(value):raise CadenceError('measurement_numeric_range','Crossing axis exceeds finite range.')
        return {**common,'found':True,'method':'piecewise_linear_selected_component_crossing','axisValue':value,'threshold':threshold,'direction':kind,'bracketIndices':[indices[i],indices[i+1]]}
    return {**common,'found':False,'method':'piecewise_linear_selected_component_crossing','axisValue':None,'threshold':threshold,'direction':None,'bracketIndices':None}
