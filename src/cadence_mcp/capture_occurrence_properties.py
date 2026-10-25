"""Occurrence effective and direct-user layers stay separate from definition layers."""
import copy,json
from .core import CadenceError,new_id,write_json
from .capture_hierarchy import get_hierarchy
from .environment import run_tcl

def validate_layers(data,root):
    try:
        if not isinstance(data,dict) or set(data)!={'effective','user','definition'}:raise ValueError('shape')
        definition=data['definition']
        if root and definition is not None:raise ValueError('root definition')
        if not root and (not isinstance(definition,dict) or set(definition)!={'nativeId','reference','fullReference','deviceDesignator','kind','effective','user'} or type(definition['nativeId']) is not int or any(not isinstance(definition[k],str) for k in ('reference','fullReference','deviceDesignator')) or definition['kind'] not in ('placed','drawn')):raise ValueError('definition identity')
        text=0
        for owner in [data]+([definition] if definition is not None else []):
            for layer in ('effective','user'):
                rows=owner[layer];names=set()
                if not isinstance(rows,list) or len(rows)>512:raise ValueError('count')
                for prop in rows:
                    if not isinstance(prop,dict) or set(prop)!={'name','value'} or any(not isinstance(v,str) for v in prop.values()) or not 1<=len(prop['name'])<=256 or len(prop['value'])>16384 or prop['name'] in names:raise ValueError('property')
                    names.add(prop['name']);text+=len(prop['name'].encode('utf-8'))+len(prop['value'].encode('utf-8'))
                owner[layer]=sorted(copy.deepcopy(rows),key=lambda p:p['name'])
        if text>8*1024*1024:raise ValueError('text budget')
        return data
    except (ValueError,TypeError,KeyError,AttributeError) as error:raise CadenceError('invalid_worker_result','Invalid bounded occurrence property layers.','decode') from error

def query_occurrence_properties(capture,sid,occurrence_id):
    with capture.lock:
        s=capture._session(sid);get_hierarchy(capture,sid,None,1000)
        target=next((r for r in s['hierarchy'] if r['occurrenceId']==occurrence_id),None)
        if target is None:raise CadenceError('object_not_found','Occurrence is outside this session/revision hierarchy.')
        if target['parentId'] is None:raise CadenceError('capability_unavailable','Root occurrence property binding is unverified after a native access violation; root is a design context, not a component occurrence.')
        directory=s['design'].parent;request=directory/(new_id('occurrence-props-request')+'.json');output=directory/(new_id('occurrence-props')+'.json')
        write_json(request,{'segments':target['instancePathSegments'],'path':target['path'],'hierarchicalPath':target['hierarchicalPath']})
        run_tcl(capture.config,'inspect_occurrence_properties.tcl',[str(s['design']),str(request),str(output)],directory);capture._session(sid)
        if output.stat().st_size>16*1024*1024:raise CadenceError('output_limit','Occurrence properties exceed16MiB.')
        data=validate_layers(json.loads(output.read_text(encoding='utf-8')),target['parentId'] is None);request.unlink();output.unlink()
        return {'sessionId':sid,'revision':s['revision'],'occurrenceId':occurrence_id,'instancePathSegments':list(target['instancePathSegments']),'reference':target['reference'],'context':'root_design_context' if target['parentId'] is None else 'component_occurrence',**data,'readOnly':True,'counts':{layer:len(data[layer]) for layer in ('effective','user')},'scope':'native_occurrence_and_immediate_definition_layers','propertySourceResolutionVerified':False,'notChecked':['complete_library_inheritance_chain','display_property_layers','external_design_closure','occurrence_pin_net_connectivity']}
