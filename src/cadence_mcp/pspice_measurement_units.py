"""Conservative unit annotations, separate from immutable native numeric evidence."""
import copy,re

def unknown(reason):return {'unit':None,'unitSource':'unknown','reason':reason}

def analysis_axis(analysis,texts):
    if analysis=='transient':return {'unit':'s','unitSource':'declared_analysis_dimension','basis':'TRAN independent time'}
    if analysis=='ac':return {'unit':'Hz','unitSource':'declared_analysis_dimension','basis':'AC independent frequency'}
    if analysis!='dc':return unknown('unrecognized_analysis')
    statements=[]
    for text in texts:
        logical=[]
        for line in text.splitlines():
            line=line.strip()
            if not line or line.startswith('*'):continue
            if line.startswith('+') and logical:logical[-1]+=' '+line[1:].strip()
            else:logical.append(line)
        statements.extend(line.split() for line in logical if re.match(r'^\.DC(?:\s|$)',line,re.I))
    if len(statements)!=1:return unknown('dc_sweep_not_unique')
    tokens=statements[0][1:]
    if tokens and tokens[0].upper() in ('LIN','DEC','OCT'):tokens=tokens[1:]
    if len(tokens)!=4 or not re.fullmatch(r'[VI][A-Za-z0-9_.$]*',tokens[0],re.I):return unknown('dc_sweep_dimension_not_verified')
    return {'unit':'V' if tokens[0][0].upper()=='V' else 'A','unitSource':'declared_dc_source_sweep','basis':tokens[0]}

def value_unit(row,declaration,axis):
    # Use the native result expression, not a measurement name such as "tau".
    expression=row.get('expression')
    atom=r'([VI])\(\s*[^()\r\n]+?\s*\)'
    match=re.fullmatch(atom,expression or '',re.I)
    if match is None:match=re.fullmatch(r'(?:MIN|MAX|AVG|RMS|PP)\(\s*'+atom+r'\s*\)',expression or '',re.I)
    if match:
        return {'unit':'V' if match[1].upper()=='V' else 'A','unitSource':'verified_native_expression_dimension','basis':expression}
    if expression is None and re.match(r'^TRIG\s',declaration.get('expression',''),re.I) and re.search(r'\sTARG\s',declaration['expression'],re.I):
        return {**axis,'basis':'TRIG/TARG independent-axis difference; '+axis.get('basis',axis.get('reason','unknown'))}
    return unknown('native_expression_dimension_not_verified')

def annotate_measurements(rows,declarations,analysis,texts):
    axis=analysis_axis(analysis,texts);declared={d['name'].casefold():d for d in declarations};result=[];known=0;unverified=0
    for source in rows:
        row=copy.deepcopy(source);declaration=declared.get(row['name'].casefold())
        if declaration is None:raise ValueError('Measurement unit context lacks a verified declaration')
        units={}
        for field in row['fields']:
            unit=value_unit(row,declaration,axis) if field=='value' else copy.deepcopy(axis) if field in ('at','from','to') else unknown('unrecognized_field')
            units[field]=unit
            if unit['unit'] is None:unverified+=1
            else:known+=1
        row['fieldUnits']=units;result.append(row)
    return result,{'version':'1.0','nativeUnitMetadataAvailable':False,'analysisAxis':axis,'inferredUnitFieldCount':known,'unknownUnitFieldCount':unverified,'basis':'verified native expression and declared single-analysis sweep; raw numeric evidence is unchanged'}
