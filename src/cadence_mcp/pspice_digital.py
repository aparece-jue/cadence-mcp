"""Bounded decoding of native getDigital transient change records."""
import math,re
from .core import CadenceError
FLOAT=re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$')
INTEGER=re.compile(r'[+-]?[0-9]+$')
SCOPE='unflagged_getDigital_change_records_v1'
VERIFIED_FLAGS_SCOPE='getDigital_change_records_with_verified_state_26_v1'
# The installed solver printed X for raw 26 at the same time in both invalid
# R-to-F and F-to-R controls. Do not mask other words or classify their hazards.
VERIFIED_FLAGGED_STATES={26:2}

def decode_digital_records(raw,block,trace,include_verified_flagged_states=False):
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
   level=v
   if v>5:
    if not include_verified_flagged_states or v not in VERIFIED_FLAGGED_STATES:
     raise CadenceError('unsupported_digital_state_flags','Native digital records contain a state code outside the requested scope; no partial trace is returned.','decode')
    level=VERIFIED_FLAGGED_STATES[v]
   row={'index':i,'time':t,'state':'01XRFZ'[level],'stateCode':level,'strengthCode':s}
   if include_verified_flagged_states:row['nativeStateCode']=v
   rows.append(row);prior=t
  return rows
 except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as error:
  raise CadenceError('invalid_digital_samples','Native digital frame does not match bounded change-record metadata.','decode') from error
