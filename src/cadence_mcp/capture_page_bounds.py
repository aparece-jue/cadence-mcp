"""Revision-bound native page dimensions and bounded comment-control-point checks."""
import copy,json,math
from .core import CadenceError,new_id
from .environment import run_tcl
from .capture_page_vectors import query_page_vectors

FLAGS=('isMetric','borderDisplayed','borderPrinted','gridRefDisplayed','gridRefPrinted','titleBlockDisplayed','titleBlockPrinted','ansiGridRefs')
PAIRS=('size','docUnits','drawableDocUnits','outerBorderMargin','innerBorderMargin')
FLOATS=('docUnitsPerInch','physicalGranularity','pinToPinScaleFactor')
FIELDS={'sizeName','pageWidth','pageHeight','pinToPin',*FLAGS,*PAIRS,*FLOATS}

def validate_dimensions(data):
    try:
        if not isinstance(data,dict) or set(data)!=FIELDS:raise ValueError('fields')
        if not isinstance(data['sizeName'],str) or len(data['sizeName'])>256 or '\x00' in data['sizeName']:raise ValueError('name')
        if any(type(data[k]) is not int or not 0<=data[k]<=2147483647 for k in ('pageWidth','pageHeight')) or type(data['pinToPin']) is not int or not 1<=data['pinToPin']<=2147483647:raise ValueError('physical dimensions')
        if any(type(data[k]) is not int or data[k] not in (0,1) for k in FLAGS):raise ValueError('flags')
        if any(type(data[k]) not in (int,float) or not math.isfinite(data[k]) or not 0<data[k]<=1e12 for k in FLOATS):raise ValueError('scale')
        for k in PAIRS:
            if not isinstance(data[k],list) or len(data[k])!=2 or any(type(v) is not int or not -2147483648<=v<=2147483647 for v in data[k]):raise ValueError('pair')
        if any(v<0 for k in ('size','docUnits') for v in data[k]):raise ValueError('negative page size')
    except (TypeError,ValueError,KeyError) as error:raise CadenceError('invalid_worker_result','Invalid native page dimensions.','decode') from error
    return copy.deepcopy(data)

def query_page_dimensions(capture,sid,page_id):
    with capture.lock:
        session=capture._session(sid);data=session['data'];page=next((p for p in data['page'] if p['objectId']==page_id),None)
        if page is None:raise CadenceError('invalid_scope','Page does not belong to this immutable session.')
        sch=next(s for s in data['schematic'] if s['objectId']==page['schematicId'])
        if sum(s['name']==sch['name'] for s in data['schematic'])!=1 or sum(p['name']==page['name'] and p['schematicId']==page['schematicId'] for p in data['page'])!=1:raise CadenceError('ambiguous_target','Page semantic identity is not unique.')
        if any(len(n)>512 or '\x00' in n for n in (sch['name'],page['name'])):raise CadenceError('input_limit','Page locator exceeds bounds.')
        cache=session.setdefault('pageDimensions',{})
        if page_id not in cache:
            directory=session['design'].parent;out=directory/(new_id('page-dimensions')+'.json');run_tcl(capture.config,'inspect_page_dimensions.tcl',[str(session['design']),str(out),sch['name'],page['name']],directory);capture._session(sid)
            if out.stat().st_size>16384:raise CadenceError('output_limit','Page dimension output exceeds16KiB.')
            cache[page_id]=validate_dimensions(json.loads(out.read_text(encoding='utf-8')));out.unlink()
        raw=copy.deepcopy(cache[page_id]);w,h=raw['docUnits'];known=w>0 and h>0
        return {'sessionId':sid,'revision':session['revision'],'pageId':page_id,'nativeParameters':raw,'coordinateUnits':'capture_native_integer','fullPageBounds':[0,0,w,h] if known else None,'dimensionsKnown':known,'readOnly':True,'notChecked':['physical_printable_origin','rendered_page_clipping','glyph_bounds','electrical_connectivity']}

def classify_control_points(rows,bounds,margin=0):
    if type(margin) is not int or not 0<=margin<=1000000 or not isinstance(bounds,list) or len(bounds)!=4 or any(type(v) is not int for v in bounds) or bounds[:2]!=[0,0] or min(bounds[2:])<=2*margin:raise CadenceError('invalid_page_bounds','Require positive native page bounds and a margin smaller than half each dimension.')
    x0,y0,x1,y1=margin,margin,bounds[2]-margin,bounds[3]-margin
    if not isinstance(rows,list) or len(rows)>4096:raise CadenceError('geometry_limit','At most4096 comment graphics are supported.')
    findings=[];points=0
    for row in rows:
        if row['kind']=='unsupported':raise CadenceError('unsupported_graphics','Cannot certify all comment control points with unsupported geometry.')
        for index,p in enumerate(row['pageControlPoints']):
            points+=1
            if points>65536:raise CadenceError('geometry_limit','At most65536 control points are supported.')
            sides=[s for s,test in [('left',p[0]<x0),('top',p[1]<y0),('right',p[0]>x1),('bottom',p[1]>y1)] if test]
            if sides:
                if len(findings)>=1000:raise CadenceError('finding_limit','More than1000 out-of-bounds control points; no partial success is returned.')
                findings.append({'objectId':row['objectId'],'kind':row['kind'],'controlPointIndex':index,'point':copy.deepcopy(p),'sides':sides,'ruleId':'PAGE-CONTROL-POINT-OUTSIDE'})
    return {'checkedBounds':[x0,y0,x1,y1],'margin':margin,'objectsChecked':len(rows),'controlPointsChecked':points,'findings':findings,'allSupportedControlPointsInBounds':not findings,'complete':True,'designPassed':None}

def check_page_graphic_bounds(capture,sid,page_id,margin=0):
    with capture.lock:
        dimensions=query_page_dimensions(capture,sid,page_id)
        if not dimensions['dimensionsKnown']:raise CadenceError('page_dimensions_unknown','Native page size is zero; no clipping or in-bounds verdict is available.')
        rows=[];cursor=None
        while True:
            result=query_page_vectors(capture,sid,page_id,cursor,1000);rows.extend(result['items']);cursor=result['nextCursor']
            if cursor is None:break
        checked=classify_control_points(rows,dimensions['fullPageBounds'],margin);capture._session(sid)
        return {**checked,'sessionId':sid,'revision':dimensions['revision'],'pageId':page_id,'readOnly':True,'scope':'page_comment_graphic_declared_control_points','notChecked':['actual_glyph_bounds','curve_or_arc_clipping','parts_wires_titleblocks_nested_symbols','physical_printable_area','electrical_connectivity','native_drc']}
