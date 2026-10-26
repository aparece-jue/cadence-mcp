"""Bounded decoding of observed native getDigital change records, not hazard interpretation."""
import math,re
from .core import CadenceError
FLOAT=re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$')
INTEGER=re.compile(r'[+-]?[0-9]+$')
SCOPE='unflagged_getDigital_change_records_v1'
def decode_digital_records(raw,block,trace):
 try:
  if set(raw)!={'block','trace','blockDigitalRows','nativeDigitalData'} or type(raw['block']) is not int or raw['block']!=block['index'] or raw['trace']!=trace or type(raw['blockDigitalRows']) is not int or raw['blockDigitalRows']!=block['digitalRowCount']:raise ValueError('receipt')
  text=raw['nativeDigitalData'];prefix=trace+"'"
  if not isinstance(text,str) or len(text)>16777216 or not text.startswith(prefix):raise ValueError('frame')
  tokens=text[len(prefix):].split(',');count=tokens.pop(0)
  if not re.fullmatch(r'[0-9]{1,6}',count):raise ValueError('count')
  count=int(count)
  if not 0<=count<=block['digitalRowCount']<=100000 or len(tokens)!=4*count:raise ValueError('count')
  rows=[];prior=-math.inf
  for i in range(count):
   time,strength,state,opaque=tokens[4*i:4*i+4]
   if not FLOAT.fullmatch(time) or any(len(v)>11 or not INTEGER.fullmatch(v) for v in (strength,state,opaque)):raise ValueError('numeric format')
   t=float(time);s=int(strength);v=int(state);tail=int(opaque)
   if not math.isfinite(t) or t<0 or t<prior or not 0<=s<64 or not -2147483648<=tail<=4294967295 or not 0<=v<=4294967295:raise ValueError('bounds')
   if v>5:raise CadenceError('unsupported_digital_state_flags','Native digital records contain unvalidated state flags; no partial trace is returned.','decode')
   rows.append({'index':i,'time':t,'state':'01XRFZ'[v],'stateCode':v,'strengthCode':s});prior=t
  return rows
 except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as error:
  raise CadenceError('invalid_digital_samples','Native digital frame does not match bounded change-record metadata.','decode') from error
