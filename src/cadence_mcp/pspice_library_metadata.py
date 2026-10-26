"""Bounded native single-file PSpice library metadata; no model execution or dependency traversal."""
import json,re
from pathlib import Path
from .core import CadenceError,checked_path,new_id,sha256,write_json
from .environment import ADAPTERS,process_env
from .process_tree import run_owned_process
HEADER=re.compile(r'^\s*\.(MODEL|SUBCKT)\s+([^\s(){}]+)',re.I)

def normalize_library_metadata(value,headers,pin_count):
    if not isinstance(value,dict) or not all(isinstance(value.get(k),list) for k in ('Data_Subckt','Data_Models')):
        raise CadenceError('invalid_library_metadata','Native parser did not return complete definition arrays.','verify')
    rows=[]
    try:
        for key,kind in [('Data_Subckt','subcircuit'),('Data_Models','model')]:
            for item in value[key]:
                item=json.loads(item) if isinstance(item,str) else item
                name=item['Title']
                if not isinstance(name,str) or not 1<=len(name)<=256 or any(c.isspace() or ord(c)<32 for c in name):raise ValueError()
                if kind=='subcircuit':
                    nodes=item['Nodes'];optional=item.get('OptNodes',[])
                    if not isinstance(nodes,list) or not isinstance(optional,list) or not all(isinstance(n,str) and 0<len(n)<=256 for n in nodes+optional):raise ValueError()
                    rows.append({'kind':kind,'name':name,'formalNodes':nodes,'optionalNodes':optional,'formalNodeCount':len(nodes),'matchesPinCount':pin_count>0 and len(nodes)==pin_count})
                else:
                    if not all(isinstance(item.get(k),str) and len(item[k])<=4096 for k in ('Type','AKO','Nodes')):raise ValueError()
                    rows.append({'kind':kind,'name':name,'modelType':item['Type'],'akoReference':item['AKO'],'nativeNodeDescription':item['Nodes']})
        expected=sorted(('model' if k.upper()=='MODEL' else 'subcircuit',n.casefold()) for k,n in headers)
        actual=sorted((x['kind'],x['name'].casefold()) for x in rows)
        if actual!=expected or len(set(actual))!=len(actual):raise ValueError()
        matching=value.get('matchingSubckts','')
        if not isinstance(matching,str):raise ValueError()
        matching=matching.split()
        if sorted(n.casefold() for n in matching)!=sorted(x['name'].casefold() for x in rows if x['kind']=='subcircuit' and x['matchesPinCount']):raise ValueError()
    except (ValueError,TypeError,KeyError,json.JSONDecodeError) as error:
        raise CadenceError('invalid_library_metadata','Native definitions or pin filter differ from source declarations.','verify') from error
    return rows

def inspect_library_metadata(config,source_library,pin_count=0,offset=0,limit=100):
    if type(pin_count) is not int or not 0<=pin_count<=4096 or type(offset) is not int or not 0<=offset<=100000 or type(limit) is not int or not 1<=limit<=1000:
        raise CadenceError('invalid_query','Use bounded pin count, offset and page size.')
    source=checked_path(source_library,config.read_roots)
    if not source.is_file() or source.suffix.lower()!='.lib' or source.stat().st_size>8*1024*1024:
        raise CadenceError('unsupported_input','Provide a single .lib file up to8MiB.')
    before=sha256(source);raw=source.read_bytes()
    if len(raw)>8*1024*1024 or b'\x00' in raw:raise CadenceError('unsupported_input','Binary/oversized libraries are not supported.')
    text=raw.decode('utf-8-sig',errors='surrogateescape');headers=[];depth=0;local_headers=0
    for line in text.splitlines():
        stripped=line.strip()
        if not stripped or stripped.startswith('*'):continue
        if re.match(r'^\.(?:LIB|INC|INCLUDE)\b',stripped,re.I):raise CadenceError('unsupported_library_reference','Inspect one file directly; referenced libraries require explicit preparation.')
        header=HEADER.match(line)
        if header:
            if any(0xD800<=ord(c)<=0xDFFF for c in header[2]):raise CadenceError('unsupported_encoding','Definition names must be valid UTF-8.')
            if depth==0:headers.append((header[1],header[2]))
            else:local_headers+=1
            if header[1].upper()=='SUBCKT':depth+=1
            if depth>32:raise CadenceError('input_limit','Subcircuit nesting exceeds32.')
        elif re.match(r'^\.ENDS\b',stripped,re.I):
            if depth==0:raise CadenceError('invalid_library_structure','Unmatched ENDS; native metadata would be incomplete.')
            depth-=1
    if depth:raise CadenceError('invalid_library_structure','Unterminated subcircuit definition.')
    if len(headers)+local_headers>100000:raise CadenceError('input_limit','Definition count exceeds bound.')
    directory=config.workspace_root/new_id('library-metadata');directory.mkdir();directory=checked_path(str(directory),(config.workspace_root,));snapshot=directory/'library.lib';
    with snapshot.open('xb') as stream:stream.write(raw)
    if sha256(source)!=before or sha256(snapshot)!=before:raise CadenceError('source_changed','Library changed while copying.')
    output=directory/'native.json';process=run_owned_process([config.install_root/'tcltk/bin/tclsh.exe',ADAPTERS/'inspect_pspice_library.tcl',config.install_root,snapshot,str(pin_count),output],directory,process_env(config),config.timeout_seconds);write_json(directory/'process.json',process)
    if process['returnCode']!=0 or process['remainingOwnedProcesses']!=0:raise CadenceError('library_parser_failed','Native library parser did not finish cleanly.','worker')
    if not output.is_file() or output.stat().st_size>64*1024*1024:raise CadenceError('output_limit','Native metadata is missing or exceeds64MiB.','worker')
    try:receipt=json.loads(output.read_text(encoding='utf-8'));value=json.loads(receipt['value']);assert receipt['returned'] is True
    except (ValueError,KeyError,TypeError,AssertionError) as error:raise CadenceError('invalid_library_metadata','Native library output is not a successful JSON result.','verify') from error
    rows=normalize_library_metadata(value,headers,pin_count)
    if sha256(source)!=before or sha256(snapshot)!=before:raise CadenceError('source_changed','Library bytes changed during inspection.')
    return {'definitionScope':'top_level','localDefinitionsNotReturned':local_headers,'sourceFingerprint':before,'copiedSourceFingerprint':sha256(snapshot),'total':len(rows),'offset':offset,'items':rows[offset:offset+limit],'hasMore':offset+limit<len(rows),'pinCountFilter':pin_count,'subcircuitCount':sum(x['kind']=='subcircuit' for x in rows),'modelCount':sum(x['kind']=='model' for x in rows),'sourceUnchanged':True,'nativeParserCompleted':True,'dependencyClosureVerified':False,'modelValidityVerified':False,'notChecked':['referenced_libraries','model_dependency_reachability','model_validity','solver','full_spice_grammar','physical_pin_mapping','local_definition_metadata']}
