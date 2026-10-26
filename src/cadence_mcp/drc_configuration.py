"""Decode source-bound native DRC configuration without claiming rule execution."""
import hashlib,json,re
from .core import CadenceError
ROWS=('IN_PIN','IO_PIN','OUT_PIN','OC_PIN','PAS_PIN','HIZ_PIN','OE_PIN','IN_PORT','IO_PORT','OUT_PORT','OC_PORT','PAS_PORT','HIZ_PORT','OE_PORT','DBGLOBAL','UNCONNECTED')
ONLINE=tuple('RunElectricRule'+s+'Online' for s in ('SingleNodeNets','NoDrivingSource','DuplicateNetNames','Offpage','Ports','Wires','FloatingPins'))
def decode_drc_configuration(data):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('duplicate field')
            result[k]=v
        return result
    try:
        if set(data)!={'nativeConfiguration','onlineEnabled','flowEnabled'}:raise ValueError('envelope')
        raw=data['nativeConfiguration']
        if not isinstance(raw,str) or len(raw.encode('utf-8'))>65536:raise ValueError('bound')
        config=json.loads(raw,object_pairs_hook=unique)
        if not isinstance(config,dict):raise ValueError('shape')
        flags={k:v for k,v in config.items() if k.startswith('Run')}
        if not set(ONLINE+('RunOnlineRules','RunElectricalRules'))<=flags.keys():raise ValueError('missing flag')
        if any(not re.fullmatch(r'Run[A-Za-z]+',k) or v not in ('0','1') for k,v in flags.items()):raise ValueError('invalid flag')
        matrix=config['ERCMatrix']
        if not isinstance(matrix,dict) or set(matrix)!=set(ROWS) or any(not isinstance(v,list) or len(v)!=16 or any(type(s) is not str or s not in ('-','W','E') for s in v) for v in matrix.values()):raise ValueError('matrix')
        if any(type(data[k]) is not bool for k in ('onlineEnabled','flowEnabled')):raise ValueError('signal')
    except (ValueError,TypeError,KeyError,UnicodeError) as e:
        raise CadenceError('invalid_drc_configuration','Native DRC configuration is missing required fields or has an unsupported shape.') from e
    return {'configurationSha256':hashlib.sha256(raw.encode('utf-8')).hexdigest(),'onlineEnabled':data['onlineEnabled'],'flowEnabled':data['flowEnabled'],'configuredFlags':{k:v=='1' for k,v in sorted(flags.items())},'onlineElectricalEnabledCount':sum(flags[k]=='1' for k in ONLINE),'onlineElectricalRuleCount':len(ONLINE),'ercColumnOrder':list(ROWS),'ercMatrix':matrix,'rulesExecuted':False,'coverageVerified':False,'scope':'native_configuration_readback_only'}
